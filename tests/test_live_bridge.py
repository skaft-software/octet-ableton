"""Fake-Live tests only: these do not qualify the bridge against a running Live set."""
import copy
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

from octet_ableton.bridge_client import BRIDGE_REVISION
from remote_script.OctetBridge import create_instance
from remote_script.OctetBridge.engine import LiveEngine
from remote_script.OctetBridge import server
from remote_script.OctetBridge.server import BridgeError, BridgeServer

TOKEN = "a" * 64


class Parameter:
    def __init__(self, name, minimum=0, maximum=1, value=0):
        self.name, self.min, self.max = name, minimum, maximum
        self.value = value
        self.is_enabled = True
        self.is_quantized = False


class Clip:
    def __init__(self, start, length, midi=True):
        self.name = "clip"
        self.start_time, self.end_time = start, start + length
        self.length = length
        self.is_midi_clip = midi
        self.warping = False
        self.notes = ()
        self.gain = 0.5
        self.pitch_coarse = 0

    def set_notes(self, notes):
        self.notes = notes


class Slot:
    def __init__(self):
        self.clip = None

    @property
    def has_clip(self):
        return self.clip is not None

    def create_clip(self, length):
        self.clip = Clip(0, length)

    def create_audio_clip(self, path):
        self.clip = Clip(0, 4, midi=False)

    def delete_clip(self):
        self.clip = None


class Track:
    def __init__(self, name="track", midi=True):
        self.name, self.has_midi_input = name, midi
        self.clip_slots = [Slot(), Slot()]
        self.arrangement_clips = []
        self.devices = [NS(name="Filter", parameters=[Parameter("Frequency", 20, 20000, 1000), Parameter("Dry/Wet")])]
        self.mixer_device = NS(volume=Parameter("Volume"), panning=Parameter("Pan", -1, 1))
        self.is_frozen = False
        self.is_foldable = False

    def create_midi_clip(self, start, length):
        self.arrangement_clips.append(Clip(start, length))  # Real API may return None.

    def duplicate_clip_to_arrangement(self, clip, start):
        result = copy.deepcopy(clip)
        result.start_time, result.end_time = start, start + clip.length
        self.arrangement_clips.append(result)


class Song:
    def __init__(self):
        self.owner = threading.get_ident()
        self.tracks = [Track()]
        self.tempo = 120
        self.signature_numerator, self.signature_denominator = 4, 4
        self._is_playing = False
        self._last_stopped_time = 40.013
        self.start_time = 0
        self.loop = False
        self.loop_start, self.loop_length = 0, 4
        self.current_song_time = 0
        self.cue_points = [NS(name="start", time=0)]
        self.view = NS(selected_track=self.tracks[0])
        self.undo = []
        self.fail_create = False

    def __getattribute__(self, name):
        if not name.startswith("_") and name != "owner":
            owner = object.__getattribute__(self, "owner")
            if threading.get_ident() != owner:
                raise AssertionError("LOM read off main thread")
        return object.__getattribute__(self, name)

    @property
    def is_playing(self):
        return self._is_playing

    @is_playing.setter
    def is_playing(self, value):
        if value and not self._is_playing:
            self.current_song_time = self.start_time
        elif not value and self._is_playing:
            self._last_stopped_time = self.current_song_time
        self._is_playing = value

    def continue_playing(self):
        if not self._is_playing:
            self.current_song_time = self._last_stopped_time
        self._is_playing = True

    def create_midi_track(self, index):
        track = Track("new")
        self.tracks.insert(len(self.tracks) if index == -1 else index, track)
        if self.fail_create:
            raise RuntimeError("Failure after insertion")

    def create_audio_track(self, index):
        self.tracks.insert(len(self.tracks) if index == -1 else index, Track("audio", midi=False))

    def duplicate_track(self, index):
        self.tracks.insert(index + 1, copy.deepcopy(self.tracks[index]))

    def begin_undo_step(self):
        self.undo.append("begin")

    def end_undo_step(self):
        self.undo.append("end")


