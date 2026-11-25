import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from remote_script.OctetBridge.capture_control import CaptureControl
from remote_script.OctetBridge.server import BridgeError


class Song:
    def __init__(self):
        self.tracks = [SimpleNamespace(solo=True), SimpleNamespace(solo=False)]
        self.is_playing = True
        self.current_song_time = 12
        self.start_time = 0  # Arrangement Insert Marker, independent of playhead.
        self.last_stopped_time = 40.013  # Stopped seeks do not update Live's resume position.
        self.loop = True
        self.tempo = 120
        self.signature_numerator = 4
        self.signature_denominator = 4
        self.record_mode = False

    def stop_playing(self):
        if self.is_playing:
            self.last_stopped_time = self.current_song_time
        self.is_playing = False

    def start_playing(self):
        self.current_song_time = self.start_time
        self.is_playing = True

    def continue_playing(self):
        if not self.is_playing:
            self.current_song_time = self.last_stopped_time
        self.is_playing = True


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.song = Song()
        self.capture = CaptureControl(self.song)
        self.args = {"capture_id": str(uuid.uuid4()), "start_beat": 24,
                     "duration_sec": 2, "solo_tracks": [1]}

    def test_begin_end_restore_and_repeat_end(self):
        self.capture.handle("capture_begin", self.args)
        self.assertEqual([t.solo for t in self.song.tracks], [False, True])
        self.assertFalse(self.song.loop)
        self.assertEqual(self.song.current_song_time, 24)
        result = self.capture.handle("capture_end", {"capture_id": self.args["capture_id"]})
        self.assertTrue(result["restored"])
        self.assertEqual([t.solo for t in self.song.tracks], [True, False])
        self.assertTrue(self.song.loop)
        self.assertTrue(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 12)
        self.assertEqual(result, self.capture.handle("capture_end", {"capture_id": self.args["capture_id"]}))

    def test_requested_position_from_stopped_and_playing_transport(self):
        for playing in (False, True):
            with self.subTest(playing=playing):
                self.song = Song()
                self.capture = CaptureControl(self.song)
                self.song.is_playing = playing
                self.capture.begin(self.args)
                self.assertTrue(self.song.is_playing)
                self.assertEqual(self.song.current_song_time, 24)
                self.assertEqual(self.song.start_time, 0)
                self.capture.restore()
                self.assertEqual(self.song.is_playing, playing)
                self.assertEqual(self.song.current_song_time, 12)
                self.assertEqual(self.song.start_time, 0)

    def test_reported_85_bpm_capture_ignores_cached_stopped_position(self):
        self.song.is_playing = False
        self.song.current_song_time = 40.013
        self.song.tempo = 85
        self.capture.begin({**self.args, 'start_beat': 8, 'duration_sec': 8 * 60 / 85})
        self.assertTrue(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 8)
        self.assertEqual(self.song.start_time, 0)
        self.song.current_song_time = 16
        result = self.capture.restore()
        self.assertEqual(result['end_beat'], 16)
        self.assertFalse(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 40.013)
        self.assertEqual(self.song.start_time, 0)

    def test_restore_resumes_saved_playhead_and_reports_capture_endpoint(self):
        self.capture.begin(self.args)
        self.song.current_song_time = 28
        with patch('remote_script.OctetBridge.capture_control.time.monotonic', return_value=123):
            result = self.capture.restore()
        self.assertTrue(result['restored'])
        self.assertEqual(result['end_beat'], 28)
        self.assertEqual(result['end_monotonic'], 123)
        self.assertEqual(self.song.current_song_time, 12)
        self.assertTrue(self.song.is_playing)

    def test_same_tick_continue_noop_does_not_leave_transport_stopped(self):
        self.song.current_song_time = 20.8704
        self.capture.begin(self.args)
        with patch.object(self.song, 'continue_playing', return_value=None):
            result = self.capture.restore()
        self.assertTrue(result['restored'])
        self.assertTrue(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 20.8704)

    def test_stopped_restore_accepts_next_tick_stop(self):
        self.song.is_playing = False
        self.capture.begin(self.args)
        next_tick = []
        stop = self.song.stop_playing
        with patch.object(self.song, 'stop_playing', side_effect=lambda: next_tick.append(stop)):
            result = self.capture.restore()
        self.assertTrue(self.song.is_playing)  # Live's transport engine hasn't processed Stop yet.
        self.assertTrue(result['restored'], result['restore_errors'])
        self.assertEqual(next_tick, [stop])
        next_tick[0]()
        self.assertFalse(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 12)
        self.assertTrue(self.song.loop)
        self.assertEqual([t.solo for t in self.song.tracks], [True, False])

    def test_stopped_restore_reports_stop_exception(self):
        self.song.is_playing = False
        self.capture.begin(self.args)
        with patch.object(self.song, 'stop_playing', side_effect=RuntimeError('stop failed')):
            result = self.capture.restore()
        self.assertFalse(result['restored'])
        self.assertIn('stop_playing', result['restore_errors'])

    def test_silent_play_failure_is_not_reported_as_restored(self):
        self.capture.begin(self.args)
        with patch.object(self.song, 'start_playing', return_value=None):
            result = self.capture.restore()
        self.assertFalse(result['restored'])
        self.assertIn('is_playing', result['restore_errors'])
        self.assertEqual(self.song.current_song_time, 12)
        self.assertTrue(self.song.loop)
        self.assertEqual([t.solo for t in self.song.tracks], [True, False])
        self.assertEqual(result, self.capture.handle('capture_end', {'capture_id': self.args['capture_id']}))

    def test_failed_begin_restores_original_playhead_and_solos(self):
        start = self.song.start_playing

        def fail_after_start():
            start()
            raise RuntimeError('failed after starting')

        with patch.object(self.song, 'start_playing', side_effect=fail_after_start):
            with self.assertRaisesRegex(RuntimeError, 'failed after starting'):
                self.capture.begin(self.args)
        self.assertIsNone(self.capture.active)
        self.assertEqual(self.song.current_song_time, 12)
        self.assertTrue(self.song.is_playing)
        self.assertTrue(self.song.loop)
        self.assertEqual([t.solo for t in self.song.tracks], [True, False])

    def test_guard_restores_when_client_disappears(self):
        self.capture.begin(self.args)
        self.capture.active["deadline"] = time.monotonic() - 1
        self.capture.tick()
        self.assertIsNone(self.capture.active)
        self.assertEqual(self.song.current_song_time, 12)

    def test_invalid_recording_or_busy_do_not_mutate(self):
        for invalid in ({"duration_sec": 9}, {"solo_tracks": [-1]}, {"start_beat": float('nan')}):
            with self.assertRaises(BridgeError):
                self.capture.begin({**self.args, **invalid})
            self.assertIsNone(self.capture.active)
        self.song.record_mode = True
        with self.assertRaises(BridgeError):
            self.capture.begin(self.args)
        self.song.record_mode = False
        self.capture.begin(self.args)
        with self.assertRaises(BridgeError):
            self.capture.begin(self.args)
        with self.assertRaises(BridgeError):
            self.capture.handle("capture_end", {"capture_id": str(uuid.uuid4())})
        self.capture.restore()
