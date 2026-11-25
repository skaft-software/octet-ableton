import json
import math
import unittest

import numpy as np

from octet_ableton.telemetry import analyze_pcm, bar_to_seconds, validate_timing


RATE = 48000


def sine(hz=440, seconds=1, amplitude=0.5):
    return amplitude * np.sin(2 * np.pi * hz * np.arange(round(seconds * RATE)) / RATE)


class TelemetryTests(unittest.TestCase):
    def test_sine_levels_spectrum_and_inferred_pitch(self):
        result = analyze_pcm(sine(), RATE)
        self.assertAlmostEqual(result["peak_dbfs"], 20 * math.log10(0.5), places=2)
        self.assertAlmostEqual(result["rms_dbfs"], 20 * math.log10(0.5 / math.sqrt(2)), places=2)
        self.assertGreater(result["band_energy_fraction"]["mid_300_4khz"], 0.99)
        self.assertAlmostEqual(result["spectral_centroid_hz"], 440, delta=1)
        pitch = result["dominant_pitches"][0]
        self.assertEqual(pitch["note"], "A4")
        self.assertAlmostEqual(pitch["hz"], 440, delta=1)
        self.assertGreater(pitch["confidence"], 0.9)
        self.assertIsNone(result["grid"])
        self.assertIsNone(result["tempo_estimate_bpm"])
        json.dumps(result, allow_nan=False)

    def test_opposite_phase_stereo_does_not_cancel_measurement(self):
        mono = sine()
        result = analyze_pcm(np.column_stack((mono, -mono)), RATE)
        self.assertEqual(result["channels"], 2)
        self.assertAlmostEqual(result["rms_dbfs"], -9.031, places=2)
        self.assertEqual(result["channel_peak_dbfs"], [-6.021, -6.021])
        self.assertGreater(result["band_energy_fraction"]["mid_300_4khz"], 0.99)

    def test_silence_is_json_safe(self):
        result = analyze_pcm(np.zeros((RATE, 2)), RATE, tempo=120)
        self.assertIsNone(result["peak_dbfs"])
        self.assertIsNone(result["rms_dbfs"])
        self.assertIsNone(result["spectral_centroid_hz"])
        self.assertEqual(result["dominant_pitches"], [])
        self.assertEqual(result["transients"], [])
        self.assertEqual(result["midrange_gaps"], [])
        self.assertTrue(all(v is None for v in result["bands_dbfs"].values()))
        json.dumps(result, allow_nan=False)

    def test_impulses_are_grid_indices_not_instrument_labels(self):
        samples = np.zeros(RATE)
        samples[int(0.25 * RATE)] = 1
        samples[int(0.75 * RATE)] = 1
        result = analyze_pcm(samples, RATE, tempo=120)
        self.assertEqual([event["grid_index"] for event in result["transients"]], [2, 6])
        self.assertEqual([event["sec"] for event in result["transients"]], [0.25, 0.75])
        self.assertNotIn("kick", json.dumps(result))
        self.assertNotIn("snare", json.dumps(result))

    def test_midrange_gap_is_strictly_below_reference(self):
        samples = sine(1000)
        samples[int(0.5 * RATE):int(0.75 * RATE)] = 0
        result = analyze_pcm(samples, RATE, tempo=120)
        self.assertEqual(len(result["midrange_gaps"]), 1)
        gap = result["midrange_gaps"][0]
        self.assertEqual(gap["from"]["grid_index"], 4)
        self.assertEqual(gap["to"]["grid_index"], 6)
        self.assertEqual(gap["duration_beats"], 0.5)
        # An 11dB reduction is not a >12dB gap.
        samples = sine(1000)
        samples[int(0.5 * RATE):int(0.75 * RATE)] *= 10 ** (-11 / 20)
        self.assertEqual(analyze_pcm(samples, RATE, tempo=120)["midrange_gaps"], [])

    def test_fractional_bars_compound_meter_and_partial_cells(self):
        self.assertEqual(bar_to_seconds(2, 120, [6, 8]), 1.5)
        self.assertEqual(bar_to_seconds(1.5, 120, [6, 8], 2), 2.75)
        self.assertEqual(bar_to_seconds(2, 120, [3, 4]), 1.5)
        result = analyze_pcm(sine(seconds=0.375), RATE, start_sec=1.5625,
                             tempo=120, signature=[6, 8])
        grid = result["grid"]
        self.assertEqual(grid["quarter_beats_per_bar"], 3)
        self.assertEqual(grid["first_cell_index"], 12)
        self.assertEqual(grid["cell_count"], 4)
        self.assertTrue(grid["partial_first_cell"])
        self.assertTrue(grid["partial_last_cell"])
        self.assertEqual(grid["start_position"]["bar"], 2)
        self.assertEqual(grid["start_position"]["sixteenth"], 1.5)
        self.assertEqual(grid["status"], "assumed_from_supplied_tempo")

    def test_event_output_is_bounded(self):
        samples = np.zeros(RATE * 8)
        step = 15 / 999
        for index in range(1, int(8 / step), 2):
            samples[round((index + 0.1) * step * RATE)] = 1
        result = analyze_pcm(samples, RATE, tempo=999)
        self.assertEqual(len(result["transients"]), 64)
        self.assertGreater(result["transients_omitted"], 0)
        json.dumps(result, allow_nan=False)

    def test_invalid_inputs_and_duration_cap(self):
        for tempo in (True, "120", 0, 19, 1000, float("nan"), float("inf")):
            with self.subTest(tempo=tempo), self.assertRaises(ValueError):
                validate_timing(tempo)
        for signature in (None, [4], [4, 3], [True, 4], [0, 4]):
            with self.subTest(signature=signature), self.assertRaises(ValueError):
                validate_timing(120, signature)
        for samples in (np.array([]), np.array([float("nan")]), np.zeros(RATE * 8 + 1)):
            with self.assertRaises(ValueError):
                analyze_pcm(samples, RATE)

    def test_cancellation_during_analysis(self):
        calls = 0

        def cancel():
            nonlocal calls
            calls += 1
            if calls == 5:
                raise InterruptedError("cancelled")

        with self.assertRaisesRegex(InterruptedError, "cancelled"):
            analyze_pcm(sine(seconds=4), RATE, check_cancel=cancel)
        self.assertEqual(calls, 5)


if __name__ == "__main__":
    unittest.main()
