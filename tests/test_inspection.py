"""API-shaped fake tests; no Live qualification or mutations."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from remote_script.OctetBridge.engine import LiveEngine
from remote_script.OctetBridge.inspection import inspect
from remote_script.OctetBridge.server import BridgeError
from test_live_bridge import Parameter, Song, Track, application


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.song = Song()
        self.engine = LiveEngine(self.song, application(self.song))
        self.query = {"view": "device", "track_index": 0, "device": "Filter"}

    def test_invalid_syntax_prevalidated_without_live_access(self):
        invalid = [None, {}, {"view": "session", "extra": 1},
                   {"view": "session", "track_indices": [True]},
                   {"view": "session", "track_indices": [-1]},
                   {"view": "session", "track_indices": list(range(65))},
                   {"queries": []}, {"queries": [{"view": "session"}] * 17},
                   {"queries": [{"view": "session"}], "view": "session"}]
        for update in ({"track_index": True}, {"track_index": -1},
                       {"device": False}, {"device": -1}, {"device": float("nan")},
                       {"parameters": [True]}, {"parameters": [-1]},
                       {"parameters": [float("inf")]}, {"parameters": [0] * 257},
                       {"fields": ["secret"]}, {"fields": [["value"]]},
                       {"fields": ["name", "name"]}, {"fields": "name"},
                       {"offset": -1}, {"limit": True}, {"limit": 0},
                       {"limit": 257}, {"parameters": [], "offset": 0}, {"extra": 1}):
            invalid.append(dict(self.query, **update))
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(BridgeError):
                inspect(None, query)
        with self.assertRaises(BridgeError):
            inspect(None, {"queries": [{"view": "session"}, dict(self.query, fields=["bad"])]})

    def test_session_is_compact_and_group_arrangement_is_never_read(self):
        class GroupTrack(Track):
            def __getattribute__(self, name):
                if name in ("arrangement_clips", "mixer_device", "clip_slots"):
                    raise AssertionError("Broad track inspection")
                return super().__getattribute__(name)

        group = GroupTrack()
        group.is_foldable = True
        group.devices = [NS(name="Device", parameters=[NS()])]
        self.song.tracks.insert(0, group)
        with patch.object(self.engine, "snapshot", side_effect=AssertionError("snapshot")):
            result = inspect(self.engine, {"view": "session", "track_indices": [0]})
        self.assertEqual(result["tracks"], [{"index": 0, "name": "track", "group": True,
                                           "devices": [{"index": 0, "name": "Device", "parameter_count": 1}],
                                           "arrangement_clip_count": 0}])
        self.assertEqual(result["transport"]["bpm"], 120)
        self.assertEqual(self.song.undo, [])

    def test_operator_discovery_and_values_are_fresh(self):
        parameters = [Parameter("Param %d" % index, value=index / 195) for index in range(195)]
        self.song.tracks[0].devices = [NS(name="Operator", parameters=parameters)]
        query = dict(self.query, device=0)
        result = inspect(self.engine, query)
        self.assertEqual(result["parameter_count"], 195)
        self.assertEqual(result["columns"], ["index", "name", "value"])
        self.assertEqual(len(result["rows"]), 195)
        self.assertIsNone(result["next_offset"])
        self.assertLess(len(json.dumps(result)), 15000)
        parameters[194].value = 0.125
        self.assertEqual(inspect(self.engine, query)["rows"][-1], [194, "Param 194", 0.125])
        self.assertEqual(self.song.undo, [])

    def test_selected_projection_never_reads_unrequested_property(self):
        class NarrowParameter:
            name = "Only"
            min = -2
            max = 2

            @property
            def value(self):
                raise AssertionError("Unrequested value read")

        self.song.tracks[0].devices[0].parameters = [NarrowParameter()]
        result = inspect(self.engine, dict(self.query, parameters=["Only"], fields=["max", "min"]))
        self.assertEqual(result["columns"], ["index", "max", "min"])
        self.assertEqual(result["rows"], [[0, 2, -2]])
        self.assertEqual(inspect(self.engine, dict(self.query, fields=[]))["rows"], [[0]])

    def test_optional_field_runtime_error_is_local_and_redacted(self):
        class FragileParameter(Parameter):
            @property
            def display_value(self):
                raise RuntimeError("secret exception text")

        parameter = FragileParameter("Fragile", value=0.25)
        parameter.value_items = ("off", "on")
        parameter.automation_state = 1
        self.song.tracks[0].devices[0].parameters = [parameter, Parameter("Other")]
        result = inspect(self.engine, dict(self.query, fields=["display_value", "value", "value_items", "automation_state"]))
        self.assertEqual(result["rows"][0], [0, None, 0.25, ["off", "on"], 1])
        self.assertIn({"parameter_index": 0, "field": "display_value", "code": "unavailable"}, result["unavailable"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertNotIn("secret", json.dumps(result))

    def test_nonfinite_or_unbounded_fields_are_unavailable(self):
        parameter = self.song.tracks[0].devices[0].parameters[0]
        parameter.value = float("nan")
        parameter.display_value = "x" * 257
        parameter.value_items = tuple(range(129))
        result = inspect(self.engine, dict(self.query, parameters=[0], fields=["value", "display_value", "value_items"]))
        self.assertEqual(result["rows"], [[0, None, None, None]])
        self.assertEqual(len(result["unavailable"]), 3)
        json.dumps(result, allow_nan=False)

    def test_bounds_pagination_and_exact_name_resolution(self):
        device = self.song.tracks[0].devices[0]
        device.parameters = [Parameter(str(index)) for index in range(1024)]
        result = inspect(self.engine, self.query)
        self.assertEqual(len(result["rows"]), 256)
        self.assertEqual(result["next_offset"], 256)
        page = inspect(self.engine, dict(self.query, offset=1000, limit=64))
        self.assertEqual(len(page["rows"]), 24)
        self.assertIsNone(page["next_offset"])
        device.parameters[2].name = "0"
        with self.assertRaises(BridgeError) as error:
            inspect(self.engine, dict(self.query, parameters=["0"]))
        self.assertEqual(error.exception.code, "ambiguous")
        device.parameters.append(Parameter("overflow"))
        with self.assertRaises(BridgeError) as error:
            inspect(self.engine, self.query)
        self.assertEqual(error.exception.code, "limit")

    def test_batch_partial_read_error_and_missing_selection(self):
        class BrokenDevice:
            @property
            def parameters(self):
                raise RuntimeError("do not leak")

        self.song.tracks[0].devices.append(BrokenDevice())
        result = inspect(self.engine, {"queries": [dict(self.query, device=1),
                                                   dict(self.query, device=0),
                                                   dict(self.query, device=20),
                                                   dict(self.query, device=0)]})
        self.assertEqual([row["ok"] for row in result["results"]], [False, True, False, True])
        self.assertEqual(result["results"][0]["error"]["code"], "live_error")
        self.assertEqual(result["results"][2]["error"]["code"], "not_found")
        self.assertNotIn("do not leak", json.dumps(result))

    def test_cancellation_propagates_outside_read_handlers(self):
        for exception in (BridgeError("cancelled", "cancel"), BridgeError("deadline", "deadline"), RuntimeError("cancel")):
            checks = []

            def check():
                checks.append(None)
                if len(checks) == 4:
                    raise exception

            with self.subTest(exception=exception), self.assertRaises(type(exception)) as caught:
                inspect(self.engine, {"queries": [self.query, self.query]}, check)
            self.assertIs(caught.exception, exception)
            self.assertEqual(len(checks), 4)

    def test_output_budget_returns_batch_error_and_continues(self):
        with patch("remote_script.OctetBridge.inspection.MAX_BYTES", 1):
            result = inspect(self.engine, {"queries": [self.query, self.query]})
            self.assertEqual([item["error"]["code"] for item in result["results"]], ["limit", "limit"])
            with self.assertRaises(BridgeError):
                inspect(self.engine, self.query)

    def test_python37_syntax(self):
        source = Path(__file__).parents[1] / "remote_script/OctetBridge/inspection.py"
        ast.parse(source.read_text(), feature_version=(3, 7))


if __name__ == "__main__":
    unittest.main()
