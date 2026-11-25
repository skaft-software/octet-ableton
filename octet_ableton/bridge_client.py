"""One request per connection; never replay a possibly applied musical edit."""

import json
import os
import re
import socket
import stat
import time
import uuid
from pathlib import Path

MAX_FRAME = 512 * 1024
BRIDGE_REVISION = 6


class BridgeError(RuntimeError):
    pass


def config_path():
    return Path.home() / ".config/octet-ableton/bridge.json"


def read_config(path=None):
    path = Path(path) if path is not None else config_path()
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise BridgeError("Bridge config must be a small regular file.")
        if os.name == "nt":
            from .windows_config import is_private_config
            if not is_private_config(path):
                raise BridgeError("Bridge config must have a private, current-user-only Windows ACL.")
        elif info.st_mode & 0o077:
            raise BridgeError(
                "Bridge config contains a secret; restrict its permissions to 0600."
            )
        config = json.loads(path.read_text())
    except FileNotFoundError:
        raise BridgeError("Bridge not set up. Run /ableton setup first.") from None
    except (OSError, ValueError):
        raise BridgeError("Cannot read bridge config. Check /ableton setup.") from None
    if (
        not isinstance(config, dict)
        or config.get("protocol") != 1
        or not isinstance(config.get("token"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", config["token"])
        or type(config.get("port")) is not int
        or config["port"] != 9878
    ):
        raise BridgeError("Invalid bridge config. Re-run setup after reviewing it.")
    return config


class BridgeClient:
    def __init__(self, config=None, timeout=20.0):
        self.config = config
        self.timeout = timeout

    def call(self, method, params=None, *, check_cancel=lambda: None):
        config = self.config if self.config is not None else read_config()
        request_id = str(uuid.uuid4())
        payload = (
            json.dumps(
                {
                    "id": request_id,
                    "protocol": 1,
                    "token": config["token"],
                    "method": method,
                    "params": params or {},
                },
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        if len(payload) > MAX_FRAME:
            raise BridgeError(
                "Batch too large; split it into smaller musical sections."
            )
        check_cancel()
        deadline = time.monotonic() + (min(self.timeout, 1.5) if method == "capture_end" else self.timeout)
        sent = False
        read_only = method in ("ping", "snapshot", "lom") or (method == "compose" and (params or {}).get("dry_run", True))
        try:
            with socket.create_connection(
                ("127.0.0.1", config["port"]), timeout=1
            ) as sock:
                sock.settimeout(0.1)
                view = memoryview(payload)
                while view:
                    check_cancel()
                    if time.monotonic() >= deadline:
                        raise TimeoutError()
                    try:
                        # Even a partial frame means delivery is uncertain to the caller.
                        sent = True
                        count = sock.send(view)
                        if count == 0:
                            raise ConnectionError()
                        view = view[count:]
                    except TimeoutError:
                        continue
                response = bytearray()
                while b"\n" not in response:
                    check_cancel()
                    if time.monotonic() >= deadline:
                        raise TimeoutError()
                    try:
                        chunk = sock.recv(min(65536, MAX_FRAME + 1 - len(response)))
                    except TimeoutError:
                        continue
                    if not chunk:
                        raise ConnectionError()
                    response.extend(chunk)
                    if len(response) > MAX_FRAME:
                        raise BridgeError("Bridge response exceeded its size limit.")
        except OSError:
            if sent:
                message = ("Bridge read connection lost/timed out; no edits were requested." if read_only else
                           "Bridge connection lost/timed out. Edits may have applied; inspect Live before retrying.")
                raise BridgeError(message) from None
            raise BridgeError(
                "Cannot reach OctetBridge. Select it in Live's Control Surface settings, then run /ableton status."
            ) from None
        try:
            message = json.loads(response.decode())
        except (ValueError, UnicodeError):
            raise BridgeError(
                "Invalid bridge response; inspect Live before retrying edits."
            ) from None
        if (
            not isinstance(message, dict)
            or message.get("id") != request_id
            or message.get("protocol") != 1
            or ("result" in message) == ("error" in message)
        ):
            raise BridgeError(
                "Bridge protocol mismatch; update OctetBridge and restart Live."
            )
        if "error" in message:
            error = message["error"]
            if not isinstance(error, dict):
                raise BridgeError("Malformed bridge error; inspect Live before retrying.")
            raise BridgeError(str(error.get("message", "Bridge request failed"))[:1000])
        if not isinstance(message["result"], dict):
            raise BridgeError("Expected an object from OctetBridge.")
        return message["result"]
