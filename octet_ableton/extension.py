"""Three musical tools and a small setup menu."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from octet_extension import CancelledError, Extension, RpcError, audio_content, text_content, tool_result

from .audio_capture import AudioError, listen_file
from .bridge_client import BRIDGE_REVISION, BridgeClient, BridgeError
from .installer import default_user_library, setup
from .live_audio import discover_devices
from .live_listen import listen_live
from .presentation import ToolRun, compact_compose

NO_LOOPBACK = "Live loopback capture is macOS-only. Export a WAV from Live and pass its absolute file_path instead."

LISTEN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "attach_audio": {"type": "boolean", "default": False, "description": "Ask for confirmation to send the requested MP3 previews to the active model as native audio."},
        "file_path": {
            "type": "string",
            "description": "Local WAV/MP3/etc. Omit to record Live through BlackHole 2ch (or an explicitly selected loopback device).",
        },
        "tempo": {
            "type": "number",
            "minimum": 20,
            "maximum": 999,
            "description": "Known constant BPM for THIS file, not automatically the open Live set's tempo.",
        },
        "signature": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "minItems": 2,
            "maxItems": 2,
            "default": [4, 4],
        },
        "origin_sec": {
            "type": "number",
            "minimum": 0,
            "description": "Time of bar 1 in the file; assumes constant tempo/meter.",
        },
        "include_session_state": {"type": "boolean", "default": False, "description": "Opt in to a full session snapshot; use ableton_live_object_model view=session for compact inspection."},
        "device": {"type": "string", "description": "Live capture only: exact loopback audio device name; default BlackHole 2ch. Never falls back to microphone."},
        "latency_ms": {"type": "number", "minimum": 0, "maximum": 1000, "description": "Live capture only: measured loopback delay compensation; default 0 is uncalibrated."},
        "slices": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string", "maxLength": 80},
                    "start_bar": {"type": "number", "minimum": 1},
                    "end_bar": {"type": "number", "exclusiveMinimum": 1},
                    "start_sec": {"type": "number", "minimum": 0},
                    "end_sec": {"type": "number", "exclusiveMinimum": 0},
                    "solo_tracks": {"type": "array", "items": {"type": "integer", "minimum": 0}, "maxItems": 64, "description": "Live only; temporary solos, restored afterward. Empty array clears solos for this preview."},
                },
                "description": "Use seconds OR 1-based bars with exclusive end. At most 8 seconds and 8 bars per slice. Bar ranges require tempo.",
            },
        },
    },
    "required": ["slices"],
}
COMPOSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "detail": {"type": "string", "enum": ["summary", "full"], "default": "summary", "description": "Compact summary and full receipt path by default; full returns all receipts inline."},
        "dry_run": {
            "type": "boolean",
            "default": True,
            "description": "Preview by default; false applies the batch. Not transactional; inspect receipts before retrying.",
        },
        "actions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 64,
            "items": {
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": [
                            "create_midi_track",
                            "create_audio_track",
                            "duplicate_track",
                            "load_device_or_preset",
                            "set_device_params",
                            "set_track_controls",
                            "write_arrangement_midi_clip",
                            "place_audio_clip",
                            "set_transport",
                        ],
                    }
                },
                "required": ["op"],
                "additionalProperties": True,
            },
        },
    },
    "required": ["actions"],
}
INSPECTION_PROPERTIES = {
    "view": {"type": "string", "enum": ["session", "device"]},
    "track_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}, "maxItems": 64},
    "track_index": {"type": "integer", "minimum": 0},
    "device": {"anyOf": [{"type": "integer", "minimum": 0}, {"type": "string", "minLength": 1}]},
    "offset": {"type": "integer", "minimum": 0, "maximum": 1023},
    "limit": {"type": "integer", "minimum": 1, "maximum": 256},
    "parameters": {"type": "array", "maxItems": 256, "items": {"anyOf": [{"type": "integer", "minimum": 0}, {"type": "string", "minLength": 1}]}},
    "fields": {"type": "array", "items": {"type": "string", "enum": ["name", "min", "max", "value", "is_enabled", "is_quantized", "display_value", "automation_state", "value_items"]}},
}
LOM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        **INSPECTION_PROPERTIES,
        "expression": {"type": "string", "minLength": 1, "maxLength": 1024},
        "queries": {"type": "array", "minItems": 1, "maxItems": 16,
                    "items": {"type": "object", "properties": INSPECTION_PROPERTIES, "required": ["view"], "additionalProperties": False}},
    },
    "oneOf": [{"required": ["expression"]}, {"required": ["view"]}, {"required": ["queries"]}],
    "description": "Use view=session, view=device with track_index/device and optional parameters/fields, a queries batch, OR a legacy expression. Never mix modes. Read-only; no arbitrary code.",
}


def result(value, *parts, error=False):
    return tool_result(
        text_content(
            json.dumps(
                value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
        ),
        *parts,
        is_error=error,
    )


def build_extension(*, client=None, scratch=None):
    ext = Extension(
        api_version="0.4",
        max_concurrent_requests=1,
        supported_features=["request_cancellation", "content_parts", "artifacts"],
    )
    bridge = client or BridgeClient()
    cached_status = "Not checked. Run /ableton status."
    scratch_dir = Path(scratch) if scratch else None

    def audio_scratch():
        nonlocal scratch_dir
        if scratch_dir is None:
            host_scratch = os.environ.get("OCTET_EXTENSION_SCRATCH")
            scratch_dir = Path(
                tempfile.mkdtemp(prefix="octet-ableton-", dir=host_scratch)
            )
        return scratch_dir

    @ext.tool(
        name="ableton_listen",
        parameters=LISTEN_SCHEMA,
        description="Listen to a file or capture Live bar ranges through loopback, restoring transport/solos afterward. Measure energy, spectral bands, estimated pitch and grid gaps. Returns short mono MP3 paths: read chosen slices together to hear timbre/groove, then compose in one batch. File grids assume constant tempo/meter/origin; Live loopback alignment is approximate and uncalibrated. Pitch is an estimate. Alternatively, attach_audio=true asks for confirmation to send these previews to the current model in slice order. Default is local only.",
    )
    def listen(args):
        run = ToolRun(bridge)
        try:
            ext.cancellation.raise_if_cancelled()
            if not isinstance(args, dict) or set(args) - set(
                LISTEN_SCHEMA["properties"]
            ):
                raise ValueError("Unexpected listen argument.")
            if type(args.get("include_session_state", False)) is not bool:
                raise ValueError("include_session_state must be boolean.")
            args = dict(args)
            attach = args.pop("attach_audio", False)
            if type(attach) is not bool:
                raise ValueError("attach_audio must be boolean.")
            if attach and "artifacts" not in ext.negotiated_features:
                raise ValueError("Host did not negotiate audio artifacts. Omit attach_audio for local previews.")
            if "file_path" not in args:
                if sys.platform == "win32":
                    raise AudioError(NO_LOOPBACK)
                output = listen_live(args, bridge=run, scratch=audio_scratch(), check_cancel=ext.cancellation.raise_if_cancelled)
            else:
                if "device" in args or "latency_ms" in args:
                    raise ValueError("device and latency_ms apply only to live capture.")
                output = listen_file(args, scratch=audio_scratch(), check_cancel=ext.cancellation.raise_if_cancelled)
                if args.get("include_session_state", False):
                    try:
                        output["session"] = run.call("snapshot", check_cancel=ext.cancellation.raise_if_cancelled)
                    except BridgeError as exc:
                        output["session_unavailable"] = str(exc)
            if not attach:
                return result(run.finish(output))

            paths = output["slice_paths"]
            output.pop("next_step")  # Never suggest re-reading declined or attached previews.
            parts = []
            try:
                if not ext.confirm(
                    f"Send {len(paths)} audio preview(s) to the current model provider?",
                    detail=f"Source: {args.get('file_path', 'Live loopback')}. Requested slices: {json.dumps(args['slices'])}. Audio may be retained in session history.",
                ):
                    output["audio_attachment"] = "Declined; local previews only."
                    return result(run.finish(output))
                for path in paths:
                    ext.cancellation.raise_if_cancelled()
                    artifact = ext.publish_artifact(mime_type="audio/mpeg", data=Path(path).read_bytes())
                    parts.append(audio_content(artifact, "audio/mpeg"))
            except CancelledError:
                raise
            except (RpcError, OSError) as exc:
                output["error"] = f"Audio attachment failed: {exc}. Local previews retained."
                return result(run.finish(output), error=True)
            return result(run.finish(output), *parts)
        except (AudioError, BridgeError, ValueError, OSError) as exc:
            return result(run.finish({"error": str(exc)}), error=True)

    @ext.tool(
        name="ableton_compose",
        parameters=COMPOSE_SCHEMA,
        description="Batch musical edits in Live, preview by default. Returns compact counts, failures and a full receipt_path; detail=full opts into inline receipts. Actions use op. Create tracks with name and ref; address later actions with track_ref (or track_index). Load devices with query and optional root. set_device_params uses device and params in actual Live units. Track controls: color, volume or volume_db, pan, sends {index:value}, exact input/output_routing_type/channel labels. MIDI: start_bar,length_bars,notes[{pitch,start_beat,duration_beats,velocity,probability?}]. Device envelopes: envelopes.device_params[{device,param,points:[{beat,value,curve?}]}]; first beat 0; curve step or ramp (96 steps/quarter, arriving at point). No MIDI pitch-bend/CC writes; automate an exposed instrument pitch parameter instead. Audio: warp_mode, gain,pitch_coarse,pitch_fine. Transport: bpm,playhead_bar,playing,loop,loop_start_bar,loop_length_bars. Save your set first; errors/cancellation do not roll back earlier edits. Never replay a lost batch blindly.",
    )
    def compose(args):
        run = ToolRun(bridge)
        try:
            if not isinstance(args, dict) or set(args) - {"actions", "dry_run", "detail"}:
                raise ValueError("Expected actions, optional dry_run and detail.")
            if args.get("detail", "summary") not in ("summary", "full"):
                raise ValueError("detail must be summary or full.")
            # Allocate scratch before any mutation, so allocation failure cannot hide applied effects.
            receipt_dir = audio_scratch() if args.get("detail", "summary") == "summary" else None
            return_value = run.call(
                "compose", {k: v for k, v in args.items() if k != "detail"}, check_cancel=ext.cancellation.raise_if_cancelled
            )
            failed = return_value.get("status") in ("failed", "partial", "cancelled") or return_value.get("ok") is False
            output = compact_compose(return_value, receipt_dir) if receipt_dir is not None else return_value
            return result(run.finish(output), error=failed)
        except (BridgeError, ValueError, OSError) as exc:
            return result(run.finish({"error": str(exc)}), error=True)

    @ext.tool(
        name="ableton_live_object_model",
        parameters=LOM_SCHEMA,
        description="Ableton Live Object Model: inspect Live without edits. Prefer view=session for compact tracks/devices/clip counts, or view=device with track_index/device and parameters/fields for a column/row table. Batch up to 16 independent reads in queries; all use one bridge call. Defaults to name/value fields; request min/max/is_quantized once for a schema, keep it in code-mode store, and read fresh values before edits. Unavailable fields are explicit, not whole-query failures. Legacy expression permits only song/app paths, never Python execution.",
    )
    def lom(args):
        run = ToolRun(bridge)
        try:
            value = run.call("lom", args, check_cancel=ext.cancellation.raise_if_cancelled)
            return result(run.finish(value), error=value.get("ok") is False)
        except (BridgeError, ValueError) as exc:
            return result(run.finish({"error": str(exc)}), error=True)

    @ext.command(
        name="ableton",
        description="Set up OctetBridge or check connection",
        usage="/ableton [setup [absolute-user-library-path] | status | devices | help]",
    )
    def command(arguments):
        nonlocal cached_status
        try:
            if arguments and arguments[0] == "setup" and len(arguments) <= 2:
                library = (
                    Path(arguments[1]).expanduser()
                    if len(arguments) == 2
                    else default_user_library()
                )
                if not library.is_absolute():
                    raise ValueError("Use an absolute User Library path.")
                if not ext.confirm(
                    "Install/update OctetBridge?",
                    detail=f"Copies the bundled Remote Script into {library / 'Remote Scripts/OctetBridge'}. Keeps a backup on update. No Live set or audio routing is changed.",
                ):
                    return "Setup cancelled."
                outcome = setup(
                    library, check_cancel=ext.cancellation.raise_if_cancelled
                )
                cached_status = (
                    "Installed; select OctetBridge in Live, then check status."
                )
                return json.dumps(outcome, indent=2)
            if arguments == ["devices"]:
                if sys.platform == "win32":
                    return NO_LOOPBACK
                return json.dumps(discover_devices(ext.cancellation.raise_if_cancelled), indent=2)
            if arguments == ["status"] or not arguments:
                ffmpeg = (
                    shutil.which("ffmpeg") is not None
                    and shutil.which("ffprobe") is not None
                )
                try:
                    state = bridge.call(
                        "ping", check_cancel=ext.cancellation.raise_if_cancelled
                    )
                    cached_status = ("Bridge connected (runtime reported, not an audition)."
                                     if state.get("revision") == BRIDGE_REVISION else
                                     "Bridge connected but outdated: run /ableton setup, save your Set, then restart Live.")
                    state["update_required"] = state.get("revision") != BRIDGE_REVISION
                except BridgeError as exc:
                    state = {"connected": False, "message": str(exc)}
                    cached_status = "Bridge unavailable; see /ableton status."
                return json.dumps(
                    {
                        "bridge": state,
                        "status": cached_status,
                        "file_audio_ready": ffmpeg,
                        "live_capture": NO_LOOPBACK if sys.platform == "win32" else "Route Live output to BlackHole 2ch; /ableton devices lists exact capture device names. Capture does not alter audio routing.",
                    },
                    indent=2,
                )
            return (
                "/ableton setup [absolute User Library path] installs OctetBridge after confirmation.\n"
                "/ableton status checks the bridge and FFmpeg.\n"
                "/ableton devices lists audio capture devices.\n"
                "Three tools: ableton_listen (file or Live → slices), ableton_compose (batch edits), ableton_live_object_model (inspect).\n"
                "Save your set before editing. No telemetry or automatic audio uploads."
            )
        except (BridgeError, OSError, ValueError) as exc:
            return "Ableton: " + str(exc)

    @ext.menu
    def menu(_params):
        return {
            "title": "Ableton · unofficial",
            "detail": cached_status,
            "items": [
                {
                    "id": "status",
                    "label": "Check connection",
                    "command": "ableton",
                    "arguments": ["status"],
                },
                {
                    "id": "setup",
                    "label": "Install / update OctetBridge",
                    "command": "ableton",
                    "arguments": ["setup"],
                },
                {
                    "id": "help",
                    "label": "Quick help",
                    "command": "ableton",
                    "arguments": ["help"],
                },
            ],
        }

    return ext
