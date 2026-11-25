"""Bounded loopback transport. Only pump(), called by Live, touches the engine.

One UTF-8 JSON line per connection, protocol 1, UUID request id. Socket workers
never schedule Live callbacks or access LOM. Disconnect/deadline cancellation is
cooperative: an in-flight Live API call cannot be interrupted or rolled back.
"""
import hmac
import json
import os
import queue
import re
import select
import socket
import threading
import time
import uuid

PROTOCOL = 1
HOST = "127.0.0.1"
PORT = 9878
MAX_FRAME = 512 * 1024
MAX_CONNECTIONS = 8
REQUEST_TIMEOUT = 30.0
READ_TIMEOUT = 3.0


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def load_config(path=None):
    path = path or os.path.expanduser("~/.config/octet-ableton/bridge.json")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            config = json.loads(stream.read(4097))
        if (set(config) != {"protocol", "token", "port"}
                or type(config["protocol"]) is not int or config["protocol"] != PROTOCOL
                or type(config["port"]) is not int or config["port"] != PORT
                or not isinstance(config["token"], str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", config["token"])):
            raise ValueError()
        return config
    except (OSError, ValueError, TypeError):
        raise BridgeError("configuration", "Missing or invalid OctetBridge configuration; run setup.")


def response(request_id, result=None, error=None):
    value = {"id": request_id, "protocol": PROTOCOL}
    if error is not None:
        value["error"] = {"code": error.code, "message": error.message}
    else:
        value["result"] = result
    return value


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode_request(data, token):
    try:
        value = json.loads(data.decode("utf-8"), parse_constant=_reject_constant,
                           object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise BridgeError("invalid_request", "Expected one valid JSON object.")
    if not isinstance(value, dict):
        raise BridgeError("invalid_request", "Expected a request object.")
    try:
        return _validate_envelope(value, token)
    except BridgeError as error:
        candidate = value.get("id")
        try:
            if isinstance(candidate, str) and str(uuid.UUID(candidate)) == candidate:
                error.request_id = candidate
        except ValueError:
            pass
        raise


def _validate_envelope(value, token):
    supplied = value.get("token")
    if not isinstance(supplied, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", supplied) or not hmac.compare_digest(supplied, token):
        raise BridgeError("unauthorized", "Authentication failed.")
    if type(value.get("protocol")) is not int or value["protocol"] != PROTOCOL:
        raise BridgeError("protocol", "Unsupported bridge protocol; expected 1.")
    if set(value) != {"id", "protocol", "token", "method", "params"}:
        raise BridgeError("invalid_request", "Unexpected or missing request fields.")
    try:
        if not isinstance(value["id"], str) or str(uuid.UUID(value["id"])) != value["id"]:
            raise ValueError()
    except (ValueError, AttributeError):
        raise BridgeError("invalid_request", "id must be a canonical UUID string.")
    if value["method"] not in ("ping", "snapshot", "compose", "lom", "capture_begin", "capture_end") or not isinstance(value["params"], dict):
        raise BridgeError("invalid_request", "Unknown method or invalid params.")
    return value


class PendingRequest:
    def __init__(self, envelope, connection, deadline):
        self.envelope = envelope
        self.connection = connection
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.reply = None

    def check_active(self):
        if self.cancelled.is_set():
            raise BridgeError("cancelled", "Request disconnected or cancelled; effects may already exist. Do not retry automatically.")
        if time.monotonic() >= self.deadline:
            self.cancelled.set()
            raise BridgeError("deadline", "Request deadline exceeded; effects may already exist. Do not retry automatically.")
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if readable:
                # EOF, or a second request, both abandon this single-request connection.
                self.cancelled.set()
                raise BridgeError("disconnected", "Connection closed or additional data received.")
        except (OSError, ValueError):
            self.cancelled.set()
            raise BridgeError("disconnected", "Connection closed.")


class BridgeServer:
    def __init__(self, engine, token, capture=None):
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", token):
            raise BridgeError("configuration", "Invalid bridge token.")
        self.engine = engine
        self.capture = capture
        self._token = token
        self._owner = threading.get_ident()
        self._stop = threading.Event()
        self._queue = queue.Queue(MAX_CONNECTIONS)
        self._lock = threading.Lock()
        self._clients = set()
        self._workers = set()
        self._listener = None
        self._thread = None

    def start(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((HOST, PORT))  # Never SO_REUSEPORT; never disturb another listener.
            listener.listen(MAX_CONNECTIONS)
            listener.settimeout(0.2)
        except OSError:
            listener.close()
            raise BridgeError("bind", "Cannot bind OctetBridge to 127.0.0.1:9878; existing listeners are left alone.")
        self._listener = listener
        self._thread = threading.Thread(target=self._accept, name="OctetBridge-listener", daemon=True)
        self._thread.start()

    @property
    def address(self):
        return self._listener.getsockname()

    def _accept(self):
        while not self._stop.is_set():
            try:
                client, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                if self._stop.is_set() or len(self._clients) >= MAX_CONNECTIONS:
                    client.close()
                    continue
                self._clients.add(client)
                worker = threading.Thread(target=self._serve, args=(client,), name="OctetBridge-client", daemon=True)
                self._workers.add(worker)
                worker.start()

    def _serve(self, client):
        try:
            self._serve_request(client)
        finally:
            self._release(client)

    def _serve_request(self, client):
        request = None
        request_id = None
        deadline = time.monotonic() + REQUEST_TIMEOUT
        try:
            chunks = bytearray()
            read_deadline = min(deadline, time.monotonic() + READ_TIMEOUT)
            while b"\n" not in chunks:
                if self._stop.is_set():
                    return
                remaining = read_deadline - time.monotonic()
                if remaining <= 0:
                    raise BridgeError("deadline", "Request frame timed out.")
                client.settimeout(min(remaining, 0.1))
                try:
                    part = client.recv(min(65536, MAX_FRAME + 1 - len(chunks)))
                except socket.timeout:
                    continue
                if not part:
                    return
                chunks.extend(part)
                if len(chunks) > MAX_FRAME:
                    raise BridgeError("frame_too_large", "Request exceeds 512 KiB.")
            line, trailing = bytes(chunks).split(b"\n", 1)
            if trailing:
                raise BridgeError("invalid_request", "Only one request per connection is allowed.")
            envelope = decode_request(line, self._token)
            request_id = envelope["id"]
            request = PendingRequest(envelope, client, deadline)
            request.check_active()
            try:
                self._queue.put_nowait(request)
            except queue.Full:
                raise BridgeError("busy", "Bridge queue is full; request was not executed.")
            while not request.done.wait(0.025):
                if self._stop.is_set():
                    request.cancelled.set()
                request.check_active()
            reply = request.reply
        except BridgeError as error:
            request_id = getattr(error, "request_id", request_id)
            reply = response(request_id, error=error)
        except socket.timeout:
            reply = response(request_id, error=BridgeError("deadline", "Socket timed out; do not automatically retry writes."))
        except OSError:
            return
        except Exception:
            reply = response(request_id, error=BridgeError("internal", "Bridge request failed."))
        finally:
            if request is not None and not request.done.is_set():
                request.cancelled.set()
        try:
            payload = json.dumps(reply, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(payload) > MAX_FRAME:
                payload = json.dumps(response(request_id, error=BridgeError("response_too_large", "Response exceeded 512 KiB; writes, if any, are not rolled back."))).encode("utf-8") + b"\n"
            client.settimeout(1.0)
            client.sendall(payload)
        except (OSError, ValueError, TypeError):
            pass

    def _release(self, client):
        client.close()
        with self._lock:
            self._clients.discard(client)
            self._workers.discard(threading.current_thread())

    def pump(self, limit=2):
        if threading.get_ident() != self._owner:
            raise RuntimeError("Bridge pump must run on Live's main thread")
        if self.capture is not None:
            self.capture.tick()
        for _ in range(limit):
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                request.check_active()
                method, params = request.envelope["method"], request.envelope["params"]
                if method.startswith("capture_"):
                    if self.capture is None:
                        raise BridgeError("unsupported", "Capture control is unavailable.")
                    result = self.capture.handle(method, params)
                else:
                    if method == "compose" and self.capture is not None and self.capture.active:
                        raise BridgeError("busy", "Wait for the active audio capture before composing.")
                    result = self.engine.handle(method, params, request.check_active)
                request.reply = response(request.envelope["id"], result=result)
            except BridgeError as error:
                request.reply = response(request.envelope["id"], error=error)
            except Exception as error:
                if request.envelope["method"] in ("ping", "snapshot", "lom"):
                    message = "Live read failed (%s); no edits were requested." % type(error).__name__
                else:
                    message = "Live API request failed; effects are not rolled back."
                request.reply = response(request.envelope["id"], error=BridgeError("live_error", message))
            finally:
                request.done.set()

    def close(self):
        if self.capture is not None:
            self.capture.restore()
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
        with self._lock:
            clients = list(self._clients)
            workers = list(self._workers)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
        while True:
            try:
                self._queue.get_nowait().cancelled.set()
            except queue.Empty:
                break
        if self._thread is not None:
            self._thread.join(1.0)
        for worker in workers:
            worker.join(1.0)
