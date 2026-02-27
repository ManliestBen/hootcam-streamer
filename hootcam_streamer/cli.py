"""Main entry: start MediaMTX and two libcamera-vid | ffmpeg pipelines."""
from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
from pathlib import Path

from .config import load_config

logger = logging.getLogger(__name__)

_processes: list[subprocess.Popen] = []


def _sig_handler(_signum: int, _frame: object) -> None:
    for p in _processes:
        try:
            p.terminate()
        except Exception:
            pass
    raise SystemExit(0)


def main() -> None:
    global _processes
    parser = argparse.ArgumentParser(description="Hootcam Streamer: RTSP from Pi CSI cameras")
    parser.add_argument("--config", "-c", type=Path, default=Path("config.yaml"), help="Config YAML path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args.config)
    mediamtx_path = config.get("mediamtx_path", "mediamtx")
    rtsp_port = config.get("rtsp_port", 8554)
    cam0 = config.get("cam0", {})
    cam1 = config.get("cam1", {})

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # 1) Start MediaMTX (no config file = default allow all)
    mtx_cmd = [mediamtx_path]
    if str(rtsp_port) != "8554":
        mtx_cmd.extend(["--rtspPort", str(rtsp_port)])
    logger.info("Starting MediaMTX: %s", " ".join(mtx_cmd))
    mtx = subprocess.Popen(
        mtx_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    _processes.append(mtx)

    # Give MediaMTX a moment to bind
    import time
    time.sleep(1)
    if mtx.poll() is not None:
        _, err = mtx.communicate()
        logger.error("MediaMTX exited: %s", err.decode() if err else "unknown")
        sys.exit(1)

    rtsp_base = f"rtsp://127.0.0.1:{rtsp_port}"

    def start_camera_pipeline(cam_key: str, camera_index: int, cam_cfg: dict) -> None:
        if not cam_cfg.get("enabled", True):
            logger.info("Skipping %s (disabled)", cam_key)
            return
        w = cam_cfg.get("width", 1920)
        h = cam_cfg.get("height", 1080)
        fps = cam_cfg.get("fps", 25)
        # libcamera-vid: -t 0 = run forever, -n = no preview, -c = camera index, -o - = stdout H.264
        libcam_cmd = [
            "libcamera-vid",
            "-t", "0",
            "-n",
            "-c", str(camera_index),
            "--width", str(w),
            "--height", str(h),
            "--framerate", str(fps),
            "--codec", "h264",
            "-o", "-",
        ]
        # ffmpeg: read H.264 from stdin, copy to RTSP
        path_name = "cam0" if camera_index == 0 else "cam1"
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "warning",
            "-f", "h264",
            "-i", "pipe:0",
            "-c:v", "copy",
            "-f", "rtsp",
            f"{rtsp_base}/{path_name}",
        ]
        logger.info("Starting pipeline %s: libcamera-vid | ffmpeg -> %s/%s", cam_key, rtsp_base, path_name)
        # Use a pipe: libcamera-vid stdout -> ffmpeg stdin
        libcam = subprocess.Popen(
            libcam_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        _processes.append(libcam)
        ffmpeg = subprocess.Popen(
            ffmpeg_cmd,
            stdin=libcam.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        libcam.stdout = None  # allow libcam to get SIGPIPE when ffmpeg exits
        _processes.append(ffmpeg)

    start_camera_pipeline("cam0", 0, cam0)
    start_camera_pipeline("cam1", 1, cam1)

    logger.info("Streams: %s/cam0 and %s/cam1 (replace 127.0.0.1 with Pi IP for remote access)", rtsp_base, rtsp_base)

    # Wait for any process to exit (then we'll exit and cleanup)
    try:
        while True:
            for p in _processes:
                if p.poll() is not None:
                    logger.warning("Process %s exited with %s", p, p.returncode)
                    raise SystemExit(1)
            time.sleep(2)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        for p in _processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            except Exception:
                pass
