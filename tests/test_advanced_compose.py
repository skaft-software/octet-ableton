"""Contract/cleanup tests against API-shaped fakes, NOT real-Live qualification.

Positive compose examples appear inline, including real parameter units, incoming
curve direction, exact route labels, and Live MidiNoteSpecification probability.
"""
import copy
import math
import tempfile
import unittest
from types import SimpleNamespace as NS

from remote_script.OctetBridge.engine import LiveEngine
from remote_script.OctetBridge.server import BridgeError
from remote_script.OctetBridge import automation
from test_live_bridge import Clip, Parameter, Slot, Song, Track, application, midi_action


LIVE_API = NS(Clip=NS(MidiNoteSpecification=lambda **kwargs: NS(**kwargs),
                      WarpMode=NS(beats=101, tones=102, texture=103, repitch=104, complex=105, complex_pro=106)))


class Envelope:
    def __init__(self):
        self.steps = []

    def insert_step(self, beat, duration, value):
        self.steps.append((beat, duration, value))


class ModernClip(Clip):
    def __init__(self, start, length, midi=True):
        super().__init__(start, length, midi)
        self.envelopes = []
        self.warp_mode = LIVE_API.Clip.WarpMode.beats
        self.available_warp_modes = list(vars(LIVE_API.Clip.WarpMode).values())
        self.pitch_fine = 0

    def add_new_notes(self, notes):
        self.notes = notes

    def create_automation_envelope(self, parameter):
        envelope = Envelope()
        self.envelopes.append((parameter, envelope))
        return envelope


class ModernSlot(Slot):
    def create_clip(self, length):
        self.clip = ModernClip(0, length)

    def create_audio_clip(self, path):
        self.clip = ModernClip(0, 4, midi=False)


class ModernTrack(Track):
    def __init__(self, midi=True):
        super().__init__(midi=midi)
        self.clip_slots = [ModernSlot(), ModernSlot()]
        self.color = 0
        self.mixer_device.sends = [Parameter("A"), Parameter("B")]
        # Deliberately nonlinear; a linear dB mapping would fail the test.
        self.mixer_device.volume.str_for_value = lambda raw: "-inf dB" if raw == 0 else "%.2f dB" % (20 * math.log10(raw) + 6)
        for direction in ("input", "output"):
            routes = [NS(display_name="None"), NS(display_name="External")]
            channels = [NS(display_name="1/2"), NS(display_name="3/4")]
            setattr(self, "available_" + direction + "_routing_types", routes)
            setattr(self, direction + "_routing_type", routes[0])
            setattr(self, "available_" + direction + "_routing_channels", channels)
            setattr(self, direction + "_routing_channel", channels[0])

    def create_midi_clip(self, start, length):
        self.arrangement_clips.append(ModernClip(start, length))


class ModernSong(Song):
    def __init__(self):
        super().__init__()
        self.tracks = [ModernTrack()]
        self.view.selected_track = self.tracks[0]

    def create_midi_track(self, index):
        self.tracks.insert(len(self.tracks) if index == -1 else index, ModernTrack())

    def create_audio_track(self, index):
        self.tracks.insert(len(self.tracks) if index == -1 else index, ModernTrack(midi=False))


def envelopes(points=None, device="Filter", param="Frequency"):
    return {"device_params": [{"device": device, "param": param,
                               "points": points if points is not None else [
                                   {"beat": 0, "value": 200},
                                   {"beat": 1, "value": 4000, "curve": "ramp"},
                                   {"beat": 2, "value": 800, "curve": "step"}]}]}


