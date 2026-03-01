"""Main entry: start MediaMTX and two camera-vid | ffmpeg pipelines."""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import load_config

logger = logging.getLogger(__name__)

_processes: list[tuple[str, subprocess.Popen]] = []

# Newer Pi OS uses rpicam-vid; older uses libcamera-vid. Same CLI for our options.
CAMERA_VID_BINARIES = ("rpicam-vid", "libcamera-vid")


def _camera_vid_binary() -> str | None:
    """Return the camera capture binary to use (rpicam-vid or libcamera-vid), or None."""
    for name in CAMERA_VID_BINARIES:
        if shutil.which(name):
            return name
    return None


def _kill_leftover_processes() -> None:
    """Kill any leftover camera/MediaMTX processes from a previous crash so cameras and ports are free."""
    # pkill sends SIGTERM; process names must match exactly (no path).
    for name in (*CAMERA_VID_BINARIES, "mediamtx"):
        try:
            subprocess.run(
                ["pkill", "-TERM", name],
                capture_output=True,
                timeout=2,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
    time.sleep(1.5)  # Give processes time to release cameras and ports


def _sig_handler(_signum: int, _frame: object) -> None:
    for _label, p in _processes:
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
    mediamtx_rtp_port = config.get("mediamtx_rtp_port")
    kill_leftovers = config.get("kill_leftover_processes", True)
    cam0 = config.get("cam0", {})
    cam1 = config.get("cam1", {})

    if kill_leftovers:
        logger.info("Cleaning up any leftover camera/MediaMTX processes from previous run...")
        _kill_leftover_processes()

    # Require system binaries (not in venv)
    if not shutil.which(mediamtx_path):
        logger.error("MediaMTX binary not found: %s. Install from https://github.com/bluenviron/mediamtx/releases", mediamtx_path)
        sys.exit(1)
    camera_vid = _camera_vid_binary()
    if not camera_vid:
        logger.error(
            "No camera capture binary found (tried: %s). Install with: sudo apt install -y libcamera-apps (or rpicam-apps on newer Pi OS)",
            ", ".join(CAMERA_VID_BINARIES),
        )
        sys.exit(1)
    logger.info("Using camera binary: %s", camera_vid)
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found. Install with: sudo apt install -y ffmpeg")
        sys.exit(1)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # 1) Start MediaMTX (no config file = default allow all)
    mtx_cmd = [mediamtx_path]
    if str(rtsp_port) != "8554":
        mtx_cmd.extend(["--rtspPort", str(rtsp_port)])
    mtx_env = os.environ.copy()
    if mediamtx_rtp_port is not None:
        rtp_port = int(mediamtx_rtp_port)
        mtx_env["MTX_RTPADDRESS"] = f":{rtp_port}"
        mtx_env["MTX_RTCPADDRESS"] = f":{rtp_port + 1}"
        logger.info("MediaMTX RTP/RTCP ports: %s / %s", rtp_port, rtp_port + 1)
    logger.info("Starting MediaMTX: %s", " ".join(mtx_cmd))
    mtx = subprocess.Popen(
        mtx_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=mtx_env,
    )
    _processes.append(("MediaMTX", mtx))

    # Give MediaMTX a moment to bind
    time.sleep(1)
    if mtx.poll() is not None:
        _, err = mtx.communicate()
        msg = err.decode(errors="replace").strip() if err else ""
        parts = [f"exit code {mtx.returncode}"]
        if msg:
            parts.append(msg)
        logger.error("MediaMTX exited: %s", " — ".join(parts) or "unknown")
        logger.error("Run '%s' in a terminal to see MediaMTX output and fix the issue.", " ".join(mtx_cmd))
        sys.exit(1)

    rtsp_base = f"rtsp://127.0.0.1:{rtsp_port}"

    def start_camera_pipeline(cam_key: str, camera_index: int, cam_cfg: dict) -> None:
        if not cam_cfg.get("enabled", True):
            logger.info("Skipping %s (disabled)", cam_key)
            return
        w = cam_cfg.get("width", 1920)
        h = cam_cfg.get("height", 1080)
        fps = cam_cfg.get("fps", 25)
        # rpicam-vid / libcamera-vid: -t 0 = run forever, -n = no preview, -c = camera index, -o - = stdout.
        # --libav-format required when writing to stdout (Pi 5 / newer libav backend).
        libcam_cmd = [
            camera_vid,
            "-t", "0",
            "-n",
            "-c", str(camera_index),
            "--width", str(w),
            "--height", str(h),
            "--framerate", str(fps),
            "--codec", "h264",
            "--libav-format", "h264",
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
        logger.info("Starting pipeline %s: %s | ffmpeg -> %s/%s", cam_key, camera_vid, rtsp_base, path_name)
        # Use a pipe: camera stdout -> ffmpeg stdin
        libcam = subprocess.Popen(
            libcam_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _processes.append((f"{cam_key}/{camera_vid}", libcam))
        ffmpeg = subprocess.Popen(
            ffmpeg_cmd,
            stdin=libcam.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        libcam.stdout = None  # allow libcam to get SIGPIPE when ffmpeg exits
        _processes.append((f"{cam_key}/ffmpeg", ffmpeg))

    start_camera_pipeline("cam0", 0, cam0)
    start_camera_pipeline("cam1", 1, cam1)

    logger.info("Streams: %s/cam0 and %s/cam1 (replace 127.0.0.1 with Pi IP for remote access)", rtsp_base, rtsp_base)

    # Wait for any process to exit (then we'll exit and cleanup)
    try:
        while True:
            for label, p in _processes:
                if p.poll() is not None:
                    err_msg = ""
                    if p.stderr is not None:
                        try:
                            err_msg = p.stderr.read().decode(errors="replace").strip()
                        except Exception:
                            pass
                    logger.warning("Process %s exited with %s", label, p.returncode)
                    if err_msg:
                        for line in err_msg.splitlines():
                            logger.warning("  %s", line)
                    raise SystemExit(1)
            time.sleep(2)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        for _label, p in _processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            except Exception:
                pass
