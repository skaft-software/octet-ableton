#!/usr/bin/env python3
"""Opt-in technical Live test; saves evidence for an audio-capable model.

Only use a disposable saved set. Adds one named track; never deletes existing
tracks or uploads audio. No automatic retry after any possibly applied failure.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octet_ableton.bridge_client import BridgeClient  # noqa: E402
from octet_ableton.live_audio import DEFAULT_DEVICE  # noqa: E402
from octet_ableton.live_listen import listen_live  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Authorize adding a test track to the named scratch set")
    parser.add_argument("--expect-marker", required=True, help="Exact name of a marker track you created in the disposable set")
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory")
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    args = parser.parse_args()
    if sys.platform not in ("darwin", "win32"):
        parser.error("This fixture requires a routed Windows or macOS loopback input; see README.md.")
    if not args.apply:
        parser.error("This test modifies the scratch set. Pass --apply explicitly.")
    client = BridgeClient()
    before = client.call("snapshot")
    if not any(t["name"] == args.expect_marker for t in before["tracks"]):
        parser.error("Expected marker track not found; open the disposable set and create the named marker first.")
    if before["transport"]["playing"]:
        parser.error("Stop playback before running the qualification test.")
    if (before["transport"]["signature_numerator"], before["transport"]["signature_denominator"]) != (4, 4) or before["transport"]["bpm"] < 60:
        parser.error("Use a 4/4 scratch set at >=60 BPM for this two-bar fixture.")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"marker": args.expect_marker, "before": before, "subjective_audio_review": "not performed"}
    def save():
        (args.output / "report.json").write_text(json.dumps(report, indent=2))
    def compose(actions):
        result = client.call("compose", {"dry_run": False, "actions": actions})
        report.setdefault("batches", []).append(result)
        save()
        if not result.get("ok"):
            raise RuntimeError("Compose failed; inspect report and Live before retrying.")
        return result
    save()
    try:
        name = "Octet check " + uuid.uuid4().hex[:6]
        created = compose([
            {"op": "create_midi_track", "name": name, "ref": "test", "volume": 0.55},
            {"op": "load_device_or_preset", "track_ref": "test", "query": "Operator", "root": "instruments"},
            {"op": "load_device_or_preset", "track_ref": "test", "query": "Auto Filter", "root": "audio_effects"},
        ])
        index = created["receipts"][0]["result"]["track_index"]
        parameters = client.call("lom", {"expression": "song.tracks[%d].devices[1].parameters" % index})["value"]
        frequency = next((p for p in parameters if p.get("name") in ("Frequency", "Filter Freq")), None)
        if frequency is None:
            raise RuntimeError("Cannot identify filter Frequency parameter; inspect device parameters.")
        low, high = frequency["min"], frequency["max"]
        compose([{"op": "write_arrangement_midi_clip", "track_index": index,
                  "name": "Qualification sweep", "start_bar": 5, "length_bars": 2,
                  "notes": [{"pitch": pitch, "start_beat": beat, "duration_beats": 0.75, "velocity": 88}
                            for pitch, beat in [(60, 0), (67, 1), (63, 2), (70, 3), (60, 4), (67, 5), (63, 6), (72, 7)]],
                  "envelopes": {"device_params": [{"device": 1, "param": frequency["name"], "points": [
                      {"beat": 0, "value": low + (high - low) * 0.2},
                      {"beat": 6, "value": low + (high - low) * 0.8, "curve": "ramp"}]}]}}])
        state = client.call("snapshot")
        track = next(t for t in state["tracks"] if t["name"] == name)
        assert len(track["arrangement_clips"]) == 1
        assert track["arrangement_clips"][0]["start_beat"] == 16
        assert not track["session_clips"], "Staging clip leaked"
        report["live_readback"] = track
        report["capture"] = listen_live({"device": args.device, "slices": [
            {"label": "synth-with-filter-sweep", "start_bar": 5, "end_bar": 7, "solo_tracks": [index]}]},
            bridge=client, scratch=args.output, check_cancel=lambda: None)
        after = client.call("snapshot")
        for key in ("playing", "playhead_beat", "loop", "bpm"):
            assert after["transport"][key] == state["transport"][key], "Transport not restored: " + key
        peak = report["capture"]["slices"][0]["telemetry"]["peak_dbfs"]
        if peak is None or peak < -70:
            raise RuntimeError("Captured silence; check Live output and loopback routing.")
        report["technical_result"] = "passed"
        print("Technical Live test passed. Read the saved capture with an audio-capable model for musical qualification.")
    except BaseException as exc:
        report["technical_result"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
