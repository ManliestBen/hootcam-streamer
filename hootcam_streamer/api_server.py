"""Minimal HTTP API so Hootcam Motion can push config (resolution, fps) to the streamer."""
from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from . import config as config_module

logger = logging.getLogger(__name__)


def _run_server(
    config_path: Path,
    reload_requested: list[bool],
    port: int,
) -> None:
    """Run HTTP server in a thread. reload_requested is a single-element list so the handler can set it."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.rstrip("/") != "/config":
                self.send_error(404)
                return
            try:
                cfg = config_module.load_config(config_path)
                body = json.dumps(cfg).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                logger.warning("GET /config error: %s", e)
                self.send_error(500)

        def do_PATCH(self) -> None:
            if self.path.rstrip("/") != "/config":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                patch = json.loads(raw)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning("PATCH /config body error: %s", e)
                self.send_error(400)
                return
            try:
                current = config_module.load_config(config_path)
                # Merge patch: only cam0, cam1 and their sub-keys (width, height, fps, enabled)
                for key in ("cam0", "cam1"):
                    if key in patch and isinstance(patch[key], dict):
                        current.setdefault(key, {})
                        for k, v in patch[key].items():
                            if k in ("width", "height", "fps", "enabled"):
                                current[key][k] = v
                config_module.save_config(config_path, current)
                reload_requested[0] = True
                self.send_response(204)
                self.end_headers()
            except Exception as e:
                logger.warning("PATCH /config error: %s", e)
                self.send_error(500)

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug("%s", args[0] if args else format)

    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info("Streamer API listening on http://0.0.0.0:%d (GET/PATCH /config)", port)
    server.serve_forever()

def start_api_server(
    config_path: Path,
    reload_requested: list[bool],
    port: int = 8084,
) -> threading.Thread:
    """Start the API server in a daemon thread. Returns the thread."""
    t = threading.Thread(
        target=_run_server,
        args=(config_path, reload_requested, port),
        daemon=True,
    )
    t.start()
    return t
