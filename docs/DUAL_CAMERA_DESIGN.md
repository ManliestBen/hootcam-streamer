# Dual-camera streaming on Raspberry Pi

## Problem

On **Raspberry Pi 5**, libcamera’s pipeline handler is effectively single-process: the first `rpicam-vid` (or any libcamera-using process) locks it. A second `rpicam-vid` cannot open the other camera and fails with “Pipeline handler in use” or “Device or resource busy”. So the default design (two separate `rpicam-vid | ffmpeg` processes) only works for **one camera** on Pi 5.

## Design options

### 1. Two processes (rpicam-vid) — **default, single-camera on Pi 5**

- **How:** One subprocess per camera: `rpicam-vid -c 0 ... | ffmpeg ...` and `rpicam-vid -c 1 ... | ffmpeg ...`.
- **Pros:** No Python camera stack; minimal deps (rpicam-apps, ffmpeg, mediamtx); works well on Pi 4 and for **one** camera on Pi 5.
- **Cons:** On Pi 5, only the first process can use the pipeline; the second camera fails.

**Use when:** Single camera, or Pi 4 (where two processes can work).

### 2. Single process, two cameras (Picamera2) — **dual-camera on Pi 5**

- **How:** One Python process creates two `Picamera2` instances (`Picamera2(0)` and `Picamera2(1)`), each with its own video config and `H264Encoder` + `FfmpegOutput` to RTSP. MediaMTX still runs as a separate process. Both cameras run in the same process, so there is only one “user” of the pipeline from the kernel’s point of view.
- **Pros:** Both cameras work on Pi 5; same RTSP URLs and MediaMTX setup.
- **Cons:** Requires the `picamera2` Python package (and its system deps); more CPU/memory in the Python process; two encoders and two ffmpeg children.

**Use when:** Two CSI cameras on Pi 5 (or when you want both streams from one app).

### 3. Other options (not implemented)

- **GStreamer + libcamerasrc:** Two pipelines in one process might work but has seen assertion failures with two cameras; would add GStreamer as a dependency.
- **Single rpicam-vid with two outputs:** `rpicam-vid` does not support multiple cameras or multiple RTSP outputs in one process.
- **V4L2 directly:** Bypassing libcamera loses hardware H.264 and the standard Pi camera stack; not recommended.

## Config

In `config.yaml`:

```yaml
# Backend: "rpicam-vid" (default) or "picamera2".
# Use "picamera2" for dual-camera on Pi 5.
backend: rpicam-vid
```

- **`backend: rpicam-vid`** — Two subprocess pipelines (cam0, cam1). On Pi 5, only cam0 is reliable; set `cam1.enabled: false` for single-camera.
- **`backend: picamera2`** — Single Python process with two Picamera2 instances; both cam0 and cam1 work on Pi 5. Requires `pip install picamera2` (and system libcamera/picamera2 stack).

## Summary

| Goal                     | Backend       | Pi 5              | Pi 4 (or older)   |
|--------------------------|---------------|-------------------|-------------------|
| One camera               | rpicam-vid    | ✅                | ✅                |
| Two cameras              | picamera2     | ✅                | ✅                |
| Two cameras              | rpicam-vid    | ❌ (second fails) | ✅ (often works)  |
