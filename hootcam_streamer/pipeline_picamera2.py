"""Dual-camera pipeline using Picamera2 in a single process (works on Pi 5)."""
from __future__ import annotations

import logging
import signal
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

_keep_running = True


def _stop_handler(_signum: int, _frame: object) -> None:
    global _keep_running
    _keep_running = False


def run_picamera2_pipeline(
    rtsp_base: str,
    cam0: dict[str, Any],
    cam1: dict[str, Any],
) -> None:
    """Run two cameras in one process with Picamera2, pushing H.264 to RTSP via ffmpeg.

    Requires: pip install picamera2
    """
    try:
        from picamera2 import Picamera2
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import Output as Picamera2Output
    except ImportError as e:
        raise RuntimeError(
            "Picamera2 backend requires the picamera2 package. Install with: pip install picamera2"
        ) from e

    class _RTSPOutput(Picamera2Output):
        """Pipes H.264 to ffmpeg with -f h264 so MediaMTX accepts it (avoids 400 Bad Request)."""

        def __init__(self, rtsp_url: str) -> None:
            try:
                super().__init__()
            except TypeError:
                super().__init__(pts=None)
            self.rtsp_url = rtsp_url
            self.ffmpeg: subprocess.Popen[bytes] | None = None
            self.recording = False
            self.needs_pacing = True

        def start(self) -> None:
            self.ffmpeg = subprocess.Popen(
                [
                    "ffmpeg",
                    "-hide_banner", "-loglevel", "warning",
                    "-f", "h264",
                    "-i", "pipe:0",
                    "-c:v", "copy",
                    "-f", "rtsp",
                    self.rtsp_url,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.recording = True

        def stop(self) -> None:
            self.recording = False
            if self.ffmpeg is not None and self.ffmpeg.stdin is not None:
                try:
                    self.ffmpeg.stdin.close()
                except Exception:
                    pass
                try:
                    self.ffmpeg.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.ffmpeg.kill()
                self.ffmpeg = None

        def outputframe(
            self,
            frame: bytes,
            keyframe: bool = True,
            timestamp: int | None = None,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            if not self.recording or self.ffmpeg is None or self.ffmpeg.stdin is None:
                return
            try:
                self.ffmpeg.stdin.write(frame)
                self.ffmpeg.stdin.flush()
            except (BrokenPipeError, OSError):
                if self.ffmpeg is not None:
                    logger.warning(
                        "RTSP output pipe closed (ffmpeg or MediaMTX disconnected): %s",
                        self.rtsp_url,
                    )
                    # Close stdin before clearing reference so gc doesn't raise again ("Exception ignored")
                    try:
                        self.ffmpeg.stdin.close()
                    except Exception:
                        pass
                self.ffmpeg = None
            except Exception:
                pass

    global _keep_running
    _keep_running = True
    signal.signal(signal.SIGINT, _stop_handler)
    signal.signal(signal.SIGTERM, _stop_handler)

    cameras: list[tuple[str, Picamera2, H264Encoder | None]] = []

    def setup_camera(cam_key: str, camera_index: int, cam_cfg: dict[str, Any]) -> None:
        if not cam_cfg.get("enabled", True):
            logger.info("Skipping %s (disabled)", cam_key)
            cameras.append((cam_key, None, None))
            return
        w = int(cam_cfg.get("width", 1920))
        h = int(cam_cfg.get("height", 1080))
        fps = int(cam_cfg.get("fps", 25))
        bitrate = int(cam_cfg.get("bitrate", 4000000))
        path_name = "cam0" if camera_index == 0 else "cam1"
        rtsp_url = f"{rtsp_base}/{path_name}"

        picam2 = Picamera2(camera_index)
        video_config = picam2.create_video_configuration(
            main={"size": (w, h), "format": "YUV420"}
        )
        picam2.configure(video_config)
        picam2.set_controls({"FrameRate": fps})

        encoder = H264Encoder(bitrate=bitrate, repeat=True, iperiod=15)
        # Use our own RTSP output (ffmpeg -f h264 -i pipe:0) so MediaMTX accepts the stream.
        # FfmpegOutput's built-in ffmpeg can cause "400 Bad Request (incorrect codec parameters)".
        output = _RTSPOutput(rtsp_url)
        encoder.output = output

        logger.info(
            "Starting %s (Picamera2 camera %s): %dx%d @ %d fps -> %s",
            cam_key,
            camera_index,
            w,
            h,
            fps,
            rtsp_url,
        )
        picam2.start()
        picam2.start_encoder(encoder)
        cameras.append((cam_key, picam2, encoder))

    setup_camera("cam0", 0, cam0)
    if cam1.get("enabled", True):
        # Longer delay so cam0 is fully streaming before cam1 starts (reduces V4L2 "Failed to queue buffer" on Pi 5)
        time.sleep(4.0)
    setup_camera("cam1", 1, cam1)

    if not any(c[1] is not None for c in cameras):
        logger.warning("No cameras enabled in Picamera2 pipeline")
        return

    logger.info("Picamera2 pipeline running (both cameras in one process). Ctrl+C to stop.")
    try:
        while _keep_running:
            time.sleep(1)
    finally:
        for cam_key, picam2, encoder in cameras:
            if picam2 is None:
                continue
            try:
                if encoder is not None:
                    picam2.stop_encoder(encoder)
                picam2.stop()
            except Exception as e:
                logger.warning("Error stopping %s: %s", cam_key, e)
