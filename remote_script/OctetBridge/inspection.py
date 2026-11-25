"""Bounded, fresh, main-thread read-only views; no snapshot or mutable-value cache.

Session defaults to the first 64 tracks. Device defaults to the first 256
parameters (all 195 Operator parameters fit); offset/limit pages larger devices.
Selectors are exact names or integer indices, never numeric-string indices.
Batch syntax is validated before any Live access. Each result is {ok, result}
or {ok, error}; cancellation checks run outside read-error handlers.
"""
import json
import math

from .server import BridgeError

FIELDS = ("name", "min", "max", "value", "is_enabled", "is_quantized",
          "display_value", "automation_state", "value_items")
MAX_BYTES = 480 * 1024  # Leave room for the bridge envelope within its 512 KiB frame.


def _fail(message, code="validation"):
    raise BridgeError(code, message)


def _index(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        _fail(label + " must be a bounded nonnegative integer.")


def _selector(value, maximum, label):
    if type(value) is int:
        _index(value, maximum, label)
    elif not isinstance(value, str) or not value or len(value) > 256 or "\x00" in value:
        _fail(label + " must be an exact name or nonnegative integer index.")


def _syntax(query):
    if not isinstance(query, dict):
        _fail("Each query must be an object.")
    view = query.get("view")
    if view == "session":
        if set(query) - {"view", "track_indices"}:
            _fail("Unknown session fields.")
        if "track_indices" in query:
            indices = query["track_indices"]
            if not isinstance(indices, list) or len(indices) > 64:
                _fail("track_indices must be a list of at most 64 indices.")
            for index in indices:
                _index(index, 511, "track_index")
    elif view == "device":
        if (set(query) - {"view", "track_index", "device", "parameters", "fields", "offset", "limit"}
                or not {"track_index", "device"} <= set(query)):
            _fail("Unknown or missing device fields.")
        _index(query["track_index"], 511, "track_index")
        _selector(query["device"], 255, "device")
        if "parameters" in query:
            selectors = query["parameters"]
            if not isinstance(selectors, list) or len(selectors) > 256:
                _fail("parameters must be a list of at most 256 selectors.")
            if {"offset", "limit"} & set(query):
                _fail("parameters cannot be combined with pagination.")
            for selector in selectors:
                _selector(selector, 1023, "parameter")
        projected = query.get("fields", ["name", "value"])
        if (not isinstance(projected, list) or len(projected) > len(FIELDS)
                or any(not isinstance(field, str) or field not in FIELDS for field in projected)
                or len(set(projected)) != len(projected)):
            _fail("fields must be a unique list of supported parameter fields.")
        _index(query.get("offset", 0), 1023, "offset")
        _index(query.get("limit", 256), 256, "limit")
        if query.get("limit", 256) == 0:
            _fail("limit must be at least 1.")
    else:
        _fail("view must be session or device.")


def _bounded(values, maximum, label):
    if len(values) > maximum:
        _fail(label + " exceeds the inspection bound.", "limit")
    return values


def _scalar(value):
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, str) and len(value) <= 256:
        return value
    raise ValueError("Unavailable primitive")


def _field(parameter, name):
    # Only property access/conversion is guarded: no cancellation check here.
    value = getattr(parameter, name)
    if name == "value_items":
        if isinstance(value, str) or not hasattr(value, "__len__") or not hasattr(value, "__getitem__") or len(value) > 128:
            raise ValueError("Unavailable value items")
        return [_scalar(value[i]) for i in range(len(value))]
    if name == "automation_state" and isinstance(value, int):
        return int(value)
    return _scalar(value)


def _resolve(objects, selector, label):
    if type(selector) is int:
        if selector >= len(objects):
            _fail(label + " not found.", "not_found")
        return selector
    matches = [index for index, obj in enumerate(objects) if obj.name == selector]
    if not matches:
        _fail(label + " not found.", "not_found")
    if len(matches) != 1:
        _fail(label + " name is ambiguous; use an index.", "ambiguous")
    return matches[0]