class AdvancedComposeTests(unittest.TestCase):
    def setUp(self):
        self.song = ModernSong()
        self.app = application(self.song)
        self.engine = LiveEngine(self.song, self.app, live_api=LIVE_API)
        self.track = self.song.tracks[0]

    def compose(self, actions, dry_run=False, check=lambda: None):
        return self.engine.handle("compose", {"actions": actions, "dry_run": dry_run}, check)

    def assert_untouched(self):
        self.assertEqual(len(self.song.tracks), 1)
        self.assertEqual(self.song.undo, [])
        self.assertEqual(self.track.arrangement_clips, [])
        self.assertTrue(all(not s.has_clip for s in self.track.clip_slots))

    def test_track_creation_and_existing_controls(self):
        controls = {"name": "Lead", "color": 0x3366AA, "volume_db": -6, "pan": -0.25,
                    "sends": {"0": 0.3, "1": 0.6}, "input_routing_type": "External",
                    "input_routing_channel": "3/4", "output_routing_type": "External",
                    "output_routing_channel": "1/2"}
        result = self.compose([{"op": "create_midi_track", "ref": "lead", **controls},
                               {"op": "set_track_controls", "track_ref": "lead", "pan": 0.5}])
        self.assertTrue(result["ok"], result)
        track = self.song.tracks[-1]
        self.assertEqual(track.name, "Lead")
        self.assertEqual(track.color, 0x3366AA)
        self.assertAlmostEqual(track.mixer_device.volume.value, 10 ** (-12 / 20), places=3)
        self.assertEqual(track.mixer_device.panning.value, 0.5)
        self.assertEqual([p.value for p in track.mixer_device.sends], [0.3, 0.6])
        self.assertEqual(track.input_routing_type.display_name, "External")
        self.assertEqual(track.input_routing_channel.display_name, "3/4")

    def test_control_dry_run_and_invalid_values_no_writes(self):
        action = {"op": "set_track_controls", "track_index": 0, "volume_db": -9, "sends": {"1": 0.4}}
        self.assertTrue(self.compose([action], dry_run=True)["ok"])
        self.assert_untouched()
        for updates in ({"volume": 0.5}, {"volume_db": 10}, {"sends": {"2": 0.4}},
                        {"sends": {"01": 0.5}}, {"color": True}, {"color": 0x1000000}):
            with self.subTest(updates=updates), self.assertRaises(BridgeError):
                self.compose([{"op": "create_midi_track"}, {**action, **updates}])
            self.assert_untouched()

    def test_volume_db_requires_parseable_display_conversion(self):
        parameter = self.track.mixer_device.volume
        for formatter in (None, lambda raw: str(raw), lambda raw: "0 dB"):
            parameter.str_for_value = formatter
            with self.subTest(formatter=formatter), self.assertRaises(BridgeError):
                self.compose([{"op": "set_track_controls", "track_index": 0, "volume_db": -6}])
            self.assert_untouched()

    def test_ambiguous_routing_rejected_not_first_match(self):
        self.track.available_output_routing_types.append(NS(display_name="External"))
        with self.assertRaises(BridgeError) as error:
            self.compose([{"op": "create_midi_track"}, {"op": "set_track_controls", "track_index": 0,
                                                       "output_routing_type": "External"}])
        self.assertEqual(error.exception.code, "ambiguous")
        self.assert_untouched()

    def test_channel_resolution_occurs_after_type_change(self):
        class RoutedTrack(ModernTrack):
            @property
            def available_output_routing_channels(self):
                return [NS(display_name="New" if self.output_routing_type.display_name == "External" else "Old")]

            @available_output_routing_channels.setter
            def available_output_routing_channels(self, value):
                pass
        track = RoutedTrack()
        self.song.tracks[0] = track
        result = self.compose([{"op": "set_track_controls", "track_index": 0,
                                "output_routing_type": "External", "output_routing_channel": "New"}])
        self.assertTrue(result["ok"], result)
        self.assertEqual(track.output_routing_channel.display_name, "New")
        self.assertTrue(result["receipts"][0]["deferred_checks"])
        self.song.tracks[0] = RoutedTrack()
        result = self.compose([{"op": "set_track_controls", "track_index": 0, "output_routing_type": "External"},
                               {"op": "set_track_controls", "track_index": 0, "output_routing_channel": "New"}])
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.song.tracks[0].output_routing_channel.display_name, "New")

    def test_missing_envelope_api_cleans_staging(self):
        self.track.clip_slots = [Slot()]
        result = self.compose([midi_action(envelopes=envelopes())])
        self.assertFalse(result["ok"])
        self.assertEqual(result["receipts"][0]["error"]["code"], "unsupported")
        self.assertEqual(self.track.arrangement_clips, [])
        self.assertFalse(self.track.clip_slots[0].has_clip)

    def test_audio_envelope_outside_import_length_cleans_staging(self):
        self.track.has_midi_input = False
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            result = self.compose([{"op": "place_audio_clip", "track_index": 0, "path": audio.name,
                                    "start_beat": 8, "envelopes": envelopes([
                                        {"beat": 0, "value": 200}, {"beat": 5, "value": 800}])}])
        self.assertFalse(result["ok"])
        self.assertEqual(self.track.arrangement_clips, [])
        self.assertFalse(self.track.clip_slots[0].has_clip)

    def test_session_envelopes_are_complete_before_arrangement_duplication(self):
        observed = []
        duplicate = self.track.duplicate_clip_to_arrangement
        def inspect(clip, start):
            observed.append((len(clip.notes), copy.deepcopy(clip.envelopes[0][1].steps)))
            duplicate(clip, start)
        self.track.duplicate_clip_to_arrangement = inspect
        result = self.compose([midi_action(start_beat=8, envelopes=envelopes())])
        self.assertTrue(result["ok"], result)
        self.assertEqual(observed[0][0], 1)
        steps = observed[0][1]
        self.assertEqual(len(steps), 98)
        self.assertEqual(steps[0], (0, 1 / 96, 200))
        self.assertAlmostEqual(steps[48][2], 2100)
        self.assertEqual(steps[-2], (1, 1, 4000))
        self.assertEqual(steps[-1], (2, 2, 800))
        self.assertEqual(self.track.arrangement_clips[0].start_time, 8)
        self.assertTrue(all(not slot.has_clip for slot in self.track.clip_slots))
        self.assertEqual(result["receipts"][0]["result"]["envelope_steps"], 98)

    def test_all_envelope_syntax_and_ranges_validated_before_batch_mutation(self):
        invalid = [None, {}, {"pitch_bend": []}, {"cc": {}},
                   envelopes([{ "beat": 1, "value": 200}]),
                   envelopes([{ "beat": 0, "value": 200}, {"beat": 0, "value": 300}]),
                   envelopes([{ "beat": 0, "value": 200, "curve": "bezier"}]),
                   envelopes([{ "beat": 0, "value": True}]),
                   envelopes([{ "beat": 0, "value": float("nan")}]),
                   envelopes([{ "beat": 0, "value": 200, "extra": 0}]),
                   envelopes([{ "beat": 0, "value": 200}, {"beat": 5, "value": 300}]),
                   envelopes([{ "beat": 0, "value": 0.25}]),  # Not a normalized frequency!
                   envelopes(device="Missing"), envelopes(param="Missing")]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(BridgeError):
                self.compose([{"op": "create_midi_track"}, midi_action(envelopes=value)])
            self.assert_untouched()

    def test_duplicate_envelope_targets_and_quantized_ramps_rejected(self):
        value = envelopes()
        value["device_params"].append({**value["device_params"][0], "device": 0, "param": 0})
        with self.assertRaises(BridgeError):
            self.compose([midi_action(envelopes=value)])
        self.track.devices[0].parameters[0].is_quantized = True
        with self.assertRaises(BridgeError):
            self.compose([midi_action(envelopes=envelopes())])
        self.assert_untouched()

    def test_envelope_dry_run_and_meter_relative_lengths(self):
        result = self.compose([midi_action(envelopes=envelopes())], dry_run=True)
        self.assertTrue(result["ok"])
        self.assert_untouched()
        result = self.compose([{"op": "set_transport", "signature_numerator": 3, "signature_denominator": 8},
                               {"op": "write_arrangement_midi_clip", "track_index": 0, "start_bar": 3,
                                "length_bars": 2, "notes": [], "envelopes": envelopes()}])
        self.assertTrue(result["ok"], result)
        clip = self.track.arrangement_clips[0]
        self.assertEqual((clip.start_time, clip.length), (3, 3))
        self.assertEqual(clip.envelopes[0][1].steps[-1], (2, 1, 800))

    def test_envelope_failure_and_cancellation_clean_staging_without_arrangement(self):
        for mode in ("insert", "cancel", "duplicate"):
            self.setUp()
            original = self.track.clip_slots[0].create_clip
            def create(length):
                original(length)
                if mode == "insert":
                    def broken(parameter):
                        return NS(insert_step=lambda *args: (_ for _ in ()).throw(RuntimeError("insertion failed")))
                    self.track.clip_slots[0].clip.create_automation_envelope = broken
            self.track.clip_slots[0].create_clip = create
            if mode == "duplicate":
                self.track.duplicate_clip_to_arrangement = lambda *args: (_ for _ in ()).throw(RuntimeError("failed"))
            def check():
                clip = self.track.clip_slots[0].clip
                if mode == "cancel" and clip and clip.envelopes and clip.envelopes[0][1].steps:
                    raise BridgeError("cancelled", "cancelled")
            result = self.compose([midi_action(envelopes=envelopes())], check=check)
            self.assertFalse(result["ok"], mode)
            self.assertFalse(self.track.clip_slots[0].has_clip, mode)
            self.assertEqual(self.track.arrangement_clips, [], mode)
            self.assertEqual(self.song.undo, ["begin", "end"])

    def test_envelope_resolution_after_device_creation(self):
        result = self.compose([{"op": "create_midi_track", "ref": "new"},
                               {"op": "load_device_or_preset", "track_ref": "new", "name": "Operator"},
                               {"op": "write_arrangement_midi_clip", "track_ref": "new", "start_beat": 0,
                                "length_beats": 4, "notes": [], "envelopes": envelopes([
                                    {"beat": 0, "value": 0.2}, {"beat": 2, "value": 0.8}], device="Operator", param="Gain")}])
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.song.tracks[-1].arrangement_clips[0].envelopes[0][0].name, "Gain")

    def test_ramp_limits_reject_before_writes_and_single_point_holds(self):
        with self.assertRaises(BridgeError) as error:
            self.compose([midi_action(length_beats=100, envelopes=envelopes([
                {"beat": 0, "value": 200}, {"beat": 100, "value": 400, "curve": "ramp"}]))])
        self.assertEqual(error.exception.code, "limit")
        self.assert_untouched()
        self.assertEqual(list(automation.steps([{"beat": 0, "value": 200}], 4)), [(0, 4, 200)])

    def test_probability_uses_specification_and_modern_note_writer(self):
        notes = [{"pitch": 60, "start_beat": 0, "duration_beats": 1, "velocity": 96, "probability": 0.25}]
        result = self.compose([midi_action(notes=notes)])
        self.assertTrue(result["ok"], result)
        note = self.track.arrangement_clips[0].notes[0]
        self.assertEqual((note.pitch, note.start_time, note.duration, note.velocity, note.probability, note.mute),
                         (60, 0, 1, 96, 0.25, False))
        self.assertFalse(self.track.clip_slots[0].has_clip)

    def test_probability_missing_api_never_silently_dropped(self):
        action = midi_action(notes=[{"pitch": 60, "start_beat": 0, "duration_beats": 1, "velocity": 96, "probability": 0.5}])
        self.engine.live_api = None
        with self.assertRaises(BridgeError):
            self.compose([{"op": "create_midi_track"}, action])
        self.assert_untouched()
        self.engine.live_api = LIVE_API
        self.track.clip_slots = [Slot()]
        result = self.compose([action])
        self.assertFalse(result["ok"])
        self.assertFalse(self.track.clip_slots[0].has_clip)
        self.assertEqual(self.track.arrangement_clips, [])

    def test_audio_warp_enum_pitch_gain_and_device_envelopes(self):
        self.track.has_midi_input = False
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            result = self.compose([{"op": "place_audio_clip", "track_index": 0, "path": audio.name,
                                    "start_beat": 8, "warp_mode": "complex_pro", "pitch_coarse": -7,
                                    "pitch_fine": 13, "gain": 0.4, "envelopes": envelopes()}])
        self.assertTrue(result["ok"], result)
        clip = self.track.arrangement_clips[0]
        self.assertEqual(clip.warp_mode, LIVE_API.Clip.WarpMode.complex_pro)
        self.assertEqual((clip.pitch_coarse, clip.pitch_fine, clip.gain), (-7, 13, 0.4))
        self.assertEqual(len(clip.envelopes), 1)
        self.assertFalse(self.track.clip_slots[0].has_clip)

    def test_lom_primitive_containers_and_no_execution(self):
        expression = "{'tempo': song.tempo, 'params': song.tracks[0].devices[0].parameters, 'literal': [None, True, -6, (1, 2)]}"
        result = self.engine.handle("lom", {"expression": expression})
        self.assertEqual(result["value"]["tempo"], 120)
        self.assertEqual(result["value"]["params"][0]["min"], 20)
        self.assertEqual(result["value"]["literal"], [None, True, -6, [1, 2]])
        self.assertTrue(result["read_only"])
        for expression in ("{'x': song.tempo, 'y': song.stop_playing()}", "{**song}",
                           "{'x': 1, 'x': 2}", "{song.tempo: 1}", "[x for x in song.tracks]",
                           "[-song.tempo]", "[1e999]", "[song.__class__]"):
            with self.subTest(expression=expression), self.assertRaises(BridgeError):
                self.engine.handle("lom", {"expression": expression})

    def test_snapshot_metadata_and_routing_objects(self):
        state = self.engine.handle("snapshot", {})
        parameter = state["tracks"][0]["devices"][0]["parameters"][0]
        self.assertEqual((parameter["name"], parameter["min"], parameter["max"]), ("Frequency", 20, 20000))
        state = self.engine.handle("lom", {"expression": "song.tracks[0].available_output_routing_types"})
        self.assertEqual(state["value"][1]["display_name"], "External")


if __name__ == "__main__":
    unittest.main()
