"""Serve an app from the test process in a background thread (for Playwright only)."""
import socket
import threading
import time

import httpx
import uvicorn


class LiveServer:
    def __init__(self, app):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self, timeout: float = 15.0) -> "LiveServer":
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                try:
                    if httpx.get(self.url + "/healthz", timeout=2).status_code == 200:
                        return self
                except httpx.HTTPError:
                    pass
            if not self._thread.is_alive():
                break
            self._thread.join(0.02)
        raise RuntimeError("live server did not start")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=15)