def _session(engine, query):
    tracks = _bounded(engine.song.tracks, 512, "tracks")
    indices = query.get("track_indices", list(range(min(64, len(tracks)))))
    summaries = []
    for index in indices:
        yield
        if index >= len(tracks):
            _fail("Track not found.", "not_found")
        track = tracks[index]
        group = bool(getattr(track, "is_foldable", False))
        devices = []
        for device_index, device in enumerate(_bounded(track.devices, 256, "devices")):
            yield
            devices.append({"index": device_index, "name": _scalar(device.name),
                            "parameter_count": len(device.parameters)})
        # Reading arrangement_clips on a group raises in Live, even when empty.
        clip_count = 0 if group else len(track.arrangement_clips)
        summaries.append({"index": index, "name": _scalar(track.name), "group": group,
                          "devices": devices, "arrangement_clip_count": clip_count})
    yield
    return {"view": "session", "transport": {key: _scalar(value) for key, value in engine.transport().items()},
            "track_count": len(tracks), "tracks": summaries,
            "truncated": "track_indices" not in query and len(tracks) > 64}


def _device(engine, query):
    tracks = _bounded(engine.song.tracks, 512, "tracks")
    track_index = query["track_index"]
    if track_index >= len(tracks):
        _fail("Track not found.", "not_found")
    devices = _bounded(tracks[track_index].devices, 256, "devices")
    device_index = _resolve(devices, query["device"], "Device")
    device = devices[device_index]
    parameters = _bounded(device.parameters, 1024, "parameters")
    if "parameters" in query:
        indices = []
        for selector in query["parameters"]:
            yield
            indices.append(_resolve(parameters, selector, "Parameter"))
    else:
        offset = query.get("offset", 0)
        indices = list(range(offset, min(len(parameters), offset + query.get("limit", 256))))
    projected = query.get("fields", ["name", "value"])
    rows, unavailable = [], []
    for index in indices:
        yield
        row = [index]
        for field in projected:
            yield
            try:
                value = _field(parameters[index], field)
            except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError):
                value = None
                unavailable.append({"parameter_index": index, "field": field, "code": "unavailable"})
            row.append(value)
        rows.append(row)
    next_offset = None
    if "parameters" not in query and indices and indices[-1] + 1 < len(parameters):
        next_offset = indices[-1] + 1
    return {"view": "device", "track_index": track_index, "device_index": device_index,
            "device_name": _scalar(device.name), "parameter_count": len(parameters),
            "columns": ["index"] + projected, "rows": rows, "unavailable": unavailable,
            "next_offset": next_offset}


def _execute(engine, query, check, batch):
    iterator = _session(engine, query) if query["view"] == "session" else _device(engine, query)
    while True:
        check()  # Outside all handlers: even RuntimeError cancellation propagates.
        try:
            next(iterator)
        except StopIteration as done:
            return {"ok": True, "result": done.value}
        except BridgeError as error:
            if not batch or error.code in ("cancelled", "deadline"):
                raise
            return {"ok": False, "error": {"code": error.code, "message": error.message}}
        except (AttributeError, RuntimeError, IndexError, TypeError, ValueError, OverflowError):
            if not batch:
                _fail("Live inspection failed.", "live_error")
            return {"ok": False, "error": {"code": "live_error", "message": "Live inspection failed."}}


def inspect(engine, params, check=lambda: None):
    """Run one view, or {queries: [1..16 views]}, sequentially on Live's thread."""
    if not isinstance(params, dict):
        _fail("Inspection params must be an object.")
    batch = "queries" in params
    if batch:
        queries = params["queries"]
        if set(params) != {"queries"} or not isinstance(queries, list) or not 1 <= len(queries) <= 16:
            _fail("Batch must contain only queries, a list of 1..16 views.")
    else:
        queries = [params]
    for query in queries:
        _syntax(query)
    results, used = [], 0
    for query in queries:
        entry = _execute(engine, query, check, batch)
        size = len(json.dumps(entry, ensure_ascii=True, allow_nan=False).encode("utf-8"))
        if used + size > MAX_BYTES:
            if not batch:
                _fail("Inspection output exceeds its bound; narrow fields or selectors.", "limit")
            entry = {"ok": False, "error": {"code": "limit", "message": "Inspection output exceeds its bound; narrow fields or selectors."}}
            size = len(json.dumps(entry))
        used += size
        results.append(entry)
    return {"read_only": True, "ok": all(entry["ok"] for entry in results), "results": results} if batch else {"read_only": True, **results[0]["result"]}
