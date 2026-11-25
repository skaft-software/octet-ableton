"""Live → loopback PCM → short previews, with explicit alignment uncertainty."""
import math
import time
import uuid
from pathlib import Path

import numpy as np

from .audio_capture import AudioError, listen_file
from .live_audio import CaptureRecorder, SAMPLE_RATE
from .telemetry import analyze_pcm


def _validate_playhead(started, restored, *, start_beat, duration, tempo):
    """Reject wrong-region previews, not certify sample-accurate audio alignment."""
    begin_time = started.get("started_monotonic")
    end_time, end_beat = restored.get("end_monotonic"), restored.get("end_beat")
    if any(type(x) not in (int, float) or not math.isfinite(x)
           for x in (begin_time, end_time, end_beat)):
        raise AudioError("Capture endpoint timing is missing or invalid; update OctetBridge and restart Live. Preview rejected.")
    # Both clocks come from Live. Include latency compensation, recorder shutdown
    # and capture_end dispatch time rather than expecting exactly duration beats.
    elapsed = end_time - begin_time
    beats_per_second = tempo / 60
    expected_end = start_beat + elapsed * beats_per_second
    requested_end = start_beat + duration * beats_per_second
    # Allow a coarse transport/audio-clock discrepancy, never a whole 4/4 bar.
    tolerance = min(0.5, 0.25 * beats_per_second)
    if (elapsed <= 0 or end_beat <= start_beat or end_beat < requested_end - tolerance
            or abs(end_beat - expected_end) > tolerance):
        raise AudioError(
            "Live playhead does not match the requested capture range: ended at beat %.3f, "
            "expected %.3f (+/-%.3f) after %.3fs, requested beats %.3f..%.3f. "
            "Preview rejected; inspect Live transport before retrying."
            % (end_beat, expected_end, tolerance, elapsed, start_beat, requested_end))
    return {"end_beat": end_beat, "expected_end_beat": expected_end, "tolerance_beats": tolerance}


def listen_live(arguments, *, bridge, scratch: Path, check_cancel, recorder_class=CaptureRecorder):
    if set(arguments) - {"slices", "include_session_state", "device", "latency_ms"}:
        raise AudioError("Live capture uses Live's tempo/meter; omit file tempo, signature and origin.")
    slices = arguments.get("slices")
    if not isinstance(slices, list) or not 1 <= len(slices) <= 4:
        raise AudioError("Provide 1..4 live bar ranges.")
    latency = arguments.get("latency_ms", 0)
    if type(latency) not in (int, float) or not math.isfinite(latency) or not 0 <= latency <= 1000:
        raise AudioError("latency_ms must be a measured loopback delay between 0 and 1000ms.")
    state = (bridge.call("snapshot", check_cancel=check_cancel) if arguments.get("include_session_state", False)
             else bridge.call("lom", {"view": "session", "track_indices": []}, check_cancel=check_cancel))
    transport = state["transport"]
    tempo = transport["bpm"]
    signature = [transport["signature_numerator"], transport["signature_denominator"]]
    beats_per_bar = signature[0] * 4 / signature[1]
    prepared = []
    for i, spec in enumerate(slices):
        if not isinstance(spec, dict) or set(spec) - {"label", "start_bar", "end_bar", "solo_tracks"}:
            raise AudioError("Live slices accept label, start_bar, end_bar and optional solo_tracks.")
        start, end = spec.get("start_bar"), spec.get("end_bar")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end)):
            raise AudioError("Live slices require finite start_bar and end_bar.")
        duration = (end - start) * beats_per_bar * 60 / tempo
        if not start >= 1 or not 0 < end - start <= 8 or not 0 < duration <= 8:
            raise AudioError("Live slices must be increasing, <=8 bars and <=8 seconds.")
        label = spec.get("label", "live-%d" % (i + 1))
        if not isinstance(label, str) or len(label) > 80:
            raise AudioError("label must be a string of at most 80 characters.")
        prepared.append((spec, label, (start - 1) * beats_per_bar, duration))
    output = {"source": "live", "slices": [], "slice_paths": [],
              "next_step": "Read the slice_paths together with an audio-capable model to judge timbre and groove. Capture alignment is approximate, not sample-accurate."}
    if arguments.get("include_session_state", False):
        output["session"] = state
    for spec, label, start_beat, duration in prepared:
        check_cancel()
        capture_id = str(uuid.uuid4())
        params = {"capture_id": capture_id, "start_beat": start_beat, "duration_sec": duration}
        if "solo_tracks" in spec:
            params["solo_tracks"] = spec["solo_tracks"]
        with recorder_class(scratch=scratch, device=arguments.get("device", "BlackHole 2ch"), max_seconds=14) as recorder:
            recorder.start(check_cancel)
            anchor_frame, anchor_time = recorder.frames_written(), time.monotonic()
            started = None
            try:
                started = bridge.call("capture_begin", params, check_cancel=check_cancel)
                if started["tempo"] != tempo or started["signature"] != signature:
                    raise AudioError("Live tempo/meter changed before capture; retry after transport settles.")
                frame = anchor_frame + round((started["started_monotonic"] - anchor_time + latency / 1000) * SAMPLE_RATE)
                count = round(duration * SAMPLE_RATE)
                recorder.wait_frames(frame + count, check_cancel)
                recorder.finish(check_cancel)
            finally:
                # Cleanup must run even after caller cancellation or a lost begin reply.
                try:
                    restored = bridge.call("capture_end", {"capture_id": capture_id}, check_cancel=lambda: None)
                except Exception:
                    if started is not None:
                        raise AudioError("Could not confirm transport restoration; bridge timeout guard will attempt it. Inspect Live.") from None
            if not restored.get("restored"):
                raise AudioError("Capture finished but Live restoration failed: " + str(restored.get("restore_errors")))
            if restored["end_tempo"] != tempo or restored["end_signature"] != signature:
                raise AudioError("Tempo/meter changed during capture; constant-tempo mapping is invalid.")
            playback = _validate_playhead(started, restored, start_beat=start_beat, duration=duration, tempo=tempo)
            window = recorder.export_window(frame, count, recorder.directory / "window.wav", check_cancel=check_cancel)
            audio = listen_file({"file_path": str(window), "slices": [{"label": label, "start_sec": 0, "end_sec": count / SAMPLE_RATE}]}, scratch=scratch, check_cancel=check_cancel)
            samples = np.fromfile(recorder.raw_path, dtype="<f4", count=count * 2, offset=frame * 8).reshape(-1, 2)
            item = audio["slices"][0]
            item["start_sec"] = start_beat * 60 / tempo
            item["end_sec"] = item["start_sec"] + count / SAMPLE_RATE
            item["telemetry"] = analyze_pcm(samples, SAMPLE_RATE, start_sec=item["start_sec"], tempo=tempo, signature=signature, check_cancel=check_cancel)
            item["capture"] = {"device": recorder.device, "alignment": "estimated from recorder frames and Live dispatch clock; device buffering uncalibrated",
                               "latency_compensation_ms": latency, "transport_restored": True, "playback": playback,
                               "warning": "Silence: check Live output routing to the selected loopback device." if item["telemetry"]["peak_dbfs"] is None or item["telemetry"]["peak_dbfs"] < -80 else None}
            output["slices"].append(item)
            output["slice_paths"].append(item["path"])
    return output
