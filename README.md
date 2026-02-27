# Hootcam Streamer

Runs on the **Raspberry Pi** and publishes **two RTSP streams** (one per CSI camera). No motion detection or recording—only high-quality, high-framerate video output so the Pi stays lightweight.

Part of the **3-part Hootcam** setup:

- **Pi (this app)** – Capture and stream only. Output: `rtsp://<pi-ip>:8554/cam0` and `cam1`.
- **NUC – [Hootcam Motion](https://github.com/ManliestBen/hootcam-motion)** – Pulls those RTSP streams, runs motion detection and recording, serves the API and MJPEG for the UI.
- **UI – [Hootcam UI](https://github.com/ManliestBen/hootcam-ui)** – Web interface; talks to the NUC only.

## Requirements

- Raspberry Pi OS (Bullseye or later) with libcamera
- Two CSI cameras (or one; second stream will not start)
- **MediaMTX** (RTSP server): [releases](https://github.com/bluenviron/mediamtx/releases)
- **FFmpeg** (with libcamera or H.264 input)
- **libcamera-vid** (from `libcamera-apps`: `sudo apt install -y libcamera-apps`)

## Quick start

1. Install MediaMTX (example for arm64):

   ```bash
   wget -qO- https://github.com/bluenviron/mediamtx/releases/download/v1.11.0/mediamtx_v1.11.0_linux_arm64v8.tar.gz | tar xz -C /usr/local/bin
   ```

2. Install system deps (if not already):

   ```bash
   sudo apt install -y ffmpeg libcamera-apps
   ```

3. **Create a virtualenv and install Python deps** (recommended; keeps deps isolated):

   ```bash
   cd hootcam-streamer
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Copy and edit config (optional):

   ```bash
   cp config.example.yaml config.yaml
   # edit config.yaml for resolution, fps, bitrate
   ```

5. Run (with venv activated):

   ```bash
   python -m hootcam_streamer
   # or: python -m hootcam_streamer --config /path/to/config.yaml
   ```

Streams will be at:

- `rtsp://<pi-ip>:8554/cam0`
- `rtsp://<pi-ip>:8554/cam1`

Configure [**Hootcam Motion**](https://github.com/ManliestBen/hootcam-motion) (on the NUC) with these URLs as each camera’s `stream_url` (e.g. `rtsp://192.168.1.10:8554/cam0` for camera 0, using the Pi’s IP).

## Config (config.yaml)

| Key | Default | Description |
|-----|---------|-------------|
| `mediamtx_path` | `mediamtx` | Path to MediaMTX binary (or `mediamtx` if in PATH). |
| `rtsp_port` | `8554` | Port MediaMTX listens on. |
| `cam0` / `cam1` | — | Per-camera options (see below). |

Per-camera (`cam0`, `cam1`):

| Key | Default | Description |
|-----|---------|-------------|
| `width` | `1920` | Width. |
| `height` | `1080` | Height. |
| `fps` | `25` | Framerate. |
| `bitrate` | `4000000` | H.264 bitrate (bits/sec). |
| `enabled` | `true` | Set `false` to disable a camera. |

## How it works

1. **MediaMTX** runs as the RTSP server (port 8554).
2. For each camera, **libcamera-vid** captures from the CSI camera and outputs H.264 to stdout.
3. **FFmpeg** reads that stream and publishes it to MediaMTX as `rtsp://127.0.0.1:8554/cam0` (or `cam1`).

No Python camera bindings are required at runtime; only MediaMTX and the two pipelines are used. This keeps CPU and dependencies minimal on the Pi.

## Stopping

Send SIGINT (Ctrl+C) or SIGTERM; the process will stop MediaMTX and the ffmpeg/libcamera-vid pipelines.

## Running as a service (start on boot)

To run Hootcam Streamer automatically on the Pi after reboot:

1. Copy the systemd unit: `sudo cp contrib/hootcam-streamer.service /etc/systemd/system/`
2. If your install path is not `/home/pi/hootcam-streamer`, edit the unit and set `WorkingDirectory` and the path in `ExecStart` (default uses `.venv/bin/python`; if you skipped the venv, use `/usr/bin/python3`).
3. Run: `sudo systemctl daemon-reload`, `sudo systemctl enable hootcam-streamer`, `sudo systemctl start hootcam-streamer`, `sudo systemctl status hootcam-streamer`.

See **contrib/README.md** for full steps and options (e.g. custom config path).

## See also

- [**Hootcam Motion**](https://github.com/ManliestBen/hootcam-motion) – Consumes these RTSP streams and runs motion detection, recording, and the API. Run on the NUC.
- [**Hootcam UI**](https://github.com/ManliestBen/hootcam-ui) – Web frontend; point it at Hootcam Motion (not at the Pi).
- [**Hootcam Server**](https://github.com/ManliestBen/hootcam-server) – Legacy all-in-one Pi backend (alternative to the 3-part setup).
