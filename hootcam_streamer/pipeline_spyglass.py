"""Run two Spyglass instances (one per camera) for MJPEG streaming.

Spyglass: https://github.com/ManliestBen/spyglass
Streams are MJPEG at http://<pi-ip>:8082/stream and http://<pi-ip>:8083/stream (default ports).
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
    spyglass_port_cam0: int = 8082,
    spyglass_port_cam1: int = 8083,
    cam1_stagger_sec: float = 5.0,
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
        # Fixed focus (lens position): only applies to cameras that support it (e.g. Camera Module 3).
        autofocus = (cam_cfg.get("autofocus") or "continuous").strip().lower()
        lens_position = cam_cfg.get("lens_position")
        if autofocus == "manual" and lens_position is not None:
            try:
                lp = float(lens_position)
                cmd.extend(["-af", "manual", "-l", str(lp)])
                logger.info("%s: fixed focus (lens_position=%.2f)", cam_key, lp)
            except (TypeError, ValueError):
                pass
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
    if cam1.get("enabled", True) and cam1_stagger_sec > 0:
        # Stagger so cam0 fully opens and binds before cam1 (reduces V4L2/libcamera contention on Pi 5)
        logger.info("Waiting %.1f s before starting cam1...", cam1_stagger_sec)
        time.sleep(cam1_stagger_sec)
    start_spyglass("cam1", 1, cam1, spyglass_port_cam1)

    if not processes:
        logger.warning("No Spyglass instances started (all cameras disabled?)")
        return processes

    logger.info(
        "Spyglass streams: http://<pi-ip>:%d/stream and http://<pi-ip>:%d/stream (MJPEG)",
        spyglass_port_cam0, spyglass_port_cam1,
    )
    return processes
