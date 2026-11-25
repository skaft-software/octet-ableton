import base64
import json
import shutil
import wave
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path

from octet_ableton.bridge_client import BridgeError, read_config
from octet_ableton.installer import setup

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def test_install_update_backup_and_private_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "__init__.py").write_text("# script v1\n")
            config = root / "config/bridge.json"
            first = setup(root / "library", config=config, source=source)
            token = read_config(config)["token"]
            if os.name == "nt":
                from octet_ableton.windows_config import is_private_config
                self.assertTrue(is_private_config(config))
            else:
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            (source / "__init__.py").write_text("# script v2\n")
            second = setup(root / "library", config=config, source=source)
            self.assertEqual(read_config(config)["token"], token)
            self.assertIn("v1", (Path(second["backup"]) / "__init__.py").read_text())
            self.assertIn("v2", (Path(first["installed"]) / "__init__.py").read_text())
            self.assertNotIn(token, json.dumps(second))
            self.assertEqual(Path(second["backup"]).parent, config.parent / "script-backups")
            self.assertEqual([p.name for p in (root / "library/Remote Scripts").iterdir()], ["OctetBridge"])

    def test_refuse_symlink_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Remote Scripts").mkdir()
            (root / "Remote Scripts/OctetBridge").symlink_to(
                root, target_is_directory=True
            )
            with self.assertRaises(ValueError):
                setup(root, config=root / "bridge.json")
            self.assertFalse((root / "bridge.json").exists())

    def test_config_missing_is_actionable(self):
        with self.assertRaisesRegex(BridgeError, "setup"):
            read_config(ROOT / "does-not-exist.json")


