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
- **Camera capture**: Either **rpicam-vid** (default) or **Picamera2** (for dual-camera on Pi 5). For the default backend: `sudo apt install -y libcamera-apps` or `rpicam-apps` on Bookworm+. Picamera2 is included in `requirements.txt`; install Python deps (step 3 below) to use `backend: picamera2`.

## Quick start

1. Install MediaMTX (example for arm64). Writing to `/usr/local/bin` requires `sudo`:

   ```bash
   wget -qO- https://github.com/bluenviron/mediamtx/releases/download/v1.11.0/mediamtx_v1.11.0_linux_arm64v8.tar.gz | sudo tar xz -C /usr/local/bin
   ```

   If you prefer not to use sudo, extract to a writable directory (e.g. `~/bin` or the project) and set `mediamtx_path` in `config.yaml` to the full path to the `mediamtx` binary:

   ```bash
   mkdir -p ~/bin
   wget -qO- https://github.com/bluenviron/mediamtx/releases/download/v1.11.0/mediamtx_v1.11.0_linux_arm64v8.tar.gz | tar xz -C ~/bin
   # Then in config.yaml: mediamtx_path: /home/pi/bin/mediamtx  (adjust user/path as needed)
   ```

2. Install system deps (if not already):

   ```bash
   sudo apt install -y ffmpeg libcamera-apps
   # On Raspberry Pi OS Bookworm and later you may need: sudo apt install -y rpicam-apps
   ```

3. **Create a virtualenv and install Python deps** (recommended; keeps deps isolated). This installs PyYAML (for config) and picamera2 (for dual-camera on Pi 5 when using `backend: picamera2`):

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

### Dual-camera on Raspberry Pi 5

On Pi 5, the default backend can only use one camera (the second fails with "Pipeline handler in use"). To use **both** cameras: install Python deps from `requirements.txt` (step 3 above; includes picamera2), set `backend: picamera2` in `config.yaml`, then run `python -m hootcam_streamer`. See [docs/DUAL_CAMERA_DESIGN.md](docs/DUAL_CAMERA_DESIGN.md).

## Config (config.yaml)

| Key | Default | Description |
|-----|---------|-------------|
| `mediamtx_path` | `mediamtx` | Path to MediaMTX binary (or `mediamtx` if in PATH). |
| `rtsp_port` | `8554` | Port MediaMTX listens on (RTSP). |
| `mediamtx_rtp_port` | *(none)* | If port 8000 (RTP) or 8001 (RTCP) is in use, set an alternate RTP port (e.g. `8010`); RTCP will use this + 1. |
| `kill_leftover_processes` | `true` | On startup, send SIGTERM to any leftover `rpicam-vid`/`libcamera-vid`/`mediamtx` from a previous crash so cameras and ports are free. Set to `false` if you run multiple instances or other apps using the same binaries. |
| `backend` | `rpicam-vid` | `rpicam-vid` (default) or `picamera2`. Use **`picamera2`** for **two cameras on Pi 5** (single process avoids "Pipeline handler in use"). Picamera2 is installed via `pip install -r requirements.txt`. |
| `cam0` / `cam1` | — | Per-camera options (see below). |

Per-camera (`cam0`, `cam1`):

| Key | Default | Description |
|-----|---------|-------------|
| `width` | `1920` | Width. |
| `height` | `1080` | Height. |
| `fps` | `25` | Framerate. |
| `bitrate` | `4000000` | H.264 bitrate (bits/sec). |
| `enabled` | `true` | Set `false` to disable a camera. |

## Troubleshooting

- **Port 8000 (or 8001) already in use** — MediaMTX uses UDP 8000 (RTP) and 8001 (RTCP) by default. Set `mediamtx_rtp_port` in `config.yaml` to an unused port (e.g. `8010`). MediaMTX will then use that port and the next for RTP/RTCP.

- **Pipeline/camera in use after a crash** — By default, on startup the app sends SIGTERM then SIGKILL to any leftover `rpicam-vid`, `libcamera-vid`, and `mediamtx` processes, then waits before starting so cameras are free. The two camera pipelines are also started with a short stagger so they don’t contend for the libcamera pipeline (Pi 5). To disable cleanup (e.g. if you run multiple instances), set `kill_leftover_processes: false` in `config.yaml`.

- **Pi 5: second camera fails with "Pipeline handler in use" or "Device or resource busy"** — With the default `rpicam-vid` backend, only one process can use the pipeline on Pi 5. **Fix:** use the **Picamera2** backend so both cameras run in one process: set `backend: picamera2` in `config.yaml` and run `pip install picamera2`. See [docs/DUAL_CAMERA_DESIGN.md](docs/DUAL_CAMERA_DESIGN.md). Alternatively, use a single camera: set `cam1.enabled: false`.

## How it works

1. **MediaMTX** runs as the RTSP server (port 8554).
2. For each camera, **rpicam-vid** or **libcamera-vid** captures from the CSI camera and outputs H.264 to stdout.
3. **FFmpeg** reads that stream and publishes it to MediaMTX as `rtsp://127.0.0.1:8554/cam0` (or `cam1`).

No Python camera bindings are required at runtime; only MediaMTX and the two pipelines are used. This keeps CPU and dependencies minimal on the Pi.

## Stopping

Send SIGINT (Ctrl+C) or SIGTERM; the process will stop MediaMTX and the camera/ffmpeg pipelines.

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
