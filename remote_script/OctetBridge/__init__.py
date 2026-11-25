"""Ableton Control Surface entrypoint; no dependency on the octet SDK."""


def create_instance(c_instance):
    # Import only inside Live, so the pure-Python engine/transport can be tested elsewhere.
    from _Framework.ControlSurface import ControlSurface
    from .engine import LiveEngine
    from .capture_control import CaptureControl
    from .server import BridgeError, BridgeServer, load_config

    class OctetBridge(ControlSurface):
        def __init__(self, instance):
            super(OctetBridge, self).__init__(instance)
            self._bridge = None
            self._active = False
            try:
                config = load_config()
                self._bridge = BridgeServer(LiveEngine(self.song(), self.application()), config["token"], CaptureControl(self.song()))
                self._bridge.start()
            except BridgeError as error:
                # These messages are fixed strings, never config contents or token values.
                self.log_message("OctetBridge disabled: " + error.message)
                if self._bridge is not None:
                    self._bridge.close()
                self._bridge = None
                return
            self._active = True
            self.log_message("OctetBridge listening on 127.0.0.1:9878.")
            self.schedule_message(1, self._pump)

        def _pump(self):
            if not self._active:
                return
            try:
                self._bridge.pump()
            finally:
                if self._active:
                    self.schedule_message(1, self._pump)

        def disconnect(self):
            self._active = False
            if self._bridge is not None:
                self._bridge.close()
            super(OctetBridge, self).disconnect()

    return OctetBridge(c_instance)
