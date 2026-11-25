"""Compact model results; full receipts remain in private host-generation scratch."""
import json
import os
import time
import uuid
from collections import Counter


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


class ToolRun:
    """Local wall time and attempted bridge calls, not provider token accounting."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.started = time.perf_counter()
        self.calls = 0

    def call(self, method, params=None, *, check_cancel=lambda: None):
        self.calls += 1
        return self.bridge.call(method, params, check_cancel=check_cancel)

    def finish(self, value):
        return {**value, "metrics": {
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "bridge_calls": self.calls,
            "payload_bytes": len(encoded(value)),
        }}


def compact_compose(value, scratch):
    receipts = value.get("receipts", [])
    summary = {key: value[key] for key in
               ("ok", "status", "dry_run", "rollback", "unauditioned", "undo_warning") if key in value}
    summary["actions"] = dict(Counter(r["op"] for r in receipts))
    summary["completed_actions"] = sum(r["status"] == "completed" for r in receipts)
    summary["total_actions"] = len(receipts)
    created, spans, warnings, deferred = [], [], [], {}
    for receipt in receipts:
        result = receipt.get("result", {})
        if receipt["status"] != "completed" and receipt.get("error"):
            warnings.append(receipt)
        if receipt["op"] in ("create_midi_track", "create_audio_track", "duplicate_track") and result:
            created.append(result)
        if "start_beat" in result and "length_beats" in result:
            spans.append((result["start_beat"], result["start_beat"] + result["length_beats"]))
        for check in receipt.get("deferred_checks", []):
            deferred.setdefault(check, []).append(receipt["index"])
    if created:
        summary["created_tracks"] = created
        summary["index_scope"] = "Track indices are receipt-time; inspect session after insertions."
    if spans:
        summary["clips_written"] = len(spans)
        summary["arrangement_span_beats"] = [min(s[0] for s in spans), max(s[1] for s in spans)]
    if warnings:
        summary["failures"] = warnings
    if value.get("dry_run") and deferred:
        summary["deferred_checks"] = [{"check": check, "actions": indices} for check, indices in deferred.items()]
    if not value.get("ok", True):
        summary["not_run_actions"] = [r["index"] for r in receipts if r["status"] == "not_run"]
        summary["next_step"] = "Inspect affected tracks before retrying; completed or partially applied effects were not rolled back."
    # A receipt-storage failure after mutation must never look like an unapplied batch.
    try:
        scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = scratch / ("compose-" + uuid.uuid4().hex + ".json")
        with open(path, "xb", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            stream.write(encoded(value))
        summary["receipt_path"] = str(path)
    except OSError:
        summary["receipt_storage_error"] = "Could not store full receipt. This does not undo any effects."
        summary["receipts"] = receipts
    return summary
