"""Main entry: run two Spyglass instances (one per camera) for MJPEG streaming."""
from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import load_config

logger = logging.getLogger(__name__)

_processes: list[tuple[str, subprocess.Popen]] = []


def _sig_handler(_signum: int, _frame: object) -> None:
    for _label, p in _processes:
        try:
            p.terminate()
        except Exception:
            pass
    raise SystemExit(0)


def main() -> None:
    global _processes
    parser = argparse.ArgumentParser(
        description="Hootcam Streamer: two Spyglass MJPEG streams from Pi CSI cameras"
    )
    parser.add_argument("--config", "-c", type=Path, default=Path("config.yaml"), help="Config YAML path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args.config)
    cam0 = config.get("cam0", {})
    cam1 = config.get("cam1", {})
    spyglass_port_cam0 = int(config.get("spyglass_port_cam0", 8082))
    spyglass_port_cam1 = int(config.get("spyglass_port_cam1", 8083))
    cam1_stagger_sec = float(config.get("spyglass_cam1_stagger_sec", 5.0))

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        from .pipeline_spyglass import run_spyglass_pipeline
        try:
            procs = run_spyglass_pipeline(cam0, cam1, spyglass_port_cam0, spyglass_port_cam1, cam1_stagger_sec)
        except RuntimeError as e:
            logger.error("%s", e)
            sys.exit(1)
        _processes.extend(procs)
        if not _processes:
            logger.warning("No Spyglass instances started (all cameras disabled)")
        while _processes:
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
