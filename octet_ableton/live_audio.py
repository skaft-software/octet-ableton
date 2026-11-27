"""Bounded AVFoundation / DirectShow loopback capture. No device routing or installation is changed.

Use ``with CaptureRecorder(scratch=...) as recorder:`` then start(check_cancel),
wait_frames(target, check_cancel), finish(check_cancel) -> float WAV Path.
All private recordings disappear on close; consume/copy them inside the context.
Frame positions count captured PCM, NOT sample-accurate Live transport positions.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from .audio_capture import AudioError, PROCESS_OUTPUT_LIMIT, SAMPLE_RATE

MAC_DEVICE = "BlackHole 2ch"
WINDOWS_DEVICE = "CABLE Output (VB-Audio Virtual Cable)"
INPUT_FORMAT = "dshow" if sys.platform == "win32" else "avfoundation"
DEFAULT_DEVICE = WINDOWS_DEVICE if INPUT_FORMAT == "dshow" else MAC_DEVICE
MAX_CAPTURE_SECONDS = 14
FRAME_BYTES = 8  # stereo float32


def _spawn(command: list[str]) -> subprocess.Popen:
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError as exc:
        raise AudioError(f"Cannot start {command[0]}: {exc}") from exc
    if os.name != "nt":
        os.set_blocking(process.stderr.fileno(), False)
    return process


def _diagnostics(process: subprocess.Popen, buffer: bytearray) -> str:
    while True:
        size = min(4096, PROCESS_OUTPUT_LIMIT + 1 - len(buffer))
        if os.name == "nt":
            # Python 3.11 cannot set Windows pipes nonblocking. Only read bytes
            # already in the anonymous pipe so cancellation/deadlines still run.
            import msvcrt
            import win32pipe
            import pywintypes
            try:
                _, available, _ = win32pipe.PeekNamedPipe(msvcrt.get_osfhandle(process.stderr.fileno()), 1)
            except pywintypes.error as exc:
                if exc.winerror == 109:  # ERROR_BROKEN_PIPE: writer closed
                    break
                raise AudioError(f"Cannot read FFmpeg diagnostics: {exc}") from exc
            if not available:
                break
            size = min(size, available)
        try:
            chunk = os.read(process.stderr.fileno(), size)
        except BlockingIOError:
            break
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > PROCESS_OUTPUT_LIMIT:
            raise AudioError("ffmpeg exceeded its diagnostic output limit")
    return buffer.decode("utf-8", "replace")


def _stop(process: subprocess.Popen | None) -> None:
    if process is not None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        process.stderr.close()


def discover_devices(check_cancel: Callable[[], None], *, ffmpeg: str = "ffmpeg") -> list[dict]:
    """Enumerate audio inputs without recording; only flag the exact loopback default."""
    check_cancel()
    process = _spawn([ffmpeg, "-nostdin", "-hide_banner", "-f", INPUT_FORMAT,
                      "-list_devices", "true", "-i", "dummy" if INPUT_FORMAT == "dshow" else ""])
    diagnostics = bytearray()
    deadline = time.monotonic() + 5
    try:
        while True:
            check_cancel()
            text = _diagnostics(process, diagnostics)
            if process.poll() is not None:
                text = _diagnostics(process, diagnostics)
                break
            if time.monotonic() >= deadline:
                raise AudioError("Audio device discovery timed out")
            time.sleep(0.02)
        check_cancel()
        if INPUT_FORMAT == "dshow":
            # FFmpeg 6+ prints one typed row per endpoint, followed by its
            # alternative ID. Neither that ID nor a video-only row is an input name.
            rows = re.findall(r'^\[dshow @ [^\]]+\] "([^"\r\n]+)" \(([^)]+)\)\r?$', text, re.M)
            if (process.returncode not in (0, 1) or
                    (not rows and "Could not enumerate audio only devices (or none found)" not in text)):
                raise AudioError(f"Cannot discover DirectShow audio devices (use FFmpeg 6+ with dshow): {text[-1200:]}")
            return [{"name": name, "is_default": name == WINDOWS_DEVICE} for name, types in rows
                    if "audio" in types.split(", ")]
        # Older ffmpeg exits 1; ffmpeg 7.1 returns AVERROR(EIO) modulo 256 (251).
        if process.returncode not in (0, 1, 251) or "AVFoundation audio devices:" not in text:
            raise AudioError(f"Cannot discover AVFoundation audio devices: {text[-1200:]}")
        audio = text.split("AVFoundation audio devices:", 1)[1]
        devices = []
        for index, name in re.findall(r"^\[[^\n]+?\]\s+\[(\d+)\]\s+([^\r\n]+)", audio, re.M):
            devices.append({"index": int(index), "name": name,
                            "is_default": name == MAC_DEVICE})
        check_cancel()
        return devices
    finally:
        _stop(process)


class CaptureRecorder:
    """Single-use private stereo/48k capture, capped at 14 seconds.

    start returns only after complete PCM frames exist. started_at / ready_at are
    monotonic observations, not hardware timestamps. frames_written advances in
    device/ffmpeg chunks; buffering and device latency are uncalibrated.
    finish stops/reaps ffmpeg and returns a float WAV without clipping >0 dBFS.
    export_window uses exact, end-exclusive captured sample indices after finish.
    """
    sample_rate = SAMPLE_RATE
    channels = 2
    timing_uncertainty = "Uncalibrated device/ffmpeg buffering; not sample-accurate Live alignment"

    def __init__(self, *, scratch: Path, device: str = DEFAULT_DEVICE,
                 max_seconds: float = 12, startup_timeout: float = 4,
                 ffmpeg: str = "ffmpeg"):
        if (isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float))
                or not math.isfinite(max_seconds) or not 1 / SAMPLE_RATE <= max_seconds <= MAX_CAPTURE_SECONDS):
            raise AudioError("capture max_seconds must be finite and between one sample and 14 seconds")
        if (isinstance(startup_timeout, bool) or not isinstance(startup_timeout, (int, float))
                or not math.isfinite(startup_timeout) or not 0 < startup_timeout <= 10):
            raise AudioError("startup_timeout must be finite and between 0 and 10 seconds")
        if not isinstance(device, str) or not device or "\x00" in device:
            raise AudioError("device must be an exact audio device name")
        self.scratch, self.device, self.ffmpeg = Path(scratch), device, ffmpeg
        self.max_frames = int(max_seconds * SAMPLE_RATE)
        self.max_seconds, self.startup_timeout = self.max_frames / SAMPLE_RATE, startup_timeout
        self.process = None
        self.directory = self.raw_path = None
        self.started_at = self.ready_at = None
        self.frames = 0
        self._stderr = bytearray()

    def __enter__(self):
        self.scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="capture-", dir=self.scratch)).resolve()
        self.raw_path = self.directory / "capture.f32"
        return self

    def __exit__(self, *_):
        self.close()

    def _command(self, device: dict) -> list[str]:
        if INPUT_FORMAT == "dshow":
            # ':' separates additional inputs in DirectShow's URL grammar.
            if ":" in device["name"]:
                raise AudioError("Rename the loopback endpoint without ':' for DirectShow capture.")
            source = ["-f", "dshow", "-audio_buffer_size", "50", "-i", "audio=" + device["name"]]
        else:
            source = ["-f", "avfoundation", "-i", f":{device['index']}"]
        return [self.ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-n",
                "-protocol_whitelist", "file", *source,
                "-map", "0:a:0", "-vn", "-sn", "-dn", "-threads", "1",
                "-t", f"{self.max_seconds:.12f}", "-ar", str(SAMPLE_RATE), "-ac", "2",
                "-c:a", "pcm_f32le", "-f", "f32le", "-flush_packets", "1",
                "-fs", str(self.max_frames * FRAME_BYTES), str(self.raw_path)]

    def start(self, check_cancel: Callable[[], None]) -> None:
        try:
            check_cancel()
            matches = [item for item in discover_devices(check_cancel, ffmpeg=self.ffmpeg)
                       if item["name"] == self.device]
            if len(matches) != 1:
                raise AudioError(f"Audio device {self.device!r} not uniquely available; check /ableton devices for the exact loopback name; no microphone fallback")
            self.started_at = time.monotonic()
            self.process = _spawn(self._command(matches[0]))
            while True:
                check_cancel()
                if self.frames_written() > 0:
                    self.ready_at = time.monotonic()
                    return
                if self.process.poll() is not None:
                    raise AudioError("ffmpeg capture ended without audio frames")
                if time.monotonic() - self.started_at >= self.startup_timeout:
                    raise AudioError("ffmpeg capture startup timed out waiting for PCM frames")
                time.sleep(0.01)
        except BaseException:
            self.close()
            raise

    def frames_written(self) -> int:
        try:
            if self.process is not None:
                text = _diagnostics(self.process, self._stderr)
                code = self.process.poll()
                if code not in (None, 0):
                    text = _diagnostics(self.process, self._stderr)
                    raise AudioError(f"ffmpeg capture failed: {text[-1200:].strip()}")
                if code is None and time.monotonic() > self.started_at + self.startup_timeout + self.max_seconds + 2:
                    raise AudioError("ffmpeg capture timed out")
            size = self.raw_path.stat().st_size if self.raw_path.exists() else 0
            if size > self.max_frames * FRAME_BYTES:
                raise AudioError("ffmpeg exceeded its audio output limit")
            self.frames = size // FRAME_BYTES
            return self.frames
        except BaseException:
            self.close()
            raise

    def wait_frames(self, target: int, check_cancel: Callable[[], None]) -> int:
        try:
            if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target <= self.max_frames:
                raise AudioError("target must be a captured frame index within the duration cap")
            while True:
                check_cancel()
                frames = self.frames_written()
                if frames >= target:
                    return frames
                if self.process.poll() is not None:
                    raise AudioError("ffmpeg capture ended before the requested frames")
                time.sleep(0.01)
        except BaseException:
            self.close()
            raise

    def finish(self, check_cancel: Callable[[], None]) -> Path:
        try:
            check_cancel()
            self.frames_written()
            _stop(self.process)
            self.process = None
            frames = self.frames_written()
            if not frames:
                raise AudioError("Capture contains no audio frames")
            return self.export_window(0, frames, self.directory / "capture.wav", check_cancel=check_cancel)
        except BaseException:
            self.close()
            raise

    def export_window(self, start_frame: int, frame_count: int, wav_path: Path,
                      *, check_cancel: Callable[[], None] = lambda: None) -> Path:
        """Write an IEEE-float WAV, preserving exact frames and unclipped samples."""
        check_cancel()
        if (any(isinstance(n, bool) or not isinstance(n, int) for n in (start_frame, frame_count))
                or start_frame < 0 or frame_count <= 0 or start_frame + frame_count > self.frames_written()):
            raise AudioError("WAV window must be an exact available captured frame range")
        with self.raw_path.open("rb") as source:
            source.seek(start_frame * FRAME_BYTES)
            data = source.read(frame_count * FRAME_BYTES)
        header = struct.pack("<4sI4s4sIHHIIHHH4sII4sI", b"RIFF", 50 + len(data), b"WAVE",
                             b"fmt ", 18, 3, 2, SAMPLE_RATE, SAMPLE_RATE * FRAME_BYTES,
                             FRAME_BYTES, 32, 0, b"fact", 4, frame_count, b"data", len(data))
        wav_path = Path(wav_path)
        output = wav_path.open("xb")
        try:
            with output:
                output.write(header)
                output.write(data)
                check_cancel()
        except BaseException:
            wav_path.unlink(missing_ok=True)
            raise
        return wav_path

    def close(self) -> None:
        _stop(self.process)
        self.process = None
        if self.directory is not None:
            shutil.rmtree(self.directory, ignore_errors=True)

    abort = close
