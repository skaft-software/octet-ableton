import json
import socket
import threading
import time
import unittest

from octet_ableton.bridge_client import BridgeClient, BridgeError


class ClientTests(unittest.TestCase):
    def server(self, reply):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        client = BridgeClient(
            {"token": "a" * 64, "port": listener.getsockname()[1]}, timeout=0.25
        )
        calls = []

        def run():
            conn, _ = listener.accept()
            with conn:
                request = b""
                while not request.endswith(b"\n"):
                    request += conn.recv(65536)
                request = json.loads(request)
                calls.append(request)
                response = reply(request)
                if response is not None:
                    conn.sendall(json.dumps(response).encode() + b"\n")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=1))
        return client, calls

    def test_matching_protocol_and_id(self):
        client, calls = self.server(
            lambda r: {"protocol": 1, "id": r["id"], "result": {"connected": True}}
        )
        self.assertEqual(client.call("ping"), {"connected": True})
        self.assertEqual(calls[0]["method"], "ping")

    def test_lost_write_is_not_replayed(self):
        client, calls = self.server(lambda r: None)
        with self.assertRaisesRegex(BridgeError, "may have applied"):
            client.call(
                "compose", {"actions": [{"op": "create_midi_track"}], "dry_run": False}
            )
        self.assertEqual(len(calls), 1)

    def test_timeout_is_bounded(self):
        client, _ = self.server(lambda r: time.sleep(0.4))
        started = time.monotonic()
        with self.assertRaisesRegex(BridgeError, "timed out"):
            client.call("ping")
        self.assertLess(time.monotonic() - started, 0.5)

    def test_mismatched_response_refused(self):
        client, _ = self.server(lambda r: {"protocol": 1, "id": "wrong", "result": {}})
        with self.assertRaisesRegex(BridgeError, "protocol mismatch"):
            client.call("ping")
