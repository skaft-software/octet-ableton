"""Main-thread-only Live operations, original implementation using documented LOM.

compose: {"actions": [{"op": "create_midi_track", "ref": "lead"}, ...],
          "dry_run": true}. Select tracks with exactly one track_index/track_ref.
Indices refer to the evolving track list; refs retain identity across insertions.
Device selectors are exact names or integer indices; params maps exact parameter
names (or decimal index strings) to values in Live's min/max domain, NOT normalized
percentages or display-text units. Mixer volume is raw 0..1; volume_db uses
Live's own str_for_value display conversion, never a guessed linear mapping.
Track controls: name, color (RGB integer), volume OR volume_db, pan, sends
({decimal send index: raw value}), exact input/output_routing_type/channel labels.
These work on create/duplicate and set_track_controls. Audio adds warp_mode,
pitch_coarse (semitones), pitch_fine (cents), gain (Live raw 0..1).
MIDI probability uses Live.Clip.MidiNoteSpecification. Device envelopes use the
schema in automation.py, with step or explicitly rasterized ramp segments.
Bars are 1-based, beats 0-based quarter notes in the current simulated signature.

Evidence: https://docs.cycling74.com/apiref/lom/{track,clip,clipslot,song}/
Python set_notes(tuple((pitch,time,duration,velocity,mute), ...)) is the legacy
Remote Script API. Arrangement MIDI uses create_midi_clip if present, otherwise
an empty Session slot plus duplicate_clip_to_arrangement. Audio uses a temporary
Session import to measure its extent BEFORE touching Arrangement. No undocumented
pitch-bend/CC writes are attempted. Parameter envelopes are staged in Session
before Arrangement duplication. Not Live-qualified.
"""
import ast
import math
import os
import re
import threading
from collections import deque

from .server import BridgeError
from . import automation

try:
    import Live
except ImportError:  # Tests run outside Live; inject live_api for modern APIs.
    Live = None

MAX_ACTIONS = 64
MAX_NOTES = 4096
MAX_TRACKS = 512
MAX_CLIPS = 4096
MAX_BEATS = 1576800.0
BROWSER_LIMIT = 4096
BROWSER_ROOTS = ("instruments", "audio_effects", "midi_effects", "user_library")
TRACK_SELECTOR = {"track_index", "track_ref"}
ROUTING_FIELDS = {"input_routing_type", "input_routing_channel", "output_routing_type", "output_routing_channel"}
CONTROL_FIELDS = {"name", "color", "volume", "volume_db", "pan", "sends"} | ROUTING_FIELDS
CREATE_FIELDS = CONTROL_FIELDS | {"ref"}
WARP_MODES = {"beats": "beats", "tones": "tones", "texture": "texture", "repitch": "repitch",
              "complex": "complex", "complex_pro": "complex_pro"}
TIMING = {"start_beat", "length_beats", "start_bar", "length_bars"}
ACTION_FIELDS = {
    "create_midi_track": CREATE_FIELDS | {"index"},
    "create_audio_track": CREATE_FIELDS | {"index"},
    "duplicate_track": CREATE_FIELDS | TRACK_SELECTOR,
    "load_device_or_preset": TRACK_SELECTOR | {"name", "query", "root"},
    "set_device_params": TRACK_SELECTOR | {"device", "params"},
    "set_track_controls": TRACK_SELECTOR | CONTROL_FIELDS,
    "write_arrangement_midi_clip": TRACK_SELECTOR | TIMING | {"name", "notes", "envelopes"},
    "place_audio_clip": TRACK_SELECTOR | {"path", "start_beat", "start_bar", "name", "gain", "pitch_coarse", "pitch_fine", "warp_mode", "envelopes"},
    "set_transport": {"bpm", "signature_numerator", "signature_denominator", "loop",
                      "loop_start_beat", "loop_length_beats", "playhead_beat",
                      "loop_start_bar", "loop_length_bars", "playhead_bar", "playing"},
}


def fail(message, code="validation"):
    raise BridgeError(code, message)


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        fail("Unknown, missing, or invalid object fields.")


