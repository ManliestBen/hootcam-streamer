"""Load streamer config from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

_DEFAULTS = {
    "spyglass_port_cam0": 8082,
    "spyglass_port_cam1": 8083,
    "spyglass_cam1_stagger_sec": 5.0,
    "streamer_api_port": 8084,
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
    for key in ("spyglass_port_cam0", "spyglass_port_cam1", "spyglass_cam1_stagger_sec", "streamer_api_port"):
        if key in data:
            out[key] = data[key]
    for cam in ("cam0", "cam1"):
        if cam in data and isinstance(data[cam], dict):
            out[cam] = {**_DEFAULTS[cam], **data[cam]}
    return out


def save_config(path: Path, config: dict[str, Any]) -> None:
    """Write config dict to YAML. Merges with defaults so only set keys are written."""
    try:
        import yaml
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise RuntimeError(f"Could not write config to {path}: {e}") from e