def item(name, uri, children=(), loadable=True):
    return NS(name=name, uri=uri, children=children, is_loadable=loadable)


def application(song):
    operator = item("Operator", "operator")
    redux = item("Redux", "redux")
    browser = NS(instruments=item("Instruments", "instruments", [operator], False),
                 audio_effects=item("Audio Effects", "effects", [redux], False),
                 midi_effects=item("MIDI Effects", "midi", [], False),
                 user_library=item("User", "user", [], False))

    def load(value):
        song.view.selected_track.devices.append(NS(name=value.name, parameters=[Parameter("Gain", 0, 1)]))

    browser.load_item = load
    return NS(browser=browser)


def envelope(method="ping", params=None, **updates):
    request = {"id": str(uuid.uuid4()), "protocol": 1, "token": TOKEN, "method": method,
               "params": {} if params is None else params}
    request.update(updates)
    return request


def midi_action(**updates):
    action = {"op": "write_arrangement_midi_clip", "track_index": 0,
              "start_beat": 0, "length_beats": 4,
              "notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1, "velocity": 100}]}
    action.update(updates)
    return action


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.song = Song()
        self.app = application(self.song)
        self.engine = LiveEngine(self.song, self.app)

    def compose(self, actions, dry_run=False, check=lambda: None):
        return self.engine.handle("compose", {"actions": actions, "dry_run": dry_run}, check)

    def test_ping_revision_matches_updated_client(self):
        self.assertEqual(self.engine.handle('ping', {})['revision'], BRIDGE_REVISION)
        self.assertEqual(BRIDGE_REVISION, 6)

    def test_group_tracks_do_not_break_snapshot_or_unrelated_composition(self):
        class GroupTrack(Track):
            def __getattribute__(self, name):
                if name == "arrangement_clips":
                    raise RuntimeError("Group tracks do not support Arrangement clips")
                return super().__getattribute__(name)
        group = GroupTrack(midi=False)
        group.is_foldable = True
        self.song.tracks.insert(0, group)
        snapshot = self.engine.handle("snapshot", {})
        self.assertTrue(snapshot["tracks"][0]["group"])
        self.assertEqual(snapshot["tracks"][0]["arrangement_clips"], [])
        self.assertTrue(self.compose([{"op": "create_midi_track"}])["ok"])
        for action in (midi_action(), {"op": "place_audio_clip", "track_index": 0,
                                      "path": __file__, "start_beat": 0}):
            with self.assertRaisesRegex(BridgeError, "Group tracks"):
                self.compose([action])

    def test_optional_parameter_properties_do_not_break_legacy_read(self):
        class UnavailableDisplay(Parameter):
            @property
            def display_value(self):
                raise RuntimeError("private native error")
        self.song.tracks[0].devices[0].parameters = [UnavailableDisplay("Frequency", value=0.5)]
        result = self.engine.handle("lom", {"expression": "song.tracks[0].devices[0].parameters"})
        self.assertEqual(result["value"][0]["value"], 0.5)
        self.assertEqual(result["unavailable"], [{"path": "value[0].display_value", "code": "unavailable"}])
        self.assertNotIn("private native error", json.dumps(result))
        with self.assertRaisesRegex(BridgeError, "property is unavailable"):
            self.engine.handle("lom", {"expression": "song.tracks[0].devices[0].parameters[0].display_value"})

    def test_dry_run_defaults_and_no_mutations(self):
        result = self.engine.handle("compose", {"actions": [{"op": "create_midi_track"}, midi_action()]})
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(len(self.song.tracks), 1)
        self.assertEqual(self.song.tracks[0].arrangement_clips, [])
        self.assertEqual(self.song.undo, [])

    def test_entire_syntax_and_ranges_validated_before_any_write(self):
        bad = [midi_action(envelopes={"pitch_bend": []}), midi_action(notes=[{"pitch": True}]),
               {"op": "set_transport", "bpm": float("nan")},
               {"op": "set_transport", "bpm": 123, "surprise": 1},
               {"op": "set_device_params", "track_index": 0, "device": "Filter", "params": {"Frequency": 99999}},
               {"op": "load_device_or_preset", "track_ref": "unknown", "name": "Operator"}]
        for action in bad:
            with self.subTest(action=action), self.assertRaises(BridgeError):
                self.compose([{"op": "create_midi_track"}, action])
            self.assertEqual(len(self.song.tracks), 1)
            self.assertEqual(self.song.undo, [])

    def test_full_music_batch_refs_indices_and_deferred_parameters(self):
        result = self.compose([
            {"op": "create_midi_track", "name": "lead", "ref": "lead"},
            {"op": "create_audio_track", "index": 0, "name": "audio"},
            {"op": "load_device_or_preset", "track_ref": "lead", "name": "Operator"},
            {"op": "set_device_params", "track_ref": "lead", "device": "Operator", "params": {"Gain": 0.7}},
            {"op": "write_arrangement_midi_clip", "track_ref": "lead", "start_bar": 3, "length_bars": 1,
             "notes": [{"pitch": 72, "start_beat": 1, "duration_beats": 2, "velocity": 90, "mute": False}]},
            {"op": "set_transport", "bpm": 155, "playhead_bar": 3, "loop_start_bar": 3,
             "loop_length_bars": 1, "loop": True, "playing": True},
        ])
        self.assertTrue(result["ok"])
        lead = self.song.tracks[2]
        self.assertEqual(lead.name, "lead")
        self.assertEqual(lead.devices[-1].parameters[0].value, 0.7)
        self.assertEqual(lead.arrangement_clips[0].start_time, 8)
        self.assertEqual(lead.arrangement_clips[0].notes, ((72, 1, 2, 90, False),))
        self.assertEqual(self.song.tempo, 155)
        self.assertEqual(self.song.current_song_time, 8)
        self.assertEqual(self.song.undo, ["begin", "end"])

    def test_transport_seek_and_play_ignores_marker_and_cached_stopped_position(self):
        self.song.start_time = 2
        for playing in (False, True):
            for position, expected in (({'playhead_bar': 3}, 8), ({'playhead_beat': 8}, 8),
                                       ({'playhead_bar': 1}, 0), ({'playhead_beat': 0}, 0)):
                with self.subTest(playing=playing, position=position):
                    self.song.is_playing = playing
                    self.song._last_stopped_time = 40.013
                    self.song.current_song_time = 40.013
                    result = self.compose([{'op': 'set_transport', **position, 'playing': True}])
                    self.assertTrue(result['ok'], result)
                    self.assertEqual(self.song.current_song_time, expected)
                    self.assertTrue(self.song.is_playing)
                    self.assertEqual(self.song.start_time, 2)
                    self.assertEqual(result['receipts'][0]['result']['playhead_beat'], expected)

    def test_transport_seek_in_new_signature_and_stop_or_preview(self):
        action = {'op': 'set_transport', 'signature_numerator': 7,
                  'signature_denominator': 8, 'playhead_bar': 5, 'playing': True}
        self.assertEqual(self.compose([action], dry_run=True)['status'], 'dry_run')
        self.assertFalse(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 0)
        self.assertEqual(self.song.signature_numerator, 4)
        self.assertTrue(self.compose([action])['ok'])
        self.assertEqual(self.song.current_song_time, 14)
        self.assertTrue(self.song.is_playing)
        self.assertTrue(self.compose([{'op': 'set_transport', 'playhead_beat': 6, 'playing': False}])['ok'])
        self.assertFalse(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 6)

    def test_cancellation_between_play_and_seek_reports_partial_effect(self):
        self.song.start_time = 2

        def cancel_after_play():
            if self.song.is_playing:
                raise InterruptedError('cancelled after play')

        result = self.compose([{'op': 'set_transport', 'playhead_bar': 3, 'playing': True}],
                              check=cancel_after_play)
        self.assertFalse(result['ok'])
        self.assertFalse(result['rollback'])
        self.assertTrue(result['receipts'][0]['possibly_partially_applied'])
        self.assertTrue(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 2)
        self.assertEqual(self.song.undo, ['begin', 'end'])

    def test_transport_seek_only_preserves_stopped_state_and_marker(self):
        self.song.start_time = 2
        self.assertTrue(self.compose([{'op': 'set_transport', 'playhead_bar': 3}])['ok'])
        self.assertFalse(self.song.is_playing)
        self.assertEqual(self.song.current_song_time, 8)
        self.assertEqual(self.song.start_time, 2)

    def test_transport_play_only_keeps_normal_insert_marker_behavior(self):
        self.song.start_time = 8
        self.song.current_song_time = 16
        self.assertTrue(self.compose([{'op': 'set_transport', 'playing': True}])['ok'])
        self.assertEqual(self.song.current_song_time, 8)
        self.assertTrue(self.song.is_playing)

    def test_duplicate_ref_identity_for_identical_new_track_records(self):
        result = self.compose([{"op": "create_midi_track", "ref": "a", "name": "a"},
                               {"op": "create_midi_track", "ref": "b", "name": "b"},
                               {"op": "duplicate_track", "track_ref": "b", "ref": "copy"},
                               {"op": "set_device_params", "track_ref": "copy", "device": 0, "params": {"0": 500}}])
        self.assertTrue(result["ok"])
        self.assertEqual(self.song.tracks[-1].name, "b")
        self.assertEqual(self.song.tracks[-1].devices[0].parameters[0].value, 500)

    def test_partial_failure_stops_and_closes_undo(self):
        self.song.fail_create = True
        result = self.compose([{"op": "set_transport", "bpm": 130}, {"op": "create_midi_track"},
                               {"op": "set_transport", "bpm": 140}])
        self.assertEqual([r["status"] for r in result["receipts"]], ["completed", "failed", "not_run"])
        self.assertTrue(result["receipts"][1]["possibly_partially_applied"])
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.song.tracks), 2)
        self.assertEqual(self.song.tempo, 130)
        self.assertEqual(self.song.undo, ["begin", "end"])

    def test_cancellation_between_effects_is_cooperative_not_rollback(self):
        def check():
            if len(self.song.tracks) > 1:
                raise BridgeError("deadline", "expired")
        result = self.compose([{"op": "create_midi_track", "name": "not assigned"},
                               {"op": "set_transport", "bpm": 140}], check=check)
        self.assertEqual(len(self.song.tracks), 2)
        self.assertEqual(self.song.tracks[-1].name, "new")
        self.assertEqual([r["status"] for r in result["receipts"]], ["failed", "not_run"])
        self.assertTrue(result["receipts"][0]["possibly_partially_applied"])

    def test_overlap_existing_and_planned_rejected_before_write(self):
        self.song.tracks[0].arrangement_clips.append(Clip(2, 4))
        with self.assertRaises(BridgeError) as caught:
            self.compose([{"op": "set_transport", "bpm": 130}, midi_action()])
        self.assertEqual(caught.exception.code, "overlap")
        self.assertEqual(self.song.tempo, 120)
        self.song.tracks[0].arrangement_clips.clear()
        with self.assertRaises(BridgeError):
            self.compose([midi_action(), midi_action(start_beat=2)])
        self.assertEqual(self.song.tracks[0].arrangement_clips, [])

    def test_session_midi_fallback_cleanup_and_failure_cleanup(self):
        track = self.song.tracks[0]
        track.create_midi_clip = None
        self.assertTrue(self.compose([midi_action()])["ok"])
        self.assertFalse(track.clip_slots[0].has_clip)
        self.assertEqual(track.arrangement_clips[0].notes[0][0], 60)
        track.duplicate_clip_to_arrangement = lambda clip, start: (_ for _ in ()).throw(RuntimeError("fail"))
        result = self.compose([midi_action(start_beat=8)])
        self.assertFalse(result["ok"])
        self.assertFalse(track.clip_slots[0].has_clip)

    def test_audio_staging_checks_actual_overlap_and_cleans_slot(self):
        self.song.tracks[0] = Track(midi=False)
        track = self.song.tracks[0]
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            action = {"op": "place_audio_clip", "track_index": 0, "path": audio.name, "start_beat": 8}
            result = self.compose([action])
            self.assertTrue(result["ok"])
            self.assertTrue(track.arrangement_clips[0].warping)
            self.assertFalse(track.clip_slots[0].has_clip)
            result = self.compose([action])
            self.assertEqual(result["receipts"][0]["error"]["code"], "overlap")
            self.assertEqual(len(track.arrangement_clips), 1)
            self.assertFalse(track.clip_slots[0].has_clip)

    def test_parameter_values_are_real_live_domain(self):
        self.assertTrue(self.compose([{"op": "set_device_params", "track_index": 0, "device": 0,
                                       "params": {"Frequency": 2800, "1": 0.65}}])["ok"])
        self.assertEqual(self.song.tracks[0].devices[0].parameters[0].value, 2800)

    def test_signature_updates_apply_to_subsequent_bar_actions(self):
        result = self.compose([{"op": "set_transport", "signature_numerator": 3, "signature_denominator": 8},
                               {"op": "write_arrangement_midi_clip", "track_index": 0,
                                "start_bar": 3, "length_bars": 2, "notes": []}])
        self.assertTrue(result["ok"])
        self.assertEqual(self.song.tracks[0].arrangement_clips[0].start_time, 3)
        self.assertEqual(self.song.tracks[0].arrangement_clips[0].length, 3)

    def test_browser_direct_match_skips_large_library_and_refuses_ambiguity(self):
        self.app.browser.user_library.children = [item("Folder", "folder", [item(str(i), str(i)) for i in range(5000)], False)]
        self.assertTrue(self.compose([{"op": "load_device_or_preset", "track_index": 0, "name": "Operator"}])["ok"])
        self.app.browser.audio_effects.children.append(item("Operator", "other"))
        with self.assertRaises(BridgeError) as caught:
            self.compose([{"op": "load_device_or_preset", "track_index": 0, "name": "Operator"}])
        self.assertEqual(caught.exception.code, "ambiguous")

    def test_browser_recursive_search_bounded_and_explicit(self):
        self.app.browser.user_library.children = [item("Folder", "folder", [item("Preset", "preset")], False)]
        with self.assertRaises(BridgeError):
            self.compose([{"op": "load_device_or_preset", "track_index": 0, "query": "Preset"}])
        self.assertTrue(self.compose([{"op": "load_device_or_preset", "track_index": 0,
                                       "query": "Preset", "root": "user_library"}])["ok"])

    def test_lom_safe_selectors_and_bounds(self):
        result = self.engine.handle("lom", {"expression": "song.tracks[0].devices[0].parameters"})
        self.assertEqual(result["value"][0]["name"], "Frequency")
        for expression in ("song.stop_playing()", "song.__class__", "song.tracks[-1]", "song.tracks[1024]",
                           "[x for x in song.tracks]", "__import__('os')", "song.tempo + 1", "song.tracks[:1]",
                           "song.tracks[True]", "song.create_midi_track"):
            with self.subTest(expression=expression), self.assertRaises(BridgeError):
                self.engine.handle("lom", {"expression": expression})
        self.song.tracks = [Track() for _ in range(40)]
        result = self.engine.handle("lom", {"expression": "song.tracks"})
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["value"]), 32)

    def test_snapshot_reports_limits_and_unauditioned_capabilities(self):
        self.song.tracks = [Track() for _ in range(70)]
        result = self.engine.handle("snapshot", {})
        self.assertTrue(result["truncated"])
        self.assertIn("tracks", result["truncated_paths"])
        self.assertFalse(result["capabilities"]["live_qualified"])
        self.assertFalse(result["capabilities"]["envelopes"]["supported"])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.port_patch = patch.object(server, "PORT", 0)
        self.port_patch.start()
        self.song = Song()
        self.bridge = BridgeServer(LiveEngine(self.song, application(self.song)), TOKEN)
        self.bridge.start()
        self.addCleanup(self.bridge.close)
        self.addCleanup(self.port_patch.stop)

    def connect(self, request=None, raw=None):
        sock = socket.create_connection(self.bridge.address, timeout=2)
        self.addCleanup(sock.close)
        sock.sendall(raw if raw is not None else json.dumps(request).encode() + b"\n")
        return sock

    def wait(self, predicate):
        end = time.monotonic() + 2
        while not predicate():
            if time.monotonic() > end:
                self.fail("Timed out waiting for test condition")
            time.sleep(0.005)

    def receive(self, sock):
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
        return json.loads(data)

    def test_main_thread_contract_and_actual_json_roundtrip(self):
        request = envelope("compose", {"actions": [{"op": "create_midi_track"}], "dry_run": False})
        sock = self.connect(request)
        self.wait(lambda: not self.bridge._queue.empty())
        self.assertEqual(len(self.song.tracks), 1)
        self.bridge.pump()
        reply = self.receive(sock)
        self.assertEqual(reply["id"], request["id"])
        self.assertEqual(reply["protocol"], 1)
        self.assertTrue(reply["result"]["ok"])
        self.assertEqual(len(self.song.tracks), 2)
        self.assertNotIn(TOKEN, json.dumps(reply))
        self.assertEqual(sock.recv(1), b"")

    def test_parent_client_interoperates_with_server(self):
        from octet_ableton.bridge_client import BridgeClient
        results, errors = [], []
        def call():
            try:
                results.append(BridgeClient({"token": TOKEN, "port": self.bridge.address[1]}).call("ping"))
            except Exception as error:
                errors.append(error)
        client = threading.Thread(target=call)
        client.start()
        self.wait(lambda: not self.bridge._queue.empty())
        self.bridge.pump()
        client.join(2)
        self.assertFalse(client.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(results[0]["bridge"], "OctetBridge")

    def test_bind_failure_does_not_touch_existing_listener(self):
        other = BridgeServer(LiveEngine(self.song, application(self.song)), TOKEN)
        with patch.object(server, "PORT", self.bridge.address[1]):
            with self.assertRaises(BridgeError) as caught:
                other.start()
        self.assertEqual(caught.exception.code, "bind")
        other.close()
        sock = self.connect(envelope())
        self.wait(lambda: not self.bridge._queue.empty())
        self.bridge.pump()
        self.assertEqual(self.receive(sock)["result"]["bridge"], "OctetBridge")

    def test_authentication_wrong_protocol_no_lom_and_matching_id(self):
        for updates, code in (({"token": "b" * 64}, "unauthorized"), ({"protocol": 2}, "protocol")):
            request = envelope(**updates)
            reply = self.receive(self.connect(request))
            self.assertEqual(reply["id"], request["id"])
            self.assertEqual(reply["error"]["code"], code)
            self.assertTrue(self.bridge._queue.empty())

    def test_deadline_before_pump_prevents_mutation(self):
        with patch.object(server, "REQUEST_TIMEOUT", 0.05):
            sock = self.connect(envelope("compose", {"actions": [{"op": "create_midi_track"}], "dry_run": False}))
            self.wait(lambda: not self.bridge._queue.empty())
            reply = self.receive(sock)
        self.assertEqual(reply["error"]["code"], "deadline")
        self.bridge.pump()
        self.assertEqual(len(self.song.tracks), 1)

    def test_disconnected_queued_request_is_not_executed(self):
        sock = self.connect(envelope("compose", {"actions": [{"op": "create_midi_track"}], "dry_run": False}))
        self.wait(lambda: not self.bridge._queue.empty())
        sock.close()
        self.bridge.pump()
        self.assertEqual(len(self.song.tracks), 1)
        self.wait(lambda: not self.bridge._clients)

    def test_oversize_frames_duplicate_keys_and_multiple_requests(self):
        for raw, code in ((b" " * (server.MAX_FRAME + 1), "frame_too_large"),
                          (b'{"token":"x","token":"y"}\n', "invalid_request"),
                          (json.dumps(envelope()).encode() + b"\n{}\n", "invalid_request")):
            reply = self.receive(self.connect(raw=raw))
            self.assertEqual(reply["error"]["code"], code)
        self.assertTrue(self.bridge._queue.empty())

    def test_idle_and_eof_connections_release_slots(self):
        sock = socket.create_connection(self.bridge.address, timeout=2)
        self.wait(lambda: len(self.bridge._clients) == 1)
        sock.close()
        self.wait(lambda: not self.bridge._clients)
        with patch.object(server, "READ_TIMEOUT", 0.05):
            sock = self.connect(raw=b"{")
            reply = self.receive(sock)
        self.assertEqual(reply["error"]["code"], "deadline")
        self.wait(lambda: not self.bridge._clients)

    def test_connection_cap_and_shutdown_no_worker_leaks(self):
        sockets = [socket.create_connection(self.bridge.address, timeout=2) for _ in range(server.MAX_CONNECTIONS)]
        for sock in sockets:
            self.addCleanup(sock.close)
        self.wait(lambda: len(self.bridge._clients) == server.MAX_CONNECTIONS)
        extra = socket.create_connection(self.bridge.address, timeout=2)
        self.addCleanup(extra.close)
        self.assertEqual(extra.recv(1), b"")
        self.bridge.close()
        self.assertFalse(self.bridge._thread.is_alive())
        self.assertFalse(self.bridge._workers)
        self.assertFalse(self.bridge._clients)

    def test_background_pump_refused(self):
        errors = []
        def run():
            try:
                self.bridge.pump()
            except RuntimeError as error:
                errors.append(str(error))
        thread = threading.Thread(target=run)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)

    def test_response_size_cap(self):
        self.bridge.engine = NS(handle=lambda *args: {"text": "x" * server.MAX_FRAME})
        sock = self.connect(envelope())
        self.wait(lambda: not self.bridge._queue.empty())
        self.bridge.pump()
        reply = self.receive(sock)
        self.assertEqual(reply["error"]["code"], "response_too_large")


