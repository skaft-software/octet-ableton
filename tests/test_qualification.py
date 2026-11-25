import contextlib
import io
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from scripts.qualify_live import main


class QualificationGuards(unittest.TestCase):
    def reject(self, extra, state=None):
        argv = ["qualify_live.py", "--expect-marker", "SCRATCH ONLY", "--output", "unused"] + extra
        client = Mock()
        client.call.return_value = state
        with patch.object(sys, "argv", argv), patch("scripts.qualify_live.BridgeClient", return_value=client), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(any(call.args[0] == "compose" for call in client.call.call_args_list))
        return client

    def test_requires_explicit_apply_before_bridge_access(self):
        self.reject([]).call.assert_not_called()

    def test_requires_marker_in_current_set(self):
        self.reject(["--apply"], {"tracks": [{"name": "Important work"}]})

    def test_fixture_places_and_captures_away_from_bar_one(self):
        transport = {'playing': False, 'bpm': 120, 'signature_numerator': 4,
                     'signature_denominator': 4, 'playhead_beat': 0, 'loop': False}
        before = {'transport': transport, 'tracks': [{'name': 'SCRATCH ONLY'}]}
        placed = {'transport': transport, 'tracks': [{
            'name': 'Octet check abcdef', 'arrangement_clips': [{'start_beat': 16}], 'session_clips': []}]}
        client = Mock()
        client.call.side_effect = [
            before,
            {'ok': True, 'receipts': [{'result': {'track_index': 1}}]},
            {'value': [{'name': 'Frequency', 'min': 0, 'max': 1}]},
            {'ok': True}, placed, placed,
        ]
        capture = {'slices': [{'telemetry': {'peak_dbfs': -10}}]}
        with tempfile.TemporaryDirectory() as directory:
            argv = ['qualify_live.py', '--apply', '--expect-marker', 'SCRATCH ONLY',
                    '--output', str(Path(directory) / 'result')]
            with (patch.object(sys, 'argv', argv),
                  patch('scripts.qualify_live.BridgeClient', return_value=client),
                  patch('scripts.qualify_live.uuid.uuid4', return_value=Mock(hex='abcdef')),
                  patch('scripts.qualify_live.listen_live', return_value=capture) as listen,
                  contextlib.redirect_stdout(io.StringIO())):
                main()
        clip_action = client.call.call_args_list[3].args[1]['actions'][0]
        self.assertEqual(clip_action['start_bar'], 5)
        self.assertEqual(clip_action['length_bars'], 2)
        self.assertEqual(listen.call_args.args[0]['slices'][0], {
            'label': 'synth-with-filter-sweep', 'start_bar': 5, 'end_bar': 7, 'solo_tracks': [1]})

    def test_requires_stopped_transport(self):
        self.reject(["--apply"], {"tracks": [{"name": "SCRATCH ONLY"}], "transport": {"playing": True}})


if __name__ == "__main__":
    unittest.main()
