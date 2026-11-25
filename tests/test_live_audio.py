import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from octet_ableton import live_audio
from octet_ableton.audio_capture import AudioError, listen_file
from octet_ableton.live_audio import CaptureRecorder, SAMPLE_RATE, discover_devices


def noop():
    pass


DEVICES = [{"index": 1, "name": "BlackHole 2ch", "is_default": True}]
DEVICE_TEXT = """[AVFoundation indev @ 0x1] AVFoundation video devices:
[AVFoundation indev @ 0x1] [0] Camera
[AVFoundation indev @ 0x1] AVFoundation audio devices:
[AVFoundation indev @ 0x1] [0] MacBook Microphone
[AVFoundation indev @ 0x1] [1] BlackHole 2ch
Error opening input files: Input/output error
"""


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def discovery(self, code, check_cancel=noop):
        spawn = live_audio._spawn
        with patch.object(live_audio, "_spawn", side_effect=lambda _: spawn([sys.executable, "-c", code])):
            return discover_devices(check_cancel)

    def test_discovery_expected_nonzero_and_audio_only(self):
        for code in (1, 251):
            result = self.discovery(f"import sys; sys.stderr.write({DEVICE_TEXT!r}); sys.exit({code})")
            self.assertEqual(result, [
                {"index": 0, "name": "MacBook Microphone", "is_default": False}, DEVICES[0],
            ])
        self.assertEqual(self.discovery("import sys; sys.stderr.write('AVFoundation audio devices:\\n'); sys.exit(1)"), [])

    def test_discovery_unavailable_and_bounded_diagnostics(self):
        with self.assertRaisesRegex(AudioError, "Cannot discover"):
            self.discovery("import sys; sys.stderr.write('Unknown input format'); sys.exit(1)")
        with self.assertRaisesRegex(AudioError, "diagnostic output limit"):
            self.discovery("import sys; sys.stderr.write('x' * 1000000)")
        with self.assertRaisesRegex(AudioError, "Cannot start"):
            discover_devices(noop, ffmpeg=str(self.root / "missing-binary"))

    def test_no_microphone_fallback_even_if_only_device(self):
        with patch.object(live_audio, "discover_devices", return_value=[{"index": 0, "name": "Microphone"}]), \
                patch.object(live_audio, "_spawn") as spawn, \
                CaptureRecorder(scratch=self.root) as recorder:
            with self.assertRaisesRegex(AudioError, "no microphone fallback"):
                recorder.start(noop)
            spawn.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_exact_selection_and_finite_local_command(self):
        with CaptureRecorder(scratch=self.root, max_seconds=14) as recorder:
            command = recorder._command(1)
            self.assertEqual(command[command.index("-i") + 1], ":1")
            self.assertIn("file", command)
            self.assertIn("f32le", command)
            self.assertEqual(command[command.index("-fs") + 1], str(14 * SAMPLE_RATE * 8))
        for value in (0, True, float("nan"), float("inf"), 14.001, "8"):
            with self.subTest(value=value), self.assertRaises(AudioError):
                CaptureRecorder(scratch=self.root, max_seconds=value)

    def run_fake(self, code, *, startup_timeout=1, max_seconds=1):
        recorder = CaptureRecorder(scratch=self.root, startup_timeout=startup_timeout, max_seconds=max_seconds)
        recorder.__enter__()
        self.addCleanup(recorder.close)
        command = [sys.executable, "-c", code, str(recorder.raw_path)]
        self.addCleanup(patch.stopall)
        patch.object(live_audio, "discover_devices", return_value=DEVICES).start()
        patch.object(recorder, "_command", return_value=command).start()
        return recorder

    def assert_reaped(self, process):
        self.assertIsNotNone(process.returncode)
        with self.assertRaises(ProcessLookupError):
            os.kill(process.pid, 0)
        self.assertTrue(process.stderr.closed)

    def test_start_waits_for_actual_complete_frames(self):
        recorder = self.run_fake("import pathlib,sys,time; time.sleep(.12); "
                                 "pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80); time.sleep(10)")
        before = time.monotonic()
        recorder.start(noop)
        self.assertGreaterEqual(time.monotonic() - before, .1)
        self.assertEqual(recorder.frames_written(), 10)
        self.assertGreaterEqual(recorder.ready_at, recorder.started_at)
        self.assertEqual(recorder.directory.stat().st_mode & 0o777, 0o700)
        process = recorder.process
        recorder.abort()
        self.assert_reaped(process)
        self.assertFalse(recorder.directory.exists())

    def test_startup_timeout_and_failure_cleanup(self):
        for code, message in (("import time; time.sleep(10)", "startup timed out"),
                              ("import sys; sys.stderr.write('device busy'); sys.exit(2)", "device busy"),
                              ("pass", "without audio frames")):
            with self.subTest(code=code):
                recorder = self.run_fake(code, startup_timeout=.15)
                processes = []
                spawn = live_audio._spawn
                def remember(command):
                    process = spawn(command)
                    processes.append(process)
                    return process
                with patch.object(live_audio, "_spawn", side_effect=remember), self.assertRaisesRegex(AudioError, message):
                    recorder.start(noop)
                self.assert_reaped(processes[0])
                self.assertFalse(recorder.directory.exists())
                patch.stopall()

    def test_wait_cancellation_reaps_and_removes_files(self):
        recorder = self.run_fake("import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80); time.sleep(10)")
        recorder.start(noop)
        process = recorder.process
        def cancel():
            raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            recorder.wait_frames(100, cancel)
        self.assert_reaped(process)
        self.assertFalse(recorder.directory.exists())

    def test_start_cancellation_reaps(self):
        recorder = self.run_fake("import time; time.sleep(10)")
        processes = []
        def cancel():
            if recorder.process is not None:
                processes.append(recorder.process)
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            recorder.start(cancel)
        self.assert_reaped(processes[0])

    def test_abort_kills_child_that_ignores_termination(self):
        recorder = self.run_fake("import signal,pathlib,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                                 "pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80); time.sleep(10)")
        recorder.start(noop)
        process = recorder.process
        before = time.monotonic()
        recorder.abort()
        self.assertLess(time.monotonic() - before, 3)
        self.assert_reaped(process)

    def test_finish_cancel_reaps(self):
        recorder = self.run_fake("import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80); time.sleep(10)")
        recorder.start(noop)
        process = recorder.process
        def cancel():
            raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            recorder.finish(cancel)
        self.assert_reaped(process)
        self.assertFalse(recorder.directory.exists())

    def test_deadline_and_disk_limit(self):
        code = "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80); time.sleep(10)"
        recorder = self.run_fake(code)
        recorder.start(noop)
        process = recorder.process
        recorder.started_at -= 100
        with self.assertRaisesRegex(AudioError, "timed out"):
            recorder.frames_written()
        self.assert_reaped(process)
        patch.stopall()
        recorder = self.run_fake(code)
        recorder.start(noop)
        process = recorder.process
        recorder.raw_path.write_bytes(b"\0" * (recorder.max_frames * 8 + 8))
        with self.assertRaisesRegex(AudioError, "audio output limit"):
            recorder.frames_written()
        self.assert_reaped(process)

    def test_wait_rejects_early_eof(self):
        recorder = self.run_fake("import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80)")
        recorder.start(noop)
        with self.assertRaisesRegex(AudioError, "before the requested frames"):
            recorder.wait_frames(100, noop)

    def test_export_cancel_removes_partial_not_existing(self):
        recorder = self.run_fake("import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'\\0' * 80)")
        recorder.start(noop)
        recorder.finish(noop)
        output = self.root / "window.wav"
        calls = 0
        def cancel():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            recorder.export_window(0, 5, output, check_cancel=cancel)
        self.assertFalse(output.exists())
        output.write_bytes(b"keep me")
        with self.assertRaises(FileExistsError):
            recorder.export_window(0, 5, output)
        self.assertEqual(output.read_bytes(), b"keep me")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe unavailable")
