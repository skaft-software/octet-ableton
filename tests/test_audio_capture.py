import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from octet_ableton.audio_capture import AudioError, _run, _validate, listen_file


RATE = 48000


def noop():
    pass


def make_wav(path, seconds=2, stereo=False, silent=False):
    samples = np.zeros(round(seconds * RATE)) if silent else (
        0.5 * np.sin(2 * np.pi * 440 * np.arange(round(seconds * RATE)) / RATE))
    if stereo:
        samples = np.column_stack((samples, -samples))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2 if stereo else 1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((samples * 32767).astype("<i2").tobytes())


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.wav"
        self.source.write_bytes(b"validation does not decode")
        self.arguments = {"file_path": str(self.source), "slices": [{"start_sec": 0, "end_sec": 1}]}

    def test_invalid_ranges_and_caps(self):
        invalid = [[], [{}], [None], [{"start_sec": 0}],
                   [{"start_sec": 0, "end_sec": 1, "start_bar": 1}],
                   [{"start_sec": -1, "end_sec": 1}],
                   [{"start_sec": 1, "end_sec": 1}],
                   [{"start_sec": 0, "end_sec": 8.0001}],
                   [{"start_sec": 0, "end_sec": 1e-9}],
                   [{"start_sec": True, "end_sec": 1}],
                   [{"start_sec": 0, "end_sec": float("inf")}],
                   [{"start_sec": 0, "end_sec": 1, "solo_tracks": [1]}],
                   [{"start_bar": 1, "end_bar": 2}],
                   self.arguments["slices"] * 5]
        for ranges in invalid:
            with self.subTest(ranges=ranges), self.assertRaises(AudioError):
                _validate({**self.arguments, "slices": ranges})
        for path in ("relative.wav", "https://example.test/a.wav", str(self.source.parent),
                     str(self.source.parent / "missing.wav")):
            with self.subTest(path=path), self.assertRaises(AudioError):
                _validate({**self.arguments, "file_path": path})

    def test_negative_origin_is_rejected(self):
        with self.assertRaisesRegex(AudioError, "origin_sec"):
            _validate({**self.arguments, "origin_sec": -1})

    def test_bar_cap_and_duration_cap_are_independent(self):
        for tempo, start, end in ((999, 1, 10), (120, 1, 6)):
            with self.assertRaises(AudioError):
                _validate({**self.arguments, "tempo": tempo,
                           "slices": [{"start_bar": start, "end_bar": end}]})
        _, slices, _, _, _ = _validate({**self.arguments, "tempo": 120, "signature": [6, 8],
                                       "slices": [{"start_bar": 1.5, "end_bar": 2.5}]})
        self.assertEqual(slices[0]["start_sec"], 0.75)
        self.assertEqual(slices[0]["end_sec"], 2.25)

    def test_subprocess_timeout_and_output_cap(self):
        with self.assertRaisesRegex(AudioError, "timed out"):
            _run([sys.executable, "-c", "import time; time.sleep(10)"], check_cancel=noop, timeout=0.1)
        with self.assertRaisesRegex(AudioError, "output limit"):
            _run([sys.executable, "-c", "print('x' * 100000)"], check_cancel=noop)

    def test_subprocess_cancel_reaps_child(self):
        pidfile = self.source.parent / "pid"

        def cancel():
            if pidfile.exists():
                raise InterruptedError("cancelled")

        before = time.monotonic()
        with self.assertRaises(InterruptedError):
            _run([sys.executable, "-c",
                  "import os,time,pathlib; pathlib.Path(__import__('sys').argv[1]).write_text(str(os.getpid())); time.sleep(10)",
                  str(pidfile)], check_cancel=cancel)
        self.assertLess(time.monotonic() - before, 3)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
class FileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source with spaces.wav"
        self.scratch = self.root / "scratch"
        make_wav(self.source, stereo=True)
        self.arguments = {"file_path": str(self.source), "slices": [{"start_sec": 0.25, "end_sec": 1.25}]}

    def listen(self, arguments=None, check_cancel=noop):
        return listen_file(arguments or self.arguments, scratch=self.scratch, check_cancel=check_cancel)

    def test_pcm_analysis_precedes_encoding_and_paths_are_private(self):
        original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = self.listen({**self.arguments, "slices": [
            {"label": "../../do-not-use-as-path", "start_sec": 0.25, "end_sec": 1.25},
            {"label": "../../do-not-use-as-path", "start_sec": 1.25, "end_sec": 1.75},
        ]})
        self.assertEqual(len(set(result["slice_paths"])), 2)
        for item in result["slices"]:
            path = Path(item["path"])
            self.assertTrue(path.is_file())
            self.assertTrue(path.is_relative_to(self.scratch.resolve()))
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertLess(path.stat().st_size, 110 * 1024)
            self.assertAlmostEqual(item["telemetry"]["peak_dbfs"], -6.021, delta=0.01)
            self.assertAlmostEqual(item["telemetry"]["rms_dbfs"], -9.031, delta=0.01)
            self.assertEqual(item["telemetry"]["channels"], 2)
            self.assertIsNone(item["telemetry"]["grid"])
            self.assertIn("phase_cancellation_fallback", item["preview_mix"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), original)
        self.assertEqual(len(list(self.scratch.rglob("*.f32"))), 0)
        json.dumps(result, allow_nan=False)
        # Repeated calls never overwrite the first call's audio.
        second = self.listen()
        self.assertTrue(set(result["slice_paths"]).isdisjoint(second["slice_paths"]))

    def test_eight_second_size_cap_and_silent_json(self):
        make_wav(self.source, seconds=8, silent=True)
        result = self.listen({**self.arguments, "slices": [{"start_sec": 0, "end_sec": 8}]})
        self.assertLessEqual(result["slices"][0]["bytes"], 110 * 1024)
        self.assertIsNone(result["slices"][0]["telemetry"]["peak_dbfs"])
        json.dumps(result, allow_nan=False)

    def test_bar_mode_compound_meter_and_mp3_input(self):
        result = self.listen({**self.arguments, "tempo": 120, "signature": [6, 8],
                              "slices": [{"start_bar": 1.25, "end_bar": 2}]})
        self.assertEqual(result["slices"][0]["start_sec"], 0.375)
        self.assertEqual(result["slices"][0]["telemetry"]["grid"]["quarter_beats_per_bar"], 3)
        result = self.listen({"file_path": result["slice_paths"][0],
                              "slices": [{"start_sec": 0.125, "end_sec": 0.625}]})
        self.assertEqual(result["slices"][0]["telemetry"]["duration_sec"], 0.5)

    def test_full_frame_quantized_window_at_85_bpm(self):
        frames = round(8 * 60 / 85 * RATE)
        self.assertEqual(frames, 271059)
        duration = frames / RATE  # 5.6470625; ffprobe reports 5.647062.
        make_wav(self.source, seconds=duration, stereo=True)
        result = self.listen({**self.arguments, 'slices': [{'start_sec': 0, 'end_sec': duration}]})
        self.assertEqual(result['slices'][0]['telemetry']['duration_sec'], round(duration, 6))
        self.assertEqual(result['slices'][0]['end_sec'], duration)
        self.assertTrue(Path(result['slice_paths'][0]).is_file())

    def test_one_sample_metadata_tolerance_does_not_allow_truncated_audio(self):
        # A one-frame overrun passes metadata tolerance but must fail decoded coverage.
        with self.assertRaisesRegex(AudioError, 'refusing a truncated slice'):
            self.listen({**self.arguments, 'slices': [{'start_sec': 1, 'end_sec': 2 + 1 / RATE}]})
        self.assertEqual(list(self.scratch.iterdir()), [])
        with self.assertRaisesRegex(AudioError, 'beyond file duration'):
            self.listen({**self.arguments, 'slices': [{'start_sec': 1, 'end_sec': 2 + 2 / RATE}]})

    def test_eof_and_bad_media_are_expected_errors(self):
        with self.assertRaisesRegex(AudioError, "beyond file duration"):
            self.listen({**self.arguments, "slices": [{"start_sec": 1, "end_sec": 2.1}]})
        self.source.write_text("not audio")
        with self.assertRaises(AudioError):
            self.listen()
        self.assertFalse(self.scratch.exists())

    def test_cancellation_and_encoding_failure_clean_all_call_artifacts(self):
        from octet_ableton import audio_capture
        original_run = audio_capture._run
        calls = 0

        def fail_encoding(command, **kwargs):
            nonlocal calls
            calls += 1
            if "libmp3lame" in command:
                raise AudioError("encoder unavailable")
            return original_run(command, **kwargs)

        with patch.object(audio_capture, "_run", side_effect=fail_encoding):
            with self.assertRaisesRegex(AudioError, "encoder unavailable"):
                self.listen()
        self.assertGreaterEqual(calls, 3)
        self.assertEqual(list(self.scratch.iterdir()), [])

        def cancel_after_decode():
            if self.scratch.exists() and list(self.scratch.rglob("*.f32")):
                raise InterruptedError("cancelled")

        with self.assertRaises(InterruptedError):
            self.listen(check_cancel=cancel_after_decode)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertTrue(self.source.exists())


if __name__ == "__main__":
    unittest.main()
