import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from octet_ableton.presentation import ToolRun, compact_compose, encoded


def batch(count=57):
    return {"ok": True, "status": "completed", "dry_run": False, "rollback": False,
            "unauditioned": True, "receipts": [
                {"index": i, "op": "write_arrangement_midi_clip", "status": "completed",
                 "deferred_checks": ["Clip APIs checked at execution."],
                 "result": {"start_beat": i * 4, "length_beats": 4, "view": "arrangement", "unauditioned": True}}
                for i in range(count)]}


class PresentationTests(unittest.TestCase):
    def test_compact_receipts_keep_counts_and_private_full_evidence(self):
        value = batch()
        with tempfile.TemporaryDirectory() as directory:
            output = compact_compose(value, Path(directory))
            self.assertEqual(output["completed_actions"], 57)
            self.assertEqual(output["arrangement_span_beats"], [0, 228])
            self.assertLess(len(encoded(output)), len(encoded(value)) // 5)
            path = Path(output["receipt_path"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), value)
            self.assertNotEqual(compact_compose(value, Path(directory))["receipt_path"], str(path))

    def test_partial_effects_and_not_run_remain_visible(self):
        value = batch(3)
        value.update(ok=False, status="failed")
        value["receipts"][1].update(status="failed", possibly_partially_applied=True, error={"code": "live_error", "message": "failed"})
        value["receipts"][1].pop("result")
        value["receipts"][2].update(status="not_run")
        value["receipts"][2].pop("result")
        with tempfile.TemporaryDirectory() as directory:
            result = compact_compose(value, Path(directory))
        self.assertEqual(result["completed_actions"], 1)
        self.assertTrue(result["failures"][0]["possibly_partially_applied"])
        self.assertEqual(result["not_run_actions"], [2])
        self.assertFalse(result["rollback"])

    def test_dry_run_deduplicates_deferred_checks(self):
        value = batch(3)
        value.update(dry_run=True, status="dry_run")
        for receipt in value["receipts"]:
            receipt["status"] = "not_run"
            receipt.pop("result")
        with tempfile.TemporaryDirectory() as directory:
            result = compact_compose(value, Path(directory))
        self.assertEqual(result["completed_actions"], 0)
        self.assertEqual(result["deferred_checks"][0]["actions"], [0, 1, 2])

    def test_storage_error_does_not_hide_applied_receipts(self):
        value = batch(1)
        with patch("builtins.open", side_effect=OSError("private info")), tempfile.TemporaryDirectory() as directory:
            result = compact_compose(value, Path(directory))
        self.assertTrue(result["ok"])
        self.assertEqual(result["receipts"], value["receipts"])
        self.assertNotIn("private info", str(result))

    def test_metrics_count_attempts_and_payload_not_provider_tokens(self):
        bridge = Mock()
        bridge.call.return_value = {"ok": True}
        run = ToolRun(bridge)
        run.call("lom", {"view": "session"})
        bridge.call.side_effect = ValueError("failure")
        with self.assertRaises(ValueError):
            run.call("lom")
        result = run.finish({"ok": True})
        self.assertEqual(result["metrics"]["bridge_calls"], 2)
        self.assertEqual(result["metrics"]["payload_bytes"], len(encoded({"ok": True})))
        self.assertGreaterEqual(result["metrics"]["elapsed_ms"], 0)