class ProcessSmoke(unittest.TestCase):
    def start(self, injected=False, fixture=False, artifacts=False):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        env = dict(
            os.environ,
            HOME=self.home.name,
            OCTET_EXTENSION_SCRATCH=self.home.name,
            PYTHONDONTWRITEBYTECODE="1",
        )
        if fixture:
            code = """
import sys
sys.path[:0] = ['.', 'vendor']
from octet_ableton.extension import build_extension
class FakeBridge:
    def call(self, method, params=None, *, check_cancel):
        if method == 'lom':
            assert params == {'view': 'session', 'track_indices': []}
            return {'read_only': True, 'view': 'session', 'transport': {'bpm': 120}, 'tracks': []}
        assert method == 'compose'
        assert 'detail' not in params
        return {'ok': True, 'status': 'completed', 'dry_run': False, 'receipts': [
            {'index': 0, 'op': 'create_midi_track', 'status': 'completed',
             'result': {'track_index': 4, 'name': 'test'}}]}
build_extension(client=FakeBridge()).run()
"""
            command = [sys.executable, "-c", code]
        elif injected:
            code = (
                "import sys,time; sys.path[:0]=['.', 'vendor']; "
                "from octet_ableton.extension import build_extension; "
                "exec('class SlowBridge:\\n def call(self, method, params=None, *, check_cancel):\\n  while True:\\n   check_cancel()\\n   time.sleep(0.01)'); "
                "build_extension(client=SlowBridge()).run()"
            )
            command = [sys.executable, "-c", code]
        else:
            command = [sys.executable, str(ROOT / "run-extension")]
            env["OCTET_EXTENSION_DIR"] = str(ROOT)
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )

        def cleanup():
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
                stream.close()

        self.addCleanup(cleanup)
        self.messages = queue.Queue()

        def reader():
            for line in self.process.stdout:
                self.messages.put(json.loads(line))

        threading.Thread(target=reader, daemon=True).start()
        manifest = tomllib.loads((ROOT / "extension.toml").read_text())
        self.send(
            1,
            "initialize",
            {
                "api_version": "0.4",
                "octet_version": "0.10.5",
                "extension": {
                    "name": manifest["name"],
                    "version": manifest["version"],
                    "manifest_path": str(ROOT / "extension.toml"),
                    "source": "explicit",
                },
                "workspace": str(ROOT),
                "capabilities": manifest["capabilities"],
                "contributes": manifest["contributes"],
                "host": {},
                "protocol": {
                    "version": "0.4",
                    "required_features": ["request_cancellation", "content_parts"],
                    "optional_features": ["artifacts"] if artifacts else [],
                    "limits": {"max_concurrent_requests": 4},
                },
            },
        )
        return self.receive()["result"]

    def send(self, request_id, method, params):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            message["id"] = request_id
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def receive(self):
        return self.messages.get(timeout=8)

    def finish(self):
        self.send(9, "shutdown", {})
        self.assertEqual(self.receive(), {"jsonrpc": "2.0", "id": 9, "result": {}})
        self.assertEqual(self.process.wait(timeout=5), 0)

    def test_real_entrypoint_catalog_menu_error_shutdown(self):
        initialized = self.start()
        self.assertEqual(initialized["api_version"], "0.4")
        self.assertEqual(
            {t["name"] for t in initialized["tools"]},
            {"ableton_listen", "ableton_compose", "ableton_live_object_model"},
        )
        manifest = tomllib.loads((ROOT / "extension.toml").read_text())
        self.assertEqual(
            {t["name"] for t in initialized["tools"]},
            set(manifest["contributes"]["tools"]),
        )
        self.send(2, "menu/collect", {"context": {}})
        self.assertEqual(len(self.receive()["result"]["items"]), 3)
        self.send(
            3,
            "tool/call",
            {
                "name": "ableton_listen",
                "arguments": {
                    "file_path": "/no-such-track.wav",
                    "slices": [{"start_sec": 0, "end_sec": 1}],
                },
                "context": {},
            },
        )
        self.assertTrue(self.receive()["result"]["is_error"])
        self.finish()

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required"
    )
    def test_successful_audio_tool_over_stdio(self):
        self.start()
        source = Path(self.home.name) / "silence.wav"
        with wave.open(str(source), "wb") as wav:
            wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 12000)
        self.send(
            2,
            "tool/call",
            {
                "name": "ableton_listen",
                "arguments": {
                    "file_path": str(source),
                    "include_session_state": False,
                    "slices": [{"start_sec": 0, "end_sec": 0.25}],
                },
                "context": {},
            },
        )
        result = self.receive()["result"]
        self.assertFalse(result["is_error"])
        output = json.loads(result["content"][0]["text"])
        self.assertTrue(Path(output["slice_paths"][0]).is_file())
        self.finish()

    def test_attach_without_artifacts_rejected_before_capture(self):
        self.start()
        self.send(2, "tool/call", {"name": "ableton_listen", "arguments": {
            "attach_audio": True, "slices": [{"start_bar": 1, "end_bar": 2}],
        }, "context": {}})
        response = self.receive()["result"]
        self.assertTrue(response["is_error"])
        output = json.loads(response["content"][0]["text"])
        self.assertIn("did not negotiate", output["error"])
        self.assertEqual(output["metrics"]["bridge_calls"], 0)
        self.finish()

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_native_audio_consent_order_and_publication_failure(self):
        self.start(artifacts=True)
        source = Path(self.home.name) / "fixture.wav"
        with wave.open(str(source), "wb") as wav:
            wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * 12000 + b"\x44\x00" * 12000)

        def reply(request, **fields):
            self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request["id"], **fields}) + "\n")
            self.process.stdin.flush()

        for request_id, mode in enumerate(("denied", "approved", "failed"), 2):
            self.send(request_id, "tool/call", {"name": "ableton_listen", "arguments": {
                "file_path": str(source), "attach_audio": True,
                "slices": [{"start_sec": 0, "end_sec": .25}, {"start_sec": .25, "end_sec": .5}],
            }, "context": {}})
            prompt = self.receive()
            self.assertEqual(prompt["method"], "confirmation/request")
            self.assertFalse(prompt["params"]["default"])
            reply(prompt, result={"confirmed": mode != "denied"})
            published = []
            if mode != "denied":
                for i in range(2):
                    publication = self.receive()
                    self.assertEqual(publication["method"], "artifact/publish")
                    self.assertEqual(publication["params"]["mime_type"], "audio/mpeg")
                    published.append(base64.b64decode(publication["params"]["data"]["data"]))
                    if mode == "failed" and i == 1:
                        reply(publication, error={"code": -32602, "message": "quota exceeded"})
                    else:
                        reply(publication, result={"artifact_id": f"preview-{i}"})
            response = self.receive()["result"]
            metadata, *audio = response["content"]
            output = json.loads(metadata["text"])
            self.assertNotIn("next_step", output)
            self.assertEqual(response["is_error"], mode == "failed")
            if mode == "approved":
                self.assertEqual(audio, [{"type": "audio", "artifact_id": f"preview-{i}", "mime_type": "audio/mpeg"} for i in range(2)])
                self.assertEqual(published, [Path(path).read_bytes() for path in output["slice_paths"]])
            else:
                self.assertEqual(audio, [])
                self.assertTrue(all(Path(path).is_file() for path in output["slice_paths"]))
        self.finish()

    def test_compact_default_full_opt_in_and_metrics_over_stdio(self):
        self.start(fixture=True)
        for request_id, detail in [(2, None), (3, "full")]:
            args = {"actions": [{"op": "create_midi_track"}], "dry_run": False}
            if detail:
                args["detail"] = detail
            self.send(request_id, "tool/call", {"name": "ableton_compose", "arguments": args, "context": {}})
            response = self.receive()["result"]
            self.assertFalse(response["is_error"], response)
            output = json.loads(response["content"][0]["text"])
            self.assertEqual(output["metrics"]["bridge_calls"], 1)
            if detail:
                self.assertEqual(len(output["receipts"]), 1)
            else:
                self.assertEqual(output["completed_actions"], 1)
                self.assertNotIn("receipts", output)
                self.assertTrue(Path(output["receipt_path"]).is_file())
        self.finish()

    def test_live_object_model_tool_over_stdio(self):
        self.start(fixture=True)
        self.send(2, "tool/call", {
            "name": "ableton_live_object_model",
            "arguments": {"view": "session", "track_indices": []},
            "context": {},
        })
        response = self.receive()["result"]
        self.assertFalse(response["is_error"], response)
        output = json.loads(response["content"][0]["text"])
        self.assertTrue(output["read_only"])
        self.assertEqual(output["view"], "session")
        self.assertEqual(output["transport"]["bpm"], 120)
        self.assertEqual(output["metrics"]["bridge_calls"], 1)
        self.finish()

    def test_cancel_then_same_process_responds(self):
        self.start(injected=True)
        self.send(
            2,
            "tool/call",
            {
                "name": "ableton_live_object_model",
                "arguments": {"expression": "song.tempo"},
                "context": {},
            },
        )
        self.send(None, "$/cancelRequest", {"id": 2})
        self.assertEqual(self.receive()["error"]["code"], -32800)
        self.send(
            3,
            "command/execute",
            {"name": "ableton", "arguments": ["help"], "context": {}},
        )
        help_text = self.receive()["result"]["text"]
        self.assertIn("Three tools", help_text)
        self.assertIn("ableton_live_object_model", help_text)
        self.finish()
