"""Load streamer config from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

_DEFAULTS = {
    "mediamtx_path": "mediamtx",
    "rtsp_port": 8554,
    "backend": "rpicam-vid",  # "rpicam-vid" | "picamera2" | "spyglass"
    "spyglass_port_cam0": 8080,
    "spyglass_port_cam1": 8081,
    "kill_leftover_processes": True,
    "cam0": {"enabled": True, "width": 1920, "height": 1080, "fps": 25, "bitrate": 4000000},
    "cam1": {"enabled": True, "width": 1920, "height": 1080, "fps": 25, "bitrate": 4000000},
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path("config.yaml")
    if not path.is_file():
        return dict(_DEFAULTS)
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return dict(_DEFAULTS)
    out = dict(_DEFAULTS)
    for key in ("mediamtx_path", "rtsp_port", "mediamtx_rtp_port", "kill_leftover_processes", "backend", "spyglass_port_cam0", "spyglass_port_cam1"):
        if key in data:
            out[key] = data[key]
    for cam in ("cam0", "cam1"):
        if cam in data and isinstance(data[cam], dict):
            out[cam] = {**_DEFAULTS[cam], **data[cam]}
    return out
