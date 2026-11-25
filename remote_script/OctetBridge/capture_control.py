"""Temporary playback/solo changes, restored on finish, expiry or disconnect.

Runs only from the Control Surface's main-thread pump. Audio recording itself is
outside Live. A lease outlives individual RPC sockets but expires after 12s.
"""
import math
import time
import uuid

from .server import BridgeError


class CaptureControl:
    def __init__(self, song):
        self.song = song
        self.active = None
        self.last = None

    def handle(self, method, params):
        if method == "capture_begin":
            return self.begin(params)
        if method == "capture_end":
            if set(params) != {"capture_id"}:
                raise BridgeError("validation", "capture_end requires capture_id.")
            if self.active is None:
                if self.last and self.last[0] == params["capture_id"]:
                    return self.last[1]
                raise BridgeError("not_found", "Capture is not active.")
            if self.active["id"] != params["capture_id"]:
                raise BridgeError("busy", "A different capture is active.")
            return self.restore()
        raise BridgeError("unsupported", "Unknown capture method.")

    def begin(self, params):
        if self.active:
            raise BridgeError("busy", "Another capture is active.")
        if set(params) - {"capture_id", "start_beat", "duration_sec", "solo_tracks"} or not {"capture_id", "start_beat", "duration_sec"} <= set(params):
            raise BridgeError("validation", "Invalid capture arguments.")
        try:
            if str(uuid.UUID(params["capture_id"])) != params["capture_id"]:
                raise ValueError()
            start, duration = params["start_beat"], params["duration_sec"]
            if any(type(n) not in (int, float) or not math.isfinite(n) for n in (start, duration)):
                raise ValueError()
            if not 0 <= start <= 1576800 or not 0 < duration <= 8:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise BridgeError("validation", "Capture requires a UUID, nonnegative start beat, and duration <=8s.")
        tracks = list(self.song.tracks)
        solos = params.get("solo_tracks")
        if solos is not None and (not isinstance(solos, list) or len(solos) > 64 or any(type(i) is not int or not 0 <= i < len(tracks) for i in solos) or len(solos) != len(set(solos))):
            raise BridgeError("validation", "solo_tracks must contain unique existing track indices.")
        if getattr(self.song, "record_mode", False) or getattr(self.song, "session_record", False):
            raise BridgeError("recording", "Stop recording before capturing a preview.")
        if getattr(self.song, "back_to_arranger", False):
            raise BridgeError("session_override", "Return to Arrangement playback before a timeline capture.")
        self.active = {"id": params["capture_id"], "deadline": time.monotonic() + duration + 4,
                       "playing": self.song.is_playing, "time": self.song.current_song_time,
                       "loop": self.song.loop, "solos": [(t, bool(t.solo)) for t in tracks],
                       "tempo": self.song.tempo, "signature": [self.song.signature_numerator, self.song.signature_denominator]}
        try:
            self.song.stop_playing()
            self.song.loop = False
            if solos is not None:
                for i, track in enumerate(tracks):
                    track.solo = i in solos
            before = time.monotonic()
            # Live starts from its marker/cached stop position, ignoring stopped seeks.
            # Start first, then seek active playback; leave the Insert Marker untouched.
            self.song.start_playing()
            self.song.current_song_time = start
            after = time.monotonic()
            return {"started_monotonic": after, "dispatch_interval_sec": after - before,
                    "tempo": self.active["tempo"], "signature": self.active["signature"],
                    "start_beat": start, "duration_sec": duration}
        except Exception:
            self.restore()
            raise

    def restore(self):
        if self.active is None:
            return None
        saved = self.active
        errors = []
        endpoint = {"end_monotonic": time.monotonic(),
                    "end_beat": self.song.current_song_time, "end_tempo": self.song.tempo,
                    "end_signature": [self.song.signature_numerator, self.song.signature_denominator]}
        def attempt(callback, field):
            try:
                callback()
            except Exception:
                errors.append(field)
        attempt(self.song.stop_playing, "stop_playing")
        for track, solo in saved["solos"]:
            attempt(lambda t=track, s=solo: setattr(t, "solo", s), "solo")
        attempt(lambda: setattr(self.song, "loop", saved["loop"]), "loop")
        if saved["playing"]:
            # Live 12.4.16 can ignore Continue just after Stop in the same tick.
            # Use Play, then seek away from the Insert Marker as in begin().
            attempt(self.song.start_playing, "resume_playing")
        attempt(lambda: setattr(self.song, "current_song_time", saved["time"]), "playhead")
        # Play is observable immediately; Stop may take effect on the next Live tick.
        if saved["playing"]:
            try:
                playing = self.song.is_playing
            except Exception:
                playing = False
            if not playing:
                errors.append("is_playing")
        self.active = None
        outcome = {"restored": not errors, "restore_errors": errors, **endpoint}
        self.last = (saved["id"], outcome)
        return outcome

    def tick(self):
        if self.active and time.monotonic() >= self.active["deadline"]:
            self.restore()
