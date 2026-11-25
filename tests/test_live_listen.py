import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from octet_ableton.audio_capture import AudioError
from octet_ableton.live_audio import CaptureRecorder
from octet_ableton.live_listen import _validate_playhead, listen_live


class Bridge:
    def __init__(self, played_start_beat=None, end_overrides=None, tempo=120):
        self.calls = []
        self.tempo = tempo
        self.restored = False
        self.played_start_beat = played_start_beat
        self.end_overrides = end_overrides or {}

    def call(self, method, params=None, *, check_cancel):
        check_cancel()
        self.calls.append(method)
        if method == "lom":
            assert params == {"view": "session", "track_indices": []}
            return {"transport": {"bpm": self.tempo, "signature_numerator": 4, "signature_denominator": 4}}
        if method == "snapshot":
            return {"transport": {"bpm": self.tempo, "signature_numerator": 4, "signature_denominator": 4}, "tracks": []}
        if method == "capture_begin":
            self.started = time.monotonic()
            self.requested_start = params['start_beat']
            return {"started_monotonic": self.started, "tempo": self.tempo, "signature": [4, 4]}
        if method == "capture_end":
            self.restored = True
            end_time = time.monotonic()
            origin = self.requested_start if self.played_start_beat is None else self.played_start_beat
            return {"restored": True, "end_tempo": self.tempo, "end_signature": [4, 4],
                    "end_monotonic": end_time, "end_beat": origin + (end_time - self.started) * self.tempo / 60,
                    **self.end_overrides}
        raise AssertionError(method)


class PlayheadValidationTests(unittest.TestCase):
    def validate(self, *, start=16, duration=6.4, tempo=150, elapsed=6.4, offset=0, **fields):
        started = {'started_monotonic': 100}
        restored = {'end_monotonic': 100 + elapsed,
                    'end_beat': start + elapsed * tempo / 60 + offset, **fields}
        return _validate_playhead(started, restored, start_beat=start, duration=duration, tempo=tempo)

    def test_accepts_requested_range_and_small_transport_jitter(self):
        for start in (0, 16, 64, 80):
            for offset in (-0.1, 0, 0.1):
                with self.subTest(start=start, offset=offset):
                    result = self.validate(start=start, offset=offset)
                    self.assertAlmostEqual(result['end_beat'], start + 16 + offset)
                    self.assertEqual(result['tolerance_beats'], 0.5)

    def test_uses_live_elapsed_time_not_just_requested_duration(self):
        # Latency compensation, recorder shutdown and queued capture_end add time.
        result = self.validate(elapsed=7.7)
        self.assertAlmostEqual(result['expected_end_beat'], 35.25)
        # Stale endpoint at the requested end still fails if Live should be farther on.
        with self.assertRaisesRegex(AudioError, 'playhead'):
            self.validate(elapsed=7.7, end_beat=32)

    def test_rejects_the_reported_bar_one_mislabels(self):
        for start in (16, 64, 80):  # bars 5, 17, 21, each a four-bar preview at 150 BPM
            with self.subTest(start=start), self.assertRaisesRegex(AudioError, 'playhead'):
                self.validate(start=start, offset=-start)

    def test_rejects_reported_cached_stop_position_at_85_bpm(self):
        with self.assertRaisesRegex(AudioError, 'ended at beat 49.873'):
            self.validate(start=8, duration=8 * 60 / 85, tempo=85, elapsed=6.966, end_beat=49.873)

    def test_rejects_forward_jump_stopped_or_incomplete_playback(self):
        for args in ({'offset': 4}, {'offset': -4}, {'end_beat': 16},
                     {'elapsed': 0}, {'elapsed': -1}, {'elapsed': 3}):
            with self.subTest(args=args), self.assertRaisesRegex(AudioError, 'playhead'):
                self.validate(**args)

    def test_endpoint_requires_finite_timing_and_position(self):
        for field in ('end_monotonic', 'end_beat'):
            for value in (None, True, '32', float('nan'), float('inf')):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(AudioError, 'endpoint timing'):
                    self.validate(**{field: value})
        with self.assertRaisesRegex(AudioError, 'update OctetBridge'):
            _validate_playhead({'started_monotonic': 100}, {'end_beat': 32},
                               start_beat=16, duration=6.4, tempo=150)

    def test_tolerance_scales_with_tempo_but_cannot_hide_one_beat(self):
        for tempo in (20, 120, 999):
            with self.subTest(tempo=tempo):
                result = self.validate(tempo=tempo)
                self.assertAlmostEqual(result['tolerance_beats'], min(0.5, tempo / 240))
                with self.assertRaisesRegex(AudioError, 'playhead'):
                    self.validate(tempo=tempo, offset=-1)