class EntryPointTests(unittest.TestCase):
    def test_tick_is_scheduled_only_by_host_and_disconnect_stops_pump(self):
        song = Song()
        scheduled = []
        owner = threading.get_ident()
        logs = []
        class Surface:
            def __init__(self, instance):
                pass
            def song(self):
                return song
            def application(self):
                return application(song)
            def schedule_message(self, ticks, callback):
                self_test.assertEqual(threading.get_ident(), owner)
                scheduled.append(callback)
            def log_message(self, message):
                logs.append(message)
            def disconnect(self):
                pass
        self_test = self
        modules = {"_Framework": NS(), "_Framework.ControlSurface": NS(ControlSurface=Surface)}
        with patch.dict("sys.modules", modules), patch.object(server, "PORT", 0), patch.object(server, "load_config", return_value={"token": TOKEN}):
            surface = create_instance(None)
            self.assertEqual(len(scheduled), 1)
            scheduled.pop()()
            self.assertEqual(len(scheduled), 1)
            surface.disconnect()
            scheduled.pop()()
            self.assertEqual(scheduled, [])
            self.assertNotIn(TOKEN, " ".join(logs))

    def test_config_rejects_non_loopback_port_and_invalid_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bridge.json")
            for change in ({"port": 9999}, {"protocol": True}, {"token": "short"}):
                config = {"protocol": 1, "token": TOKEN, "port": 9878}
                config.update(change)
                with open(path, "w") as stream:
                    json.dump(config, stream)
                with self.assertRaises(BridgeError):
                    server.load_config(path)


if __name__ == "__main__":
    unittest.main()
