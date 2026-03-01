"""Run two Spyglass instances (one per camera) for MJPEG streaming.

Spyglass: https://github.com/ManliestBen/spyglass
Streams are MJPEG at http://<pi-ip>:8080/stream and http://<pi-ip>:8081/stream (default ports).
"""
from __future__ import annotations

import logging
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_keep_running = True


def _stop_handler(_signum: int, _frame: object) -> None:
    global _keep_running
    _keep_running = False


def run_spyglass_pipeline(
    cam0: dict[str, Any],
    cam1: dict[str, Any],
    spyglass_port_cam0: int = 8080,
    spyglass_port_cam1: int = 8081,
) -> list[tuple[str, subprocess.Popen]]:
    """Start two Spyglass processes (camera 0 and 1). Returns list of (label, process) for caller to track."""
    _bin = shutil.which("spyglass") or (Path(sys.executable).parent / "spyglass")
    if isinstance(_bin, Path) and not _bin.is_file():
        _bin = None
    if not _bin:
        raise RuntimeError(
            "Spyglass not found. Install with: pip install git+https://github.com/ManliestBen/spyglass.git"
        )
    spyglass_bin = str(_bin)

    global _keep_running
    _keep_running = True
    signal.signal(signal.SIGINT, _stop_handler)
    signal.signal(signal.SIGTERM, _stop_handler)

    processes: list[tuple[str, subprocess.Popen]] = []

    def start_spyglass(cam_key: str, camera_index: int, cam_cfg: dict[str, Any], port: int) -> None:
        if not cam_cfg.get("enabled", True):
            logger.info("Skipping %s (disabled)", cam_key)
            return
        w = int(cam_cfg.get("width", 1920))
        h = int(cam_cfg.get("height", 1080))
        fps = int(cam_cfg.get("fps", 25))
        resolution = f"{w}x{h}"
        cmd = [
            spyglass_bin,
            "-n", str(camera_index),
            "-p", str(port),
            "-r", resolution,
            "-f", str(fps),
            "--use_sw_jpg_encoding",  # recommended on Pi 5
            "--disable_webrtc",      # recommended on Pi 5
        ]
        logger.info(
            "Starting %s (Spyglass camera %s): %s @ %d fps on port %d",
            cam_key, camera_index, resolution, fps, port,
        )
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        processes.append((f"{cam_key}/spyglass", proc))

    start_spyglass("cam0", 0, cam0, spyglass_port_cam0)
    if cam1.get("enabled", True):
        time.sleep(2)  # Stagger so cam0 binds before cam1
    start_spyglass("cam1", 1, cam1, spyglass_port_cam1)

    if not processes:
        logger.warning("No Spyglass instances started (all cameras disabled?)")
        return processes

    logger.info(
        "Spyglass streams: http://<pi-ip>:%d/stream and http://<pi-ip>:%d/stream (MJPEG)",
        spyglass_port_cam0, spyglass_port_cam1,
    )
    return processes