class SyntheticRecorder(CaptureRecorder):
    def _command(self, index):
        return ["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-n", "-re",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", str(self.max_seconds), "-ac", "2", "-c:a", "pcm_f32le", "-f", "f32le",
                "-flush_packets", "1", str(self.raw_path)]


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class LiveListenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.bridge = Bridge()

    def run_listen(self, cancel=lambda: None, start_bar=2, length_bars=0.125):
        with patch("octet_ableton.live_audio.discover_devices", return_value=[{"name": "BlackHole 2ch", "index": 1}]):
            return listen_live({"slices": [{"start_bar": start_bar, "end_bar": start_bar + length_bars}]},
                               bridge=self.bridge, scratch=self.path,
                               check_cancel=cancel, recorder_class=SyntheticRecorder)

    def test_synthetic_closed_loop_and_timeline_coordinates(self):
        result = self.run_listen()
        self.assertTrue(self.bridge.restored)
        self.assertEqual(result["source"], "live")
        self.assertEqual(self.bridge.calls[0], "lom")
        self.assertNotIn("snapshot", self.bridge.calls)
        self.assertNotIn("session", result)
        clip = result["slices"][0]
        self.assertEqual(clip["telemetry"]["grid"]["start_position"]["bar"], 2)
        self.assertGreater(clip["telemetry"]["peak_dbfs"], -30)
        self.assertTrue(Path(clip["path"]).is_file())
        self.assertFalse(list(self.path.glob("capture-*")))
        self.assertIn("uncalibrated", clip["capture"]["alignment"])
        self.assertAlmostEqual(clip['capture']['playback']['end_beat'],
                               clip['capture']['playback']['expected_end_beat'])

    def test_two_bar_85_bpm_capture_exports_all_271059_frames(self):
        self.bridge = Bridge(tempo=85)
        result = self.run_listen(start_bar=3, length_bars=2)
        clip = result['slices'][0]
        self.assertTrue(self.bridge.restored)
        self.assertEqual(clip['telemetry']['grid']['start_position']['bar'], 3)
        self.assertAlmostEqual(clip['end_sec'] - clip['start_sec'], 271059 / 48000)
        self.assertEqual(clip['telemetry']['duration_sec'], round(271059 / 48000, 6))
        self.assertTrue(Path(clip['path']).is_file())
        self.assertFalse(list(self.path.glob('capture-*')))

    def test_wrong_region_restores_and_rejects_before_creating_preview(self):
        for start in (5, 17, 21):
            self.bridge = Bridge(played_start_beat=0)
            with self.subTest(start=start), patch('octet_ableton.live_listen.listen_file') as encode:
                with self.assertRaisesRegex(AudioError, 'playhead'):
                    self.run_listen(start_bar=start)
                self.assertTrue(self.bridge.restored)
                self.assertEqual(self.bridge.calls, ['lom', 'capture_begin', 'capture_end'])
                encode.assert_not_called()
                self.assertFalse(list(self.path.iterdir()))

    def test_changed_tempo_still_rejects_and_cleans(self):
        self.bridge = Bridge(end_overrides={'end_tempo': 121})
        with self.assertRaisesRegex(AudioError, 'Tempo/meter changed'):
            self.run_listen()
        self.assertTrue(self.bridge.restored)
        self.assertFalse(list(self.path.iterdir()))

    def test_cancellation_after_start_restores_and_cleans(self):
        def cancel():
            if "capture_begin" in self.bridge.calls:
                raise InterruptedError("cancelled")
        with self.assertRaisesRegex(InterruptedError, "cancelled"):
            self.run_listen(cancel)
        self.assertTrue(self.bridge.restored)
        self.assertFalse(list(self.path.iterdir()))

    def test_too_long_and_file_timing_rejected(self):
        for args in ({"tempo": 99, "slices": []}, {"slices": [{"start_bar": 1, "end_bar": 10}]}):
            with self.assertRaises(AudioError):
                listen_live(args, bridge=self.bridge, scratch=self.path, check_cancel=lambda: None)
        self.assertNotIn("capture_begin", self.bridge.calls)