class SyntheticIntegrationTests(unittest.TestCase):
    def test_real_ffmpeg_lavfi_float_wav_sample_exact_and_listenable(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(live_audio, "discover_devices", return_value=DEVICES), \
                CaptureRecorder(scratch=Path(directory), max_seconds=.5) as recorder:
            # Never opens any real audio device. Amplitude > 1 tests float preservation.
            command = recorder._command(1)
            start = command.index("-protocol_whitelist")
            end = command.index("-map")
            command[start:end] = ["-re", "-f", "lavfi", "-i",
                                  "aevalsrc=1.5*sin(2*PI*440*t)|0.5*sin(2*PI*660*t):s=48000"]
            with patch.object(recorder, "_command", return_value=command):
                recorder.start(noop)
            recorder.wait_frames(24000, noop)
            process = recorder.process
            wav = recorder.finish(noop)
            self.assertIsNotNone(process.returncode)
            self.assertEqual(recorder.frames, 24000)
            self.assertIsNone(recorder.process)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(wav)],
                                   check=True, capture_output=True, text=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "pcm_f32le")
            self.assertEqual(stream["sample_rate"], "48000")
            self.assertEqual(stream["channels"], 2)
            self.assertEqual(stream["duration_ts"], 24000)
            window = recorder.export_window(123, 10001, recorder.directory / "window.wav")
            decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(window), "-f", "f32le", "-"],
                                    check=True, capture_output=True)
            expected = np.fromfile(recorder.raw_path, dtype="<f4").reshape(-1, 2)[123:10124]
            actual = np.frombuffer(decode.stdout, dtype="<f4").reshape(-1, 2)
            np.testing.assert_array_equal(actual, expected)
            self.assertGreater(np.max(actual), 1)
            for start, count in ((-1, 10), (0, 0), (23999, 2), (True, 1), (1.5, 2)):
                with self.assertRaises(AudioError):
                    recorder.export_window(start, count, recorder.directory / "invalid.wav")
            result = listen_file({"file_path": str(wav), "slices": [{"start_sec": 0, "end_sec": .5}]},
                                 scratch=Path(directory) / "listen", check_cancel=noop)
            self.assertGreater(result["slices"][0]["telemetry"]["peak_dbfs"], 0)
            self.assertTrue(Path(result["slice_paths"][0]).is_file())


if __name__ == "__main__":
    unittest.main()
