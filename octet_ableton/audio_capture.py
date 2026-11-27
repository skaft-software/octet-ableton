"""Local-file audio slices for native listening. No Live state or device is changed.

ffmpeg/ffprobe are invoked without a shell, with local-file protocols only,
finite time/output limits, and cancellation that terminates and reaps the child.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .telemetry import MAX_SECONDS, _number, analyze_pcm, bar_to_seconds, validate_timing

SAMPLE_RATE = 48000
MAX_MP3_BYTES = 110 * 1024
PROCESS_OUTPUT_LIMIT = 64 * 1024


class AudioError(ValueError):
    """An expected input, media, or local audio-tool failure."""


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # A PATH entry may be a launcher (e.g. Chocolatey ShimGen). Stopping
        # only that PID leaves FFmpeg recording and the private PCM file locked.
        from win32api import GetSystemDirectory
        command = [str(Path(GetSystemDirectory()) / "taskkill.exe"), "/pid", str(process.pid), "/t", "/f"]
        try:
            killed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=3)
            if killed.returncode and process.poll() is None:
                raise AudioError(f"Could not stop audio process tree (taskkill exit {killed.returncode}).")
            process.wait(timeout=2)
        except subprocess.TimeoutExpired as exc:
            raise AudioError("Timed out stopping audio process tree.") from exc
    else:
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _run(
    command: list[str], *, check_cancel: Callable[[], None], timeout: float = 30,
    output: Path | None = None, max_output_bytes: int | None = None,
) -> str:
    check_cancel()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        except OSError as exc:
            raise AudioError(f"Cannot start {command[0]}: {exc}") from exc
        deadline = time.monotonic() + timeout
        try:
            while True:
                check_cancel()
                if time.monotonic() >= deadline:
                    raise AudioError(f"{command[0]} timed out after {timeout:g}s")
                if stdout.tell() > PROCESS_OUTPUT_LIMIT or stderr.tell() > PROCESS_OUTPUT_LIMIT:
                    raise AudioError(f"{command[0]} exceeded its diagnostic output limit")
                if output is not None and output.exists() and output.stat().st_size > max_output_bytes:
                    raise AudioError(f"{command[0]} exceeded its audio output limit")
                try:
                    process.wait(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    pass
            check_cancel()
            if stdout.tell() > PROCESS_OUTPUT_LIMIT or stderr.tell() > PROCESS_OUTPUT_LIMIT:
                raise AudioError(f"{command[0]} exceeded its diagnostic output limit")
            if output is not None and output.exists() and output.stat().st_size > max_output_bytes:
                raise AudioError(f"{command[0]} exceeded its audio output limit")
            stdout.seek(0)
            stderr.seek(0)
            text = stdout.read(PROCESS_OUTPUT_LIMIT).decode("utf-8", "replace")
            error = stderr.read(PROCESS_OUTPUT_LIMIT).decode("utf-8", "replace")
            if process.returncode:
                raise AudioError(f"{command[0]} failed: {error[-1200:].strip()}")
            return text
        finally:
            stop_process(process)


def _probe(path: Path, check_cancel: Callable[[], None]) -> tuple[float, int]:
    raw = _run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file", "-select_streams", "a:0",
        "-show_entries", "stream=duration,channels:format=duration", "-of", "json", str(path),
    ], check_cancel=check_cancel, timeout=10)
    try:
        data = json.loads(raw)
        stream = data["streams"][0]
        channels = int(stream["channels"])
        duration = None
        for candidate in (stream.get("duration"), data.get("format", {}).get("duration")):
            try:
                number = float(candidate)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number) and number > 0:
                duration = number
                break
        if duration is None or not 1 <= channels <= 8:
            raise ValueError("requires known positive duration and 1..8 audio channels")
        return duration, channels
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AudioError(f"Cannot determine audio duration/channels: {exc}") from exc


def _validate(arguments: dict) -> tuple[Path, list[dict], float | None, tuple[int, int], float]:
    if not isinstance(arguments, dict):
        raise AudioError("arguments must be an object")
    source = arguments.get("file_path")
    if not isinstance(source, str) or not source or "\x00" in source or not Path(source).is_absolute():
        raise AudioError("file_path must be an absolute path to an existing local file")
    try:
        path = Path(source).resolve(strict=True)
        if not path.is_file():
            raise AudioError("file_path must be a regular local file")
    except (OSError, RuntimeError) as exc:
        raise AudioError(f"Cannot access file_path: {exc}") from exc
    try:
        tempo, signature, origin = validate_timing(
            arguments.get("tempo"), arguments.get("signature", [4, 4]), arguments.get("origin_sec", 0),
        )
        requested = arguments.get("slices")
        if not isinstance(requested, list) or not 1 <= len(requested) <= 4:
            raise AudioError("slices must be an array containing 1..4 ranges")
        slices = []
        for index, item in enumerate(requested):
            if not isinstance(item, dict):
                raise AudioError("each slice must be an object")
            unknown = set(item) - {"label", "start_sec", "end_sec", "start_bar", "end_bar"}
            if unknown:
                raise AudioError(f"unsupported file-slice fields: {', '.join(sorted(map(str, unknown)))}")
            label = item.get("label", f"slice-{index + 1}")
            if not isinstance(label, str) or len(label) > 200:
                raise AudioError("slice label must be a string of at most 200 characters")
            seconds = {key for key in ("start_sec", "end_sec") if key in item}
            bars = {key for key in ("start_bar", "end_bar") if key in item}
            if (seconds and bars) or (not seconds and not bars):
                raise AudioError("each slice needs either seconds or bars, never both")
            if seconds:
                if len(seconds) != 2:
                    raise AudioError("second ranges require start_sec and end_sec")
                start = _number(item["start_sec"], "start_sec")
                end = _number(item["end_sec"], "end_sec")
            else:
                if len(bars) != 2:
                    raise AudioError("bar ranges require start_bar and end_bar")
                if tempo is None:
                    raise AudioError("bar ranges require explicitly supplied tempo; tempo is never guessed")
                first = _number(item["start_bar"], "start_bar")
                last = _number(item["end_bar"], "end_bar")
                if not 0 < last - first <= 8:
                    raise AudioError("bar ranges must be increasing and no longer than 8 bars")
                start = bar_to_seconds(first, tempo, signature, origin)
                end = bar_to_seconds(last, tempo, signature, origin)
            if start < 0 or not 0 < end - start <= MAX_SECONDS:
                raise AudioError("slices must start at/after zero and last more than zero, at most 8 seconds")
            if round(end * SAMPLE_RATE) <= round(start * SAMPLE_RATE):
                raise AudioError("slice is shorter than one output sample")
            slices.append({"label": label, "start_sec": start, "end_sec": end})
        return path, slices, tempo, signature, origin
    except ValueError as exc:
        if isinstance(exc, AudioError):
            raise
        raise AudioError(str(exc)) from exc


def listen_file(arguments: dict, *, scratch: Path, check_cancel: Callable[[], None]) -> dict:
    """Return PCM telemetry and private, persistent <=8s/96kbps mono MP3 paths.

    Ranges are end-exclusive. Bar ranges need explicit quarter-note BPM; seconds
    without tempo never acquire an asserted bar map. include_session_state is
    deliberately ignored: the caller owns Live integration. On failure or
    cancellation every artifact from this call is removed; source is never opened
    for writing. Successful MP3s remain until the caller cleans its scratch area.
    """
    cancelled = False

    def checkpoint():
        nonlocal cancelled
        try:
            check_cancel()
        except BaseException:
            cancelled = True
            raise

    checkpoint()
    source, slices, tempo, signature, origin = _validate(arguments)
    duration, channels = _probe(source, checkpoint)
    for item in slices:
        # ffprobe's decimal duration can round below the actual last sample.
        # Allow one output sample here; decoded frame coverage below remains strict.
        if item["end_sec"] > duration + 1 / SAMPLE_RATE:
            raise AudioError(f"slice {item['label']!r} extends beyond file duration ({duration:g}s)")
    directory = None
    succeeded = False
    try:
        scratch = Path(scratch)
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="listen-", dir=scratch)).resolve()
        results = []
        for index, item in enumerate(slices):
            checkpoint()
            first_sample = round(item["start_sec"] * SAMPLE_RATE)
            frames = round(item["end_sec"] * SAMPLE_RATE) - first_sample
            pcm_path = directory / f"slice-{index + 1}.f32"
            mono_path = directory / f"slice-{index + 1}-mono.f32"
            mp3_path = directory / f"slice-{index + 1}.mp3"
            _run([
                "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-n",
                "-protocol_whitelist", "file", "-ss", f"{first_sample / SAMPLE_RATE:.12f}",
                "-i", str(source), "-t", f"{frames / SAMPLE_RATE:.12f}",
                "-map", "0:a:0", "-vn", "-sn", "-dn", "-threads", "1",
                "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", "-f", "f32le", str(pcm_path),
            ], check_cancel=checkpoint, output=pcm_path, max_output_bytes=(frames + 1) * channels * 4)
            checkpoint()
            raw = np.fromfile(pcm_path, dtype="<f4")
            if raw.size != frames * channels:
                raise AudioError("decoded audio does not cover the requested range; refusing a truncated slice")
            samples = raw.reshape(-1, channels)
            telemetry = analyze_pcm(samples, SAMPLE_RATE, start_sec=first_sample / SAMPLE_RATE,
                                    tempo=tempo, signature=signature, origin_sec=origin,
                                    check_cancel=checkpoint)
            # Usually average channels. If that cancels the signal, retain the
            # loudest channel for the preview; telemetry always uses all channels.
            channel_power = np.mean(samples.astype(np.float64) ** 2, axis=0)
            mono = np.mean(samples, axis=1)
            mode = "channel_average"
            if float(np.mean(mono.astype(np.float64) ** 2)) < float(np.max(channel_power)) * 0.0625:
                channel = int(np.argmax(channel_power))
                mono = samples[:, channel]
                mode = f"channel_{channel + 1}_phase_cancellation_fallback"
            checkpoint()
            np.asarray(mono, dtype="<f4").tofile(mono_path)
            _run([
                "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-n",
                "-protocol_whitelist", "file", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1",
                "-i", str(mono_path), "-map_metadata", "-1", "-threads", "1",
                "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "1", str(mp3_path),
            ], check_cancel=checkpoint, output=mp3_path, max_output_bytes=MAX_MP3_BYTES)
            if not 0 < mp3_path.stat().st_size <= MAX_MP3_BYTES:
                raise AudioError("encoded MP3 is empty or exceeds the 110 KiB cap")
            pcm_path.unlink()
            mono_path.unlink()
            results.append({**item, "path": str(mp3_path), "bytes": mp3_path.stat().st_size,
                            "audio_format": "mp3/96kbps/mono/48000Hz", "preview_mix": mode,
                            "telemetry": telemetry})
        checkpoint()
        result = {"source": "file", "file_path": str(source), "file_duration_sec": duration,
                  "slices": results, "slice_paths": [item["path"] for item in results],
                  "next_step": "Read slice_paths in parallel to hear timbre and groove. PCM levels are measured; supplied-tempo grid is assumed; pitch is inferred, not key/f0 ground truth."}
        succeeded = True
        return result
    except (OSError, ValueError) as exc:
        if cancelled or isinstance(exc, AudioError):
            raise
        raise AudioError(f"Audio processing failed: {exc}") from exc
    finally:
        if directory is not None and not succeeded:
            shutil.rmtree(directory, ignore_errors=True)
