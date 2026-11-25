"""Bounded PCM measurements; supplied tempo is a grid assumption, not detection.

Samples are floating-point PCM (full scale = 1), shaped frames or frames/channels.
Channel powers are combined, never waveforms: opposite-phase stereo is not silence.
Pitch output describes spectral peaks, not a verified fundamental or musical key.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np

MAX_SECONDS = 8.0
MAX_EVENTS = 64
BANDS = {
    "sub_20_90hz": (20, 90),
    "low_90_300hz": (90, 300),
    "mid_300_4khz": (300, 4000),
    "high_4_20khz": (4000, 20000),
}


def _noop() -> None:
    pass


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def validate_timing(
    tempo: float | None = None,
    signature: Sequence[int] = (4, 4),
    origin_sec: float = 0.0,
) -> tuple[float | None, tuple[int, int], float]:
    if tempo is not None:
        tempo = _number(tempo, "tempo")
        if not 20 <= tempo <= 999:
            raise ValueError("tempo must be between 20 and 999 quarter-note BPM")
    if (not isinstance(signature, (tuple, list)) or len(signature) != 2
            or any(type(v) is not int for v in signature)
            or not 1 <= signature[0] <= 32
            or signature[1] not in (1, 2, 4, 8, 16, 32)):
        raise ValueError("signature must be [numerator 1..32, denominator 1/2/4/8/16/32]")
    origin_sec = _number(origin_sec, "origin_sec")
    if origin_sec < 0:
        raise ValueError("origin_sec must be nonnegative")
    return tempo, (signature[0], signature[1]), origin_sec


def bar_to_seconds(
    bar: float, tempo: float, signature: Sequence[int] = (4, 4), origin_sec: float = 0.0,
) -> float:
    """One-based (possibly fractional) bars; tempo always counts quarter notes."""
    tempo, signature, origin_sec = validate_timing(tempo, signature, origin_sec)
    if tempo is None:
        raise ValueError("bar ranges require explicitly supplied tempo")
    bar = _number(bar, "bar")
    if bar < 1:
        raise ValueError("bar must be at least 1")
    return origin_sec + (bar - 1) * (signature[0] * 4 / signature[1]) * 60 / tempo


def _db(power: float) -> float | None:
    return round(10 * math.log10(power), 3) if power > 0 else None


def _spectrum(samples: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """One-sided, Hann-window-corrected mean-square power per FFT bin."""
    n = len(samples)
    window = np.hanning(n) if n > 3 else np.ones(n)
    transform = np.fft.rfft(samples * window[:, None], axis=0)
    power = np.mean(np.abs(transform) ** 2, axis=1) / (n * np.sum(window ** 2))
    power[1:-1 if n % 2 == 0 else None] *= 2
    return np.fft.rfftfreq(n, 1 / sample_rate), power


def _position(seconds: float, tempo: float, signature: tuple[int, int], origin: float) -> dict:
    quarter = (seconds - origin) * tempo / 60
    per_bar = signature[0] * 4 / signature[1]
    bar = math.floor(quarter / per_bar + 1e-9)
    within = max(0.0, quarter - bar * per_bar)
    beat = math.floor(within + 1e-9)
    return {"bar": bar + 1, "quarter_beat": beat + 1,
            "sixteenth": round((within - beat) * 4 + 1, 6)}


def _pitches(frequencies: np.ndarray, power: np.ndarray) -> list[dict]:
    """Prominent spectral peaks with concentration-based confidence, not f0."""
    total = float(np.sum(power))
    if total <= 1e-16 or len(power) < 3:
        return []
    peaks = np.flatnonzero((power[1:-1] > power[:-2]) & (power[1:-1] >= power[2:])) + 1
    peaks = [i for i in peaks if 35 <= frequencies[i] <= 4000]
    result = []
    for i in sorted(peaks, key=lambda i: power[i], reverse=True)[:3]:
        concentration = float(np.sum(power[max(0, i - 1):i + 2]) / total)
        if concentration < 0.05:
            continue
        # Parabolic interpolation in log power reduces FFT-bin quantization.
        a, b, c = np.log(np.maximum(power[i - 1:i + 2], 1e-30))
        denominator = a - 2 * b + c
        offset = float(np.clip(0.5 * (a - c) / denominator, -0.5, 0.5)) if denominator else 0.0
        hz = float(frequencies[i] + offset * (frequencies[1] - frequencies[0]))
        midi = 69 + 12 * math.log2(hz / 440)
        nearest = round(midi)
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        result.append({"hz": round(hz, 2), "midi": round(midi, 2),
                       "note": f"{names[nearest % 12]}{nearest // 12 - 1}",
                       "confidence": round(min(1.0, concentration), 3)})
    return result


def analyze_pcm(
    samples: np.ndarray,
    sample_rate: int,
    *,
    start_sec: float = 0.0,
    tempo: float | None = None,
    signature: Sequence[int] = (4, 4),
    origin_sec: float = 0.0,
    check_cancel: Callable[[], None] = _noop,
) -> dict:
    """Analyze <=8s of PCM with bounded events and JSON-safe silence values.

    With tempo, events use globally anchored sixteenth-note cells. Partial edge
    cells are retained. Without tempo, events are measured in 25ms windows only;
    no bars or guessed BPM are asserted. dBFS silence is null, not -Infinity.
    """
    check_cancel()
    tempo, signature, origin_sec = validate_timing(tempo, signature, origin_sec)
    start_sec = _number(start_sec, "start_sec")
    if start_sec < 0:
        raise ValueError("start_sec must be nonnegative")
    if type(sample_rate) is not int or not 1 <= sample_rate <= 384000:
        raise ValueError("sample_rate must be an integer between 1 and 384000")
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim == 1:
        samples = samples[:, None]
    if (samples.ndim != 2 or not 1 <= samples.shape[1] <= 8
            or not 1 <= len(samples) <= sample_rate * MAX_SECONDS):
        raise ValueError("PCM must contain 1..8 channels and more than zero, at most 8 seconds")
    if not np.all(np.isfinite(samples)):
        raise ValueError("PCM contains nonfinite samples")
    check_cancel()
    end_sec = start_sec + len(samples) / sample_rate
    channel_power = np.mean(samples ** 2, axis=0)
    channel_peak = np.max(np.abs(samples), axis=0)

    # Welch-style spectral average with shorter FFTs for very short slices.
    fft_size = min(8192, len(samples))
    summed = None
    count = 0
    for offset in range(0, max(1, len(samples) - fft_size + 1), max(1, fft_size // 2)):
        check_cancel()
        frequencies, power = _spectrum(samples[offset:offset + fft_size], sample_rate)
        summed = power.copy() if summed is None else summed + power
        count += 1
    power = summed / count
    band_power = {name: float(np.sum(power[(frequencies >= low) & (frequencies < high)]))
                  for name, (low, high) in BANDS.items()}
    covered = sum(band_power.values())
    mask = (frequencies >= 20) & (frequencies < 20000)
    centroid = float(np.sum(frequencies[mask] * power[mask]) / covered) if covered > 1e-16 else None

    step = 15 / tempo if tempo is not None else 0.025
    anchor = origin_sec if tempo is not None else start_sec
    first = math.floor((start_sec - anchor) / step + 1e-9)
    last = math.ceil((end_sec - anchor) / step - 1e-9)
    cells = []
    for index in range(first, last):
        check_cancel()
        left = max(start_sec, anchor + index * step)
        right = min(end_sec, anchor + (index + 1) * step)
        a = max(0, round((left - start_sec) * sample_rate))
        b = min(len(samples), round((right - start_sec) * sample_rate))
        if b <= a:
            continue
        block = samples[a:b]
        freq, p = _spectrum(block, sample_rate)
        cells.append((index, left, right, float(np.mean(block ** 2)),
                      float(np.sum(p[(freq >= 300) & (freq < 4000)]))))

    def coordinate(seconds: float) -> dict:
        return _position(seconds, tempo, signature, origin_sec)

    def boundary(cell: tuple, end: bool = False) -> dict:
        result = {"sec": round(cell[2 if end else 1], 6)}
        if tempo is not None:
            result.update(grid_index=cell[0] + int(end), position=coordinate(cell[2 if end else 1]))
        return result

    # A >6dB rise over the preceding cell, with a relative noise floor.
    # The first cell has no measured predecessor, so is not called an onset.
    transients = []
    floor = max((c[3] for c in cells), default=0) * 1e-4
    for previous, cell in zip(cells, cells[1:]):
        check_cancel()
        if cell[3] > max(previous[3] * 4, floor, 1e-16):
            transients.append(boundary(cell))

    # Median of band powers, not of waveforms; exact digital silence is handled
    # separately because there is no finite relative-to-median dB threshold.
    median = float(np.median([c[4] for c in cells])) if cells else 0.0
    threshold = median * 10 ** (-12 / 10)
    gaps = []
    run = None
    for i, cell in enumerate(cells):
        check_cancel()
        quiet = median > 1e-16 and cell[4] < threshold
        if quiet and run is None:
            run = i
        if run is not None and (not quiet or i == len(cells) - 1):
            end_index = i if quiet else i - 1
            left, right = cells[run], cells[end_index]
            gap = {"from": boundary(left), "to": boundary(right, True),
                   "duration_sec": round(right[2] - left[1], 6)}
            if tempo is not None:
                gap["duration_beats"] = round((right[2] - left[1]) * tempo / 60, 6)
            gaps.append(gap)
            run = None
    grid = None
    if tempo is not None:
        grid = {"status": "assumed_from_supplied_tempo", "tempo_bpm": tempo,
                "signature": list(signature), "origin_sec": origin_sec,
                "beat_unit": "quarter_note (LOM); sixteenth = 1/4 quarter note",
                "quarter_beats_per_bar": signature[0] * 4 / signature[1],
                "sec_per_bar": signature[0] * 4 / signature[1] * 60 / tempo,
                "sec_per_beat": 60 / tempo, "sec_per_16th": step,
                "first_cell_index": first, "cell_count": len(cells),
                "partial_first_cell": not math.isclose(start_sec, anchor + first * step, abs_tol=1e-8),
                "partial_last_cell": not math.isclose(end_sec, anchor + last * step, abs_tol=1e-8),
                "start_position": coordinate(start_sec), "end_position": coordinate(end_sec)}
    check_cancel()
    return {
        "measurement_source": "decoded PCM before lossy encoding; channel powers averaged",
        "sample_rate": sample_rate, "channels": samples.shape[1],
        "start_sec": round(start_sec, 6), "end_sec": round(end_sec, 6),
        "duration_sec": round(len(samples) / sample_rate, 6),
        "peak_dbfs": _db(float(np.max(channel_peak)) ** 2),
        "rms_dbfs": _db(float(np.mean(channel_power))),
        "channel_peak_dbfs": [_db(float(v) ** 2) for v in channel_peak],
        "channel_rms_dbfs": [_db(float(v)) for v in channel_power],
        "bands_dbfs": {name: _db(value) for name, value in band_power.items()},
        "band_energy_fraction": {name: round(value / covered, 6) if covered > 0 else 0.0
                                 for name, value in band_power.items()},
        "spectral_centroid_hz": round(centroid, 2) if centroid is not None else None,
        "dominant_pitches": _pitches(frequencies, power),
        "pitch_status": "inferred spectral peaks, not verified f0 or key; confidence is spectral concentration",
        "tempo_estimate_bpm": None,
        "tempo_estimate_status": "not_estimated; supply tempo to assume a musical grid",
        "grid": grid,
        "event_method": "cell energy rises >6dB; no instrument classification; times quantized to cell boundaries",
        "event_resolution_sec": step, "transients": transients[:MAX_EVENTS],
        "transients_omitted": max(0, len(transients) - MAX_EVENTS),
        "midrange_gap_threshold_db": -12,
        "midrange_median_dbfs": _db(median),
        "midrange_gaps": gaps[:MAX_EVENTS],
        "midrange_gaps_omitted": max(0, len(gaps) - MAX_EVENTS),
    }