def number(value, label, low, high, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        fail(label + " must be a finite " + ("integer." if integer else "number."))
    if not low <= value <= high or not math.isfinite(value):
        fail(label + " is outside its allowed range.")
    return value


def text(value, label, limit=256):
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        fail(label + " must be a nonempty bounded string.")
    return value


def boolean(value, label):
    if type(value) is not bool:
        fail(label + " must be boolean.")


def available(obj, name):
    return callable(getattr(obj, name, None))


def arrangement_clips(track):
    # Live exposes the attribute on Group Tracks but raises when it is read.
    return () if getattr(track, "is_foldable", False) else getattr(track, "arrangement_clips", ())


def bounded(values, limit, label):
    if len(values) > limit:
        fail(label + " exceeds the safe inspection limit.", "limit")
    return list(values)


class LiveEngine:
    def __init__(self, song, app, live_api=None):
        self.song = song
        self.app = app
        self.live_api = live_api if live_api is not None else Live
        self._owner = threading.get_ident()

    def handle(self, method, params, check_active=lambda: None):
        if threading.get_ident() != self._owner:
            raise RuntimeError("LOM must be accessed on Live's main thread")
        check_active()
        if method == "compose":
            return self.compose(params, check_active)
        if method == "lom":
            return self.lom(params, check_active)
        fields(params, ())
        if method == "ping":
            return {"bridge": "OctetBridge", "protocol": 1, "revision": 6, "capabilities": self.capabilities(),
                    "transport": self.transport()}
        if method == "snapshot":
            return self.snapshot()
        fail("Unknown method.")

    def transport(self):
        return {"bpm": self.song.tempo, "signature_numerator": self.song.signature_numerator,
                "signature_denominator": self.song.signature_denominator,
                "playing": bool(self.song.is_playing), "playhead_beat": self.song.current_song_time,
                "loop": bool(self.song.loop), "loop_start_beat": self.song.loop_start,
                "loop_length_beats": self.song.loop_length}

    def capabilities(self):
        tracks = list(self.song.tracks[:64])
        slots = [slot for track in tracks for slot in track.clip_slots[:8]]
        clips = [slot.clip for slot in slots if slot.has_clip]
        return {
            "live_qualified": False, "unauditioned": True, "rollback": False,
            "cancellation": "Cooperative checks before effects; an in-flight Live call cannot be interrupted. Never automatically retry writes.",
            "actual_api_presence": {
                "Song.create_midi_track": available(self.song, "create_midi_track"),
                "Song.create_audio_track": available(self.song, "create_audio_track"),
                "Song.duplicate_track": available(self.song, "duplicate_track"),
                "Track.create_midi_clip": any(available(t, "create_midi_clip") for t in tracks) if tracks else None,
                "Track.create_audio_clip": any(available(t, "create_audio_clip") for t in tracks) if tracks else None,
                "Track.duplicate_clip_to_arrangement": any(available(t, "duplicate_clip_to_arrangement") for t in tracks) if tracks else None,
                "ClipSlot.create_audio_clip": any(available(s, "create_audio_clip") for s in slots) if slots else None,
                "Clip.set_notes": any(available(c, "set_notes") for c in clips) if clips else None,
                "Clip.add_new_notes": any(available(c, "add_new_notes") for c in clips) if clips else None,
                "Clip.create_automation_envelope": any(available(c, "create_automation_envelope") for c in clips) if clips else None,
                "Live.Clip.MidiNoteSpecification": available(getattr(self.live_api, "Clip", None), "MidiNoteSpecification"),
                "Browser.load_item": available(getattr(self.app, "browser", None), "load_item"),
            },
            "api_probe_scope": "First 64 tracks / 8 Session slots per track. Null means no sample object; presence is not qualification.",
            "envelopes": {
                "supported": any(available(c, "create_automation_envelope") for c in clips) if clips else None,
                "implemented": "Session device-parameter envelopes, then Arrangement duplication; runtime API availability checked before duplication.",
                "pitch_bend_cc": False, "time_units": "clip-relative quarter-note beats",
                "value_units": "actual parameter min/max domain",
                "curves": "step; ramp rasterized at <=1/96 quarter-note intervals, not native continuous interpolation",
                "curve_direction": "curve describes the segment arriving at that point; default step",
                "limits": {"envelopes": automation.MAX_ENVELOPES, "points_per_envelope": automation.MAX_POINTS,
                           "steps_per_clip": automation.MAX_STEPS}},
            "audio_placement": "Requires an empty Session slot and create_audio_clip; enables warping to measure beat extent, then checks overlap and duplicates. Optional warp_mode uses Live.Clip.WarpMode.",
            "track_controls": "color RGB, volume raw OR volume_db via Live display inversion, pan, sends {index: raw value}, exact input/output routing type/channel labels.",
            "note_probability": "Live.Clip.MidiNoteSpecification + add_new_notes required; never silently dropped.",
            "browser_search": "Unique exact top-level category child first; recursive preset search only within an explicit root, capped at 4096 nodes.",
            "parameter_units": "Raw Live parameter min/max domain, not normalized fractions, dB conversions, or display strings.",
            "bar_mapping": "Current signature only; does not model historical meter or tempo automation.",
            "limits": {"actions": MAX_ACTIONS, "notes_per_clip": MAX_NOTES, "frame_bytes": 524288},
        }

    def snapshot(self):
        truncated = []

        def take(values, count, path):
            if len(values) > count:
                truncated.append(path)
            return values[:count]

        def clip_info(clip):
            return {"name": str(clip.name)[:128], "start_beat": clip.start_time,
                    "end_beat": clip.end_time, "midi": bool(clip.is_midi_clip)}

        tracks = []
        parameter_budget = 128
        for index, track in enumerate(take(self.song.tracks, 64, "tracks")):
            base = "tracks[%d]" % index
            devices = []
            for i, device in enumerate(take(track.devices, 16, base + ".devices")):
                parameters = take(device.parameters, min(16, parameter_budget), base + ".devices[%d].parameters" % i)
                parameter_budget -= len(parameters)
                devices.append({"index": i, "name": str(device.name)[:128], "parameter_count": len(device.parameters),
                                "parameters": [{"index": j, "name": str(p.name)[:128], "min": p.min, "max": p.max,
                                                "value": p.value, "is_enabled": bool(getattr(p, "is_enabled", True)),
                                                "is_quantized": bool(getattr(p, "is_quantized", False))}
                                               for j, p in enumerate(parameters)]})
            arrangement = arrangement_clips(track)
            clips = [clip_info(c) for c in take(arrangement, 32, base + ".arrangement_clips")]
            session = [{"slot_index": i, "name": str(s.clip.name)[:128], "length": s.clip.length}
                       for i, s in enumerate(take(track.clip_slots, 8, base + ".clip_slots")) if s.has_clip]
            tracks.append({"index": index, "name": str(track.name)[:128],
                           "midi": bool(track.has_midi_input), "group": bool(getattr(track, "is_foldable", False)), "devices": devices,
                           "arrangement_clips": clips, "session_clips": session,
                           "color": getattr(track, "color", None),
                           "volume": track.mixer_device.volume.value, "pan": track.mixer_device.panning.value,
                           "sends": [p.value for p in take(getattr(track.mixer_device, "sends", ()), 16, base + ".sends")],
                           "routing": {key: str(getattr(getattr(track, key, None), "display_name", ""))[:128]
                                       for key in sorted(ROUTING_FIELDS)}})
        locators = [{"name": str(c.name)[:128], "beat": c.time}
                    for c in take(self.song.cue_points, 64, "locators")]
        return {"song_name": str(getattr(self.song, "name", ""))[:256],
                "transport": self.transport(), "tracks": tracks, "locators": locators,
                "truncated": bool(truncated), "truncated_paths": truncated,
                "capabilities": self.capabilities()}

    def _syntax(self, params):
        fields(params, {"actions", "dry_run"}, {"actions"})
        boolean(params.get("dry_run", True), "dry_run")
        actions = params["actions"]
        if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
            fail("actions must contain 1..64 actions.")
        for action in actions:
            if not isinstance(action, dict):
                fail("Each action must be an object.")
            kind = action.get("op")
            if not isinstance(kind, str) or kind not in ACTION_FIELDS:
                fail("Unknown action type.")
            fields(action, ACTION_FIELDS[kind] | {"op"})
            if TRACK_SELECTOR & ACTION_FIELDS[kind]:
                if len(TRACK_SELECTOR & set(action)) != 1:
                    fail("Use exactly one track_index or track_ref.")
                if "track_index" in action:
                    number(action["track_index"], "track_index", 0, MAX_TRACKS - 1, True)
                else:
                    text(action["track_ref"], "track_ref", 64)
            for key in ("name", "ref", "query"):
                if key in action:
                    text(action[key], key, 64 if key == "ref" else 256)
            if "index" in action:
                number(action["index"], "index", -1, MAX_TRACKS, True)
            for key, low, high in (("volume", 0, 1), ("volume_db", -144, 24), ("pan", -1, 1),
                                   ("gain", 0, 1), ("pitch_coarse", -48, 48), ("pitch_fine", -50, 50),
                                   ("color", 0, 0xFFFFFF)):
                if key in action:
                    number(action[key], key, low, high, key in ("pitch_coarse", "pitch_fine", "color"))
            if "volume" in action and "volume_db" in action:
                fail("Use volume or volume_db, not both.")
            for key in ROUTING_FIELDS & set(action):
                text(action[key], key)
            if "sends" in action:
                if not isinstance(action["sends"], dict) or not 1 <= len(action["sends"]) <= 16:
                    fail("sends must map 1..16 decimal send indices to raw values.")
                for key, value in action["sends"].items():
                    if not isinstance(key, str) or not re.fullmatch(r"0|[1-9][0-9]?", key):
                        fail("Send selectors must be canonical decimal index strings.")
                    number(value, "send value", 0, 1)
            if "warp_mode" in action:
                if not isinstance(action["warp_mode"], str) or action["warp_mode"] not in WARP_MODES:
                    fail("Unknown warp_mode; use beats, tones, texture, repitch, complex or complex_pro.")
                self._warp_mode(action["warp_mode"])
            if "envelopes" in action:
                automation.validate(action["envelopes"], fields, number, text, MAX_BEATS)
            if kind == "load_device_or_preset":
                if len({"name", "query"} & set(action)) != 1:
                    fail("Specify one exact browser name or query (not a fuzzy search).")
                if action.get("root", "instruments") not in BROWSER_ROOTS:
                    fail("Unsupported browser root.")
            if kind == "set_device_params":
                if "device" not in action or "params" not in action:
                    fail("device and params are required.")
                if type(action["device"]) is int:
                    number(action["device"], "device", 0, 255, True)
                else:
                    text(action["device"], "device")
                values = action["params"]
                if not isinstance(values, dict) or not 1 <= len(values) <= 128:
                    fail("params must map 1..128 parameter names or index strings to values.")
                for key, value in values.items():
                    text(key, "parameter selector")
                    number(value, "parameter value", -1e15, 1e15)
            if kind == "write_arrangement_midi_clip":
                self._timing(action, 4, length=True)
                notes = action.get("notes")
                if not isinstance(notes, list) or len(notes) > MAX_NOTES:
                    fail("notes must be an array of at most 4096 notes.")
                for note in notes:
                    fields(note, {"pitch", "start_beat", "duration_beats", "velocity", "mute", "probability"},
                           {"pitch", "start_beat", "duration_beats", "velocity"})
                    number(note["pitch"], "pitch", 0, 127, True)
                    number(note["start_beat"], "note start_beat", 0, MAX_BEATS)
                    number(note["duration_beats"], "duration_beats", 1e-9, MAX_BEATS)
                    number(note["velocity"], "velocity", 1, 127, True)
                    boolean(note.get("mute", False), "mute")
                    if "probability" in note:
                        number(note["probability"], "probability", 0, 1)
                        if not available(getattr(self.live_api, "Clip", None), "MidiNoteSpecification"):
                            fail("Note probability requires Live.Clip.MidiNoteSpecification.", "unsupported")
            if kind == "place_audio_clip":
                self._timing(action, 4, length=False)
                path = text(action.get("path"), "path", 4096)
                if not os.path.isabs(path) or not os.path.isfile(path):
                    fail("Audio path must be an existing absolute file path.")
            if kind == "set_transport":
                self._transport_values(action, 4)

    def _timing(self, action, bar_length, length):
        if len({"start_beat", "start_bar"} & set(action)) != 1:
            fail("Specify exactly one start_beat or start_bar.")
        if "start_beat" in action:
            start = number(action["start_beat"], "start_beat", 0, MAX_BEATS)
        else:
            start = (number(action["start_bar"], "start_bar", 1, MAX_BEATS) - 1) * bar_length
        duration = None
        if length:
            if len({"length_beats", "length_bars"} & set(action)) != 1:
                fail("Specify exactly one length_beats or length_bars.")
            key = "length_beats" if "length_beats" in action else "length_bars"
            duration = number(action[key], key, 1e-9, MAX_BEATS) * (1 if key == "length_beats" else bar_length)
        number(start + (duration or 0), "clip end", 0, MAX_BEATS)
        return start, duration

    def _transport_values(self, action, bar_length):
        result = {}
        for key, low, high, integer in (("bpm", 20, 999, False), ("signature_numerator", 1, 99, True),
                                       ("signature_denominator", 1, 16, True)):
            if key in action:
                number(action[key], key, low, high, integer)
                if key == "signature_denominator" and action[key] not in (1, 2, 4, 8, 16):
                    fail("signature_denominator must be a power of two up to 16.")
                result["tempo" if key == "bpm" else key] = action[key]
        for prefix, target, is_length in (("loop_start", "loop_start", False),
                                           ("loop_length", "loop_length", True),
                                           ("playhead", "current_song_time", False)):
            beat = prefix + ("_beats" if is_length else "_beat")
            bar = prefix + ("_bars" if is_length else "_bar")
            if beat in action and bar in action:
                fail("Use beats or bars, not both, for " + prefix + ".")
            if beat in action:
                result[target] = number(action[beat], beat, 1e-9 if is_length else 0, MAX_BEATS)
            elif bar in action:
                value = number(action[bar], bar, 1e-9 if is_length else 1, MAX_BEATS)
                result[target] = number((value if is_length else value - 1) * bar_length, bar, 0, MAX_BEATS)
        for key in ("loop", "playing"):
            if key in action:
                boolean(action[key], key)
                result["is_playing" if key == "playing" else key] = action[key]
        if result.get("is_playing") and "current_song_time" in result:
            # Starting restores Live's marker/cached position; seek active playback last.
            result["current_song_time"] = result.pop("current_song_time")
        return result

    def _record(self, track=None, midi=True):
        clips = bounded(arrangement_clips(track), MAX_CLIPS, "Arrangement clips")
        return {"object": track, "midi": bool(track.has_midi_input) if track is not None else midi,
                "ranges": [(c.start_time, c.end_time) for c in clips], "deferred_devices": False,
                "deferred_routing": False}

    def _target(self, action, tracks, refs):
        if "track_ref" in action:
            if action["track_ref"] not in refs:
                fail("track_ref must refer to an earlier created or duplicated track.")
            return refs[action["track_ref"]]
        index = action["track_index"]
        if index >= len(tracks):
            fail("track_index is out of range.")
        return tracks[index]

    def _overlap(self, ranges, start, length):
        if any(start < end and start + length > begin for begin, end in ranges):
            fail("Destination overlaps an occupied Arrangement clip; no overwrite is allowed.", "overlap")

    def _browser_item(self, action, check):
        browser = getattr(self.app, "browser", None)
        if not available(browser, "load_item"):
            fail("Browser loading is unavailable.", "unsupported")
        roots = (action["root"],) if "root" in action else BROWSER_ROOTS
        categories = [getattr(browser, root) for root in roots if hasattr(browser, root)]
        query = action.get("name", action.get("query"))
        direct = {}
        for category in categories:
            check()
            for item in bounded(getattr(category, "children", ()), BROWSER_LIMIT, "Browser category"):
                if getattr(item, "is_loadable", False) and item.name == query:
                    direct[getattr(item, "uri", None) or id(item)] = item
        if len(direct) > 1:
            fail("Browser category name is ambiguous; narrow the root.", "ambiguous")
        if direct:
            return next(iter(direct.values()))
        if "root" not in action:
            fail("No exact top-level browser match; specify root for a bounded recursive preset search.", "not_found")
        pending = deque((category, 0) for category in categories)
        matches = []
        visited = set()
        count = 0
        query = action.get("name", action.get("query"))
        while pending:
            check()
            item, depth = pending.popleft()
            uri = getattr(item, "uri", None)
            identity = ("uri", uri) if uri else ("object", id(item))
            if identity in visited:
                continue
            visited.add(identity)
            count += 1
            if count > BROWSER_LIMIT or depth > 12:
                fail("Browser search was truncated; narrow the root. Uniqueness cannot be established.", "limit")
            if getattr(item, "is_loadable", False) and item.name == query:
                matches.append(item)
                if len(matches) > 1:
                    fail("Browser name is ambiguous; no item loaded.", "ambiguous")
            children = getattr(item, "children", ())
            if len(children) + len(pending) + count > BROWSER_LIMIT:
                fail("Browser search exceeds its bound; narrow the root.", "limit")
            pending.extend((child, depth + 1) for child in children)
        if not matches:
            fail("No exact loadable browser match.", "not_found")
        return matches[0]

    def _parameter(self, track, device, key):
        devices = bounded(track.devices, 256, "devices")
        matches = devices[device:device + 1] if type(device) is int else [d for d in devices if d.name == device]
        if len(matches) != 1:
            fail("Device selector must match exactly one device.")
        parameters = bounded(matches[0].parameters, 1024, "parameters")
        if type(key) is int or re.fullmatch(r"[0-9]{1,4}", key):
            index = int(key)
            found = parameters[index:index + 1]
        else:
            found = [p for p in parameters if p.name == key]
        if len(found) != 1:
            fail("Parameter selector must match exactly one parameter.")
        parameter = found[0]
        if not getattr(parameter, "is_enabled", True):
            fail("Parameter is disabled.")
        return parameter

    def _parameter_writes(self, track, action):
        writes = []
        for key, value in action["params"].items():
            parameter = self._parameter(track, action["device"], key)
            number(value, "parameter value", parameter.min, parameter.max)
            writes.append((parameter, value))
        return writes

    def _warp_mode(self, mode):
        modes = getattr(getattr(self.live_api, "Clip", None), "WarpMode", None)
        value = getattr(modes, WARP_MODES[mode], None)
        if value is None:
            fail("Requested Live.Clip.WarpMode is unavailable.", "unsupported")
        return value

    def _volume_raw(self, parameter, decibels):
        if not available(parameter, "str_for_value"):
            fail("volume_db requires Live's str_for_value conversion; use raw volume instead.", "unsupported")

        def display(raw):
            value = str(parameter.str_for_value(raw)).strip().replace("\u2212", "-")
            if re.fullmatch(r"-(?:inf|\u221e)\s*(?:dB)?", value, re.IGNORECASE):
                return -math.inf
            match = re.fullmatch(r"([+-]?[0-9]+(?:\.[0-9]+)?)\s*dB", value, re.IGNORECASE)
            if not match:
                fail("Live volume display is not a supported dB string; use raw volume.", "unsupported")
            return float(match.group(1))

        low, high = parameter.min, parameter.max
        minimum, maximum = display(low), display(high)
        if not minimum < maximum or not minimum <= decibels <= maximum:
            fail("volume_db is outside Live's displayed volume range.")
        for _ in range(40):
            middle = (low + high) / 2
            if display(middle) < decibels:
                low = middle
            else:
                high = middle
        value = min((low, high), key=lambda raw: abs(display(raw) - decibels))
        if abs(display(value) - decibels) > 0.051:
            fail("volume_db cannot be represented within 0.051 dB by Live's display conversion; use raw volume.")
        return value

    def _routing(self, track, key, label):
        choices = getattr(track, "available_" + key + "s", None)
        if choices is None or not hasattr(track, key):
            fail("Routing API is unavailable: " + key, "unsupported")
        matches = [r for r in bounded(choices, 1024, "routing choices") if r.display_name == label]
        if len(matches) != 1:
            fail("Routing label must match exactly one available " + key + ".", "ambiguous" if matches else "not_found")
        return matches[0]

    def _track_writes(self, track, action):
        writes = []
        for key in ("name", "color"):
            if key in action:
                writes.append((track, key, action[key]))
        for key, attribute in (("volume", "volume"), ("volume_db", "volume"), ("pan", "panning")):
            if key in action:
                parameter = getattr(track.mixer_device, attribute)
                value = self._volume_raw(parameter, action[key]) if key == "volume_db" else action[key]
                number(value, key, parameter.min, parameter.max)
                if not getattr(parameter, "is_enabled", True):
                    fail("Mixer parameter is disabled.")
                writes.append((parameter, "value", value))
        for key, value in action.get("sends", {}).items():
            sends = bounded(getattr(track.mixer_device, "sends", ()), 16, "sends")
            if int(key) >= len(sends):
                fail("Send index is out of range.")
            parameter = sends[int(key)]
            number(value, "send value", parameter.min, parameter.max)
            if not getattr(parameter, "is_enabled", True):
                fail("Send parameter is disabled.")
            writes.append((parameter, "value", value))
        deferred = []
        for direction in ("input", "output"):
            type_key, channel_key = direction + "_routing_type", direction + "_routing_channel"
            selected = self._routing(track, type_key, action[type_key]) if type_key in action else None
            changing = selected is not None and selected != getattr(track, type_key)
            if type_key in action:
                writes.append((track, type_key, selected))
            if channel_key in action:
                if changing:
                    deferred.append(channel_key)
                else:
                    writes.append((track, channel_key, self._routing(track, channel_key, action[channel_key])))
        return writes, deferred

    def _set_track_controls(self, track, action, effect):
        writes, deferred = self._track_writes(track, action)
        for target, key, value in writes:
            effect(lambda t=target, k=key, v=value: setattr(t, k, v))
        # Channel choices depend on the selected type: never select from stale choices.
        channels = [(key, self._routing(track, key, action[key])) for key in deferred]
        for key, value in channels:
            effect(lambda k=key, v=value: setattr(track, k, v))
        return {"track_index": list(self.song.tracks).index(track), "name": str(track.name)[:256]}

    def _slot(self, track, audio=False):
        method = "create_audio_clip" if audio else "create_clip"
        for slot in bounded(track.clip_slots, 1024, "Session slots"):
            if not slot.has_clip and available(slot, method) and available(slot, "delete_clip"):
                return slot
        fail("An empty Session slot with " + method + " and delete_clip is required.", "unsupported")

    def _preflight(self, actions, check):
        tracks = [self._record(t) for t in bounded(self.song.tracks, MAX_TRACKS, "tracks")]
        refs = {}
        plans = []
        numerator = self.song.signature_numerator
        denominator = self.song.signature_denominator
        for index, action in enumerate(actions):
            check()
            kind = action["op"]
            plan = {"action": action, "deferred": []}
            if kind == "set_transport":
                numerator = action.get("signature_numerator", numerator)
                denominator = action.get("signature_denominator", denominator)
                plan["writes"] = self._transport_values(action, numerator * 4.0 / denominator)
            elif kind in ("create_midi_track", "create_audio_track", "duplicate_track"):
                if not available(self.song, kind):
                    fail("Song API is unavailable: " + kind, "unsupported")
                if len(tracks) >= MAX_TRACKS:
                    fail("Track count limit reached.", "limit")
                if kind == "duplicate_track":
                    source = self._target(action, tracks, refs)
                    if source["object"] is not None and getattr(source["object"], "is_foldable", False):
                        fail("Group track duplication is not supported.", "unsupported")
                    plan["source"] = source
                    record = self._record(midi=source["midi"])
                    record["ranges"] = list(source["ranges"])
                    record["deferred_devices"] = True
                    position = next(i for i, t in enumerate(tracks) if t is source) + 1
                else:
                    record = self._record(midi=kind == "create_midi_track")
                    position = action.get("index", -1)
                    position = len(tracks) if position == -1 else position
                    if position > len(tracks):
                        fail("New track index is out of range.")
                tracks.insert(position, record)
                plan["record"] = record
                if CONTROL_FIELDS & set(action):
                    plan["deferred"].append("New track mixer/send ranges and routing choices checked after creation.")
                if "ref" in action:
                    if action["ref"] in refs:
                        fail("Track refs must be unique within a batch.")
                    refs[action["ref"]] = record
            else:
                record = self._target(action, tracks, refs)
                plan["record"] = record
                track = record["object"]
                if kind in ("write_arrangement_midi_clip", "place_audio_clip") and getattr(track, "is_foldable", False):
                    fail("Group tracks cannot contain clips.", "unsupported")
                if track is not None and getattr(track, "is_frozen", False):
                    fail("Target track is frozen.")
                if kind == "set_track_controls":
                    if track is not None:
                        controls = {k: v for k, v in action.items() if k not in ROUTING_FIELDS} if record["deferred_routing"] else action
                        _, channels = self._track_writes(track, controls)
                        if channels or record["deferred_routing"] and ROUTING_FIELDS & set(action):
                            plan["deferred"].append("Routing choices checked after preceding routing/device changes.")
                    else:
                        plan["deferred"].append("Track controls checked after track creation.")
                    if ROUTING_FIELDS & set(action):
                        record["deferred_routing"] = True
                elif kind == "load_device_or_preset":
                    plan["item"] = self._browser_item(action, check)
                    record["deferred_devices"] = True
                    record["deferred_routing"] = True
                elif kind == "set_device_params":
                    if track is not None and not record["deferred_devices"]:
                        self._parameter_writes(track, action)
                    else:
                        plan["deferred"].append("Device/parameter existence and ranges checked after track/device creation.")
                elif kind == "write_arrangement_midi_clip":
                    if not record["midi"]:
                        fail("MIDI clip requires a MIDI track.")
                    start, length = self._timing(action, numerator * 4.0 / denominator, True)
                    if any(n["start_beat"] + n["duration_beats"] > length for n in action["notes"]):
                        fail("A MIDI note extends beyond the requested clip length.")
                    automation.check_length(action.get("envelopes", {}), length)
                    self._overlap(record["ranges"], start, length)
                    record["ranges"].append((start, start + length))
                    if track is not None:
                        if not hasattr(track, "arrangement_clips"):
                            fail("Cannot inspect Arrangement occupancy.", "unsupported")
                        if action.get("envelopes") or any("probability" in n for n in action["notes"]) or not available(track, "create_midi_clip"):
                            if not available(track, "duplicate_clip_to_arrangement"):
                                fail("No supported Arrangement MIDI creation API.", "unsupported")
                            self._slot(track)
                    else:
                        plan["deferred"].append("New track clip API availability checked at execution.")
                    plan.update(start=start, length=length)
                elif kind == "place_audio_clip":
                    if record["midi"]:
                        fail("Audio clip requires an audio track.")
                    if track is not None:
                        if not hasattr(track, "arrangement_clips") or not available(track, "duplicate_clip_to_arrangement"):
                            fail("Audio placement requires inspectable Arrangement and duplication API.", "unsupported")
                        self._slot(track, audio=True)
                    plan["start"], _ = self._timing(action, numerator * 4.0 / denominator, False)
                    plan["deferred"].append("Imported audio extent/overlap checked in temporary Session slot before Arrangement placement.")
                if action.get("envelopes"):
                    if track is not None and not record["deferred_devices"]:
                        automation.resolve(action["envelopes"], lambda d, p: self._parameter(track, d, p), number)
                    else:
                        plan["deferred"].append("Envelope targets and value ranges checked after device creation.")
                    plan["deferred"].append("Session clip automation API checked after staging clip creation, before Arrangement duplication.")
                if any("probability" in n for n in action.get("notes", ())):
                    plan["deferred"].append("Clip.add_new_notes availability checked on created clip.")
            plans.append(plan)
        return plans

    def compose(self, params, check):
        self._syntax(params)  # Entire batch syntax, including every envelope, BEFORE any effects.
        plans = self._preflight(params["actions"], check)
        dry_run = params.get("dry_run", True)
        receipts = [{"index": i, "op": p["action"]["op"], "status": "not_run",
                     "deferred_checks": p["deferred"]} for i, p in enumerate(plans)]
        result = {"ok": True, "status": "dry_run" if dry_run else "completed",
                  "dry_run": dry_run, "receipts": receipts, "rollback": False, "unauditioned": True,
                  "validation": "Preflight complete; creation-dependent checks remain explicit in receipts."}
        if dry_run:
            return result
        undo = available(self.song, "begin_undo_step") and available(self.song, "end_undo_step")
        began = False
        try:
            for plan, receipt in zip(plans, receipts):
                touched = [False]

                def effect(callback):
                    check()
                    touched[0] = True  # A throwing Live call may already have changed state.
                    return callback()

                try:
                    check()
                    if undo and not began:
                        self.song.begin_undo_step()
                        began = True
                    receipt["result"] = self._execute(plan, effect)
                    receipt["status"] = "completed"
                except Exception as error:
                    result.update(ok=False, status="failed")
                    receipt["status"] = "failed"
                    receipt["possibly_partially_applied"] = touched[0]
                    receipt["error"] = {"code": error.code if isinstance(error, BridgeError) else "live_error",
                                        "message": error.message if isinstance(error, BridgeError) else "Live API operation failed; inspect state before retrying."}
                    break
        finally:
            if began:
                try:
                    self.song.end_undo_step()
                except Exception:
                    result["undo_warning"] = "Live could not close the undo group. No rollback was attempted."
        return result

    def _execute(self, plan, effect):
        action = plan["action"]
        kind = action["op"]
        if kind == "set_transport":
            for key, value in plan["writes"].items():
                effect(lambda k=key, v=value: setattr(self.song, k, v))
            return self.transport()
        record = plan["record"]
        if kind in ("create_midi_track", "create_audio_track", "duplicate_track"):
            before = list(self.song.tracks)
            if kind == "duplicate_track":
                source = plan["source"]["object"]
                index = before.index(source)
            else:
                index = action.get("index", -1)
            effect(lambda: getattr(self.song, kind)(index))
            added = [t for t in self.song.tracks if t not in before]
            if len(added) != 1:
                fail("Live did not produce exactly one identifiable new track.", "live_error")
            track = added[0]
            record["object"] = track
            result = self._set_track_controls(track, action, effect)
            result["track_ref"] = action.get("ref")
            return result
        track = record["object"]
        if kind == "load_device_or_preset":
            view = self.song.view
            previous = view.selected_track
            try:
                effect(lambda: setattr(view, "selected_track", track))
                effect(lambda: self.app.browser.load_item(plan["item"]))
            finally:
                # Restore temporary UI selection even if the client has disconnected.
                view.selected_track = previous
            return {"loaded": str(plan["item"].name)[:256]}
        if kind == "set_track_controls":
            return self._set_track_controls(track, action, effect)
        if kind == "set_device_params":
            writes = self._parameter_writes(track, action)
            for parameter, value in writes:
                effect(lambda p=parameter, v=value: setattr(p, "value", v))
            return {"parameters_set": len(writes)}
        return self._write_clip(track, plan, effect)

    def _write_clip(self, track, plan, effect):
        action = plan["action"]
        audio = action["op"] == "place_audio_clip"
        start = plan["start"]
        if not hasattr(track, "arrangement_clips"):
            fail("Arrangement occupancy cannot be inspected.", "unsupported")

        def check_space(length):
            clips = bounded(track.arrangement_clips, MAX_CLIPS, "Arrangement clips")
            self._overlap([(c.start_time, c.end_time) for c in clips], start, length)
            number(start + length, "clip end", 0, MAX_BEATS)

        resolved = automation.resolve(action.get("envelopes", {}), lambda d, p: self._parameter(track, d, p), number)
        probability = any("probability" in n for n in action.get("notes", ()))
        envelope_steps = [0]

        def fill(clip, length):
            automation.check_length(action.get("envelopes", {}), length)
            if not audio:
                specification = getattr(getattr(self.live_api, "Clip", None), "MidiNoteSpecification", None)
                if callable(specification) and available(clip, "add_new_notes"):
                    notes = tuple(specification(pitch=n["pitch"], start_time=n["start_beat"],
                                                duration=n["duration_beats"], velocity=n["velocity"],
                                                mute=n.get("mute", False), probability=n.get("probability", 1.0))
                                  for n in action["notes"])
                    effect(lambda: clip.add_new_notes(notes))
                else:
                    if probability or not available(clip, "set_notes"):
                        fail("This Live clip cannot write the requested notes/probability.", "unsupported")
                    notes = tuple((n["pitch"], n["start_beat"], n["duration_beats"], n["velocity"], n.get("mute", False)) for n in action["notes"])
                    effect(lambda: clip.set_notes(notes))
            if "name" in action:
                effect(lambda: setattr(clip, "name", action["name"]))
            for key in ("gain", "pitch_coarse", "pitch_fine"):
                if key in action:
                    if not hasattr(clip, key):
                        fail("Audio clip property is unavailable: " + key, "unsupported")
                    effect(lambda k=key: setattr(clip, k, action[k]))
            envelope_steps[0] = automation.write(clip, resolved, length, effect)

        if not audio and not resolved and not probability and available(track, "create_midi_clip"):
            check_space(plan["length"])
            before = list(track.arrangement_clips)
            effect(lambda: track.create_midi_clip(start, plan["length"]))
            created = [c for c in track.arrangement_clips if c not in before]
            if len(created) != 1:
                fail("Cannot identify created Arrangement clip.", "live_error")
            fill(created[0], plan["length"])
            length = plan["length"]
        else:
            if not available(track, "duplicate_clip_to_arrangement"):
                fail("Track.duplicate_clip_to_arrangement is unavailable.", "unsupported")
            slot = self._slot(track, audio)
            attempted = False
            try:
                attempted = True
                if audio:
                    effect(lambda: slot.create_audio_clip(action["path"]))
                    effect(lambda: setattr(slot.clip, "warping", True))
                    if "warp_mode" in action:
                        mode = self._warp_mode(action["warp_mode"])
                        if not hasattr(slot.clip, "warp_mode") or mode not in getattr(slot.clip, "available_warp_modes", (mode,)):
                            fail("Requested warp mode is unavailable on this audio clip.", "unsupported")
                        effect(lambda: setattr(slot.clip, "warp_mode", mode))
                    length = number(slot.clip.length, "imported clip length", 1e-9, MAX_BEATS)
                else:
                    length = plan["length"]
                    check_space(length)
                    effect(lambda: slot.create_clip(length))
                fill(slot.clip, length)
                check_space(length)
                before = list(track.arrangement_clips)
                effect(lambda: track.duplicate_clip_to_arrangement(slot.clip, start))
                if len([c for c in track.arrangement_clips if c not in before]) != 1:
                    fail("Cannot identify duplicated Arrangement clip.", "live_error")
            finally:
                # Attempt staging cleanup even after cancellation; cleanup errors surface as failure.
                if attempted and slot.has_clip:
                    slot.delete_clip()
        return {"start_beat": start, "length_beats": length, "view": "arrangement", "unauditioned": True,
                "device_envelopes": len(resolved), "envelope_steps": envelope_steps[0],
                "ramp_resolution_beats": automation.RAMP_STEP_BEATS if resolved else None}

    def lom(self, params, check=lambda: None):
        if isinstance(params, dict) and "expression" not in params:
            from .inspection import inspect
            return inspect(self, params, check)
        fields(params, {"expression"}, {"expression"})
        expression = text(params["expression"], "expression", 1024)
        try:
            root = ast.parse(expression, mode="eval").body
        except (SyntaxError, RecursionError):
            fail("Invalid read-only selector.")

        nodes = [0]

        def validate(node, depth=0):
            nodes[0] += 1
            if nodes[0] > 256:
                fail("Selector exceeds 256 nodes.")
            if depth > 16:
                fail("Selector depth exceeds 16.")
            if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
                if isinstance(node.value, float) and not math.isfinite(node.value):
                    fail("Literal numbers must be finite.")
                return
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float):
                validate(node.operand, depth + 1)
                return
            if isinstance(node, (ast.List, ast.Tuple)):
                if len(node.elts) > 32:
                    fail("Selector containers are limited to 32 items.")
                for item in node.elts:
                    validate(item, depth + 1)
                return
            if isinstance(node, ast.Dict):
                if len(node.keys) > 32 or any(not isinstance(key, ast.Constant) or not isinstance(key.value, str) for key in node.keys):
                    fail("Selector dictionaries require at most 32 literal string keys.")
                if len({key.value for key in node.keys}) != len(node.keys):
                    fail("Selector dictionary keys must be unique.")
                for item in node.values:
                    validate(item, depth + 1)
                return
            if isinstance(node, ast.Name) and node.id in ("song", "app"):
                return
            if isinstance(node, ast.Attribute) and not node.attr.startswith("_"):
                validate(node.value, depth + 1)
                return
            if isinstance(node, ast.Subscript):
                index = node.slice
                if isinstance(index, ast.Index):  # Python 3.7/3.8 AST shape.
                    index = index.value
                value = getattr(index, "value", getattr(index, "n", None))
                if isinstance(index, (getattr(ast, "Num", ast.Constant), ast.Constant)) and type(value) is int and 0 <= value <= 1023:
                    validate(node.value, depth + 1)
                    return
            fail("Only song/app, public attributes, nonnegative indices and primitive dict/list/tuple literals are allowed; no calls or Python execution.")

        validate(root)  # Validate the WHOLE AST before any property access.

        def resolve(node):
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.UnaryOp):
                return -node.operand.value
            if isinstance(node, (ast.List, ast.Tuple)):
                return [resolve(item) for item in node.elts]
            if isinstance(node, ast.Dict):
                return {key.value: resolve(item) for key, item in zip(node.keys, node.values)}
            if isinstance(node, ast.Name):
                return self.song if node.id == "song" else self.app
            if isinstance(node, ast.Attribute):
                value = getattr(resolve(node.value), node.attr)
                if callable(value):
                    fail("Methods cannot be selected or invoked.")
                return value
            index = node.slice
            if isinstance(index, ast.Index):
                index = index.value
            return resolve(node.value)[getattr(index, "value", getattr(index, "n", None))]

        truncated = [False]
        budget = [512]
        unavailable = []

        def serialize(value, depth=0, path="value"):
            check()
            budget[0] -= 1
            if budget[0] < 0 or depth > 4:
                truncated[0] = True
                return None
            if value is None or type(value) in (bool, int):
                return value
            if type(value) is float:
                return value if math.isfinite(value) else None
            if isinstance(value, str):
                truncated[0] |= len(value) > 256
                return value[:256]
            if callable(value):
                fail("Methods cannot be selected or invoked.")
            if isinstance(value, dict):
                truncated[0] |= len(value) > 32
                result = {}
                for index, (key, item) in enumerate(value.items()):
                    if index >= 32:
                        break
                    if not isinstance(key, str):
                        truncated[0] = True
                        continue
                    truncated[0] |= len(key) > 256
                    result[key[:256]] = serialize(item, depth + 1, path + "." + key[:256])
                return result
            if hasattr(value, "__len__") and hasattr(value, "__getitem__"):
                size = len(value)
                truncated[0] |= size > 32
                return [serialize(value[i], depth + 1, path + "[%d]" % i) for i in range(min(size, 32))]
            result = {"object_type": type(value).__name__}
            for key in ("name", "display_name", "class_name", "min", "max", "value", "is_enabled", "is_quantized", "display_value", "automation_state"):
                try:
                    item = getattr(value, key, None)
                except (AttributeError, RuntimeError):
                    unavailable.append({"path": path + "." + key, "code": "unavailable"})
                    continue
                if item is not None and type(item) in (str, int, float, bool):
                    result[key] = serialize(item, depth + 1, path + "." + key)
            return result

        try:
            value = resolve(root)
        except (AttributeError, IndexError, TypeError):
            fail("Selector does not resolve in this Live set.", "not_found")
        except RuntimeError:
            fail("Selected Live property is unavailable in the current state; no edits were requested.", "unavailable")
        output = {"value": serialize(value), "truncated": truncated[0], "read_only": True}
        if unavailable:
            output["unavailable"] = unavailable
        return output
