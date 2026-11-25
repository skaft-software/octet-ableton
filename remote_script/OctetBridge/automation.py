"""Session-first parameter envelopes; no MIDI CC/pitch-bend API is invented.

Compose schema (both MIDI and audio placement):
  envelopes={"device_params": [{"device": "Filter", "param": "Frequency",
      "points": [{"beat": 0, "value": 200},
                 {"beat": 2, "value": 4000, "curve": "ramp"},
                 {"beat": 3, "value": 800, "curve": "step"}]}]}
Beats are clip-relative quarter notes, values are actual parameter min/max units.
A point's curve describes the segment ARRIVING at that point; default is step.
Ramps are explicitly rasterized at <=1/96 quarter-note intervals using insert_step;
this is NOT a claim of native continuous/Bezier interpolation. First point must
be at zero; last value holds to clip end. Quantized parameters only allow steps.

API evidence (runtime reference, not a claim of Live qualification):
https://midiremotescripts.structure-void.com/reference/live12/Live.Clip.runtime/#create_automation_envelope
https://midiremotescripts.structure-void.com/reference/live12/Live.Envelope.runtime/#insert_step
Live 11 exposes the same insert_step(time, length, value) on AutomationEnvelope.
"""
import math

from .server import BridgeError

MAX_ENVELOPES = 32
MAX_POINTS = 512
MAX_STEPS = 8192  # Entire clip, including all rasterized envelopes.
RAMP_STEP_BEATS = 1.0 / 96


def fail(message, code="validation"):
    raise BridgeError(code, message)


def validate(envelopes, fields, number, text, max_beats):
    if isinstance(envelopes, dict) and set(envelopes) & {"pitch_bend", "cc", "midi_cc"}:
        fail("MIDI pitch-bend/CC envelopes are not exposed by the verified Live API. Automate an exposed instrument parameter instead.", "unsupported")
    fields(envelopes, {"device_params"}, {"device_params"})
    entries = envelopes["device_params"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENVELOPES:
        fail("device_params must contain 1..32 envelopes.")
    total = 0
    for entry in entries:
        fields(entry, {"device", "param", "points"}, {"device", "param", "points"})
        for key, bound in (("device", 255), ("param", 1023)):
            if type(entry[key]) is int:
                number(entry[key], key, 0, bound, True)
            else:
                text(entry[key], key)
        points = entry["points"]
        if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
            fail("points must contain 1..512 beat/value objects.")
        previous = None
        for point in points:
            fields(point, {"beat", "value", "curve"}, {"beat", "value"})
            number(point["beat"], "envelope beat", 0, max_beats)
            number(point["value"], "envelope value", -1e15, 1e15)
            if point.get("curve", "step") not in ("step", "ramp"):
                fail("Envelope curve must be step or ramp.")
            if previous is None:
                if point["beat"] != 0:
                    fail("The first envelope point must be at beat zero.")
            else:
                if point["beat"] <= previous["beat"]:
                    fail("Envelope points must have strictly increasing beats.")
                if point.get("curve", "step") == "ramp":
                    total += math.ceil((point["beat"] - previous["beat"]) / RAMP_STEP_BEATS)
            total += 1
            previous = point
    if total > MAX_STEPS:
        fail("Envelope ramps exceed the 8192-step per-clip limit; shorten or simplify them.", "limit")


def check_length(envelopes, length):
    for entry in envelopes.get("device_params", ()):
        if entry["points"][-1]["beat"] > length:
            fail("An envelope point extends beyond the clip length.")


def resolve(envelopes, resolve_parameter, number):
    """Resolve ALL targets/values before creating even the temporary clip."""
    resolved = []
    seen = []
    for entry in envelopes.get("device_params", ()):
        parameter = resolve_parameter(entry["device"], entry["param"])
        if parameter in seen:
            fail("An envelope parameter may only be specified once per clip.")
        seen.append(parameter)
        for point in entry["points"]:
            number(point["value"], "envelope value", parameter.min, parameter.max)
            if getattr(parameter, "is_quantized", False) and point.get("curve") == "ramp":
                fail("Ramps require a non-quantized parameter.")
        resolved.append((parameter, entry["points"]))
    return resolved


def steps(points, length):
    for previous, point in zip(points, points[1:]):
        duration = point["beat"] - previous["beat"]
        count = max(1, math.ceil(duration / RAMP_STEP_BEATS)) if point.get("curve", "step") == "ramp" else 1
        for index in range(count):
            start = previous["beat"] + duration * index / count
            end = previous["beat"] + duration * (index + 1) / count
            value = previous["value"] + (point["value"] - previous["value"]) * index / count
            yield start, end - start, value
    last = points[-1]
    # A zero-duration insert at clip end records the requested terminal value.
    yield last["beat"], length - last["beat"], last["value"]


def write(clip, resolved, length, effect):
    if not resolved:
        return 0
    if not callable(getattr(clip, "create_automation_envelope", None)):
        fail("Clip.create_automation_envelope is unavailable.", "unsupported")
    envelopes = []
    for parameter, points in resolved:
        existing = clip.automation_envelope(parameter) if callable(getattr(clip, "automation_envelope", None)) else None
        envelope = existing if existing is not None else effect(lambda p=parameter: clip.create_automation_envelope(p))
        if not callable(getattr(envelope, "insert_step", None)):
            fail("Envelope.insert_step is unavailable.", "unsupported")
        envelopes.append((envelope, points))
    inserted = 0
    for envelope, points in envelopes:
        for beat, duration, value in steps(points, length):
            effect(lambda e=envelope, b=beat, d=duration, v=value: e.insert_step(b, d, v))
            inserted += 1
    return inserted
