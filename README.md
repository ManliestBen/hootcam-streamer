# Hootcam Streamer

Runs on the **Raspberry Pi** and publishes **two MJPEG streams** (one per CSI camera) using [Spyglass](https://github.com/ManliestBen/spyglass). No motion detection or recording—only capture and stream so the Pi stays lightweight.

Part of the **3-part Hootcam** setup:

- **Pi (this app)** – Capture and stream only. Output: `http://<pi-ip>:8080/stream` and `http://<pi-ip>:8081/stream` (MJPEG).
- **NUC – [Hootcam Motion](https://github.com/ManliestBen/hootcam-motion)** – Pulls those streams, runs motion detection and recording, serves the API and MJPEG for the UI.
- **UI – [Hootcam UI](https://github.com/ManliestBen/hootcam-ui)** – Web interface; talks to the NUC only.

## Requirements

- Raspberry Pi OS (Bullseye or later) with libcamera
- Two CSI cameras (or one; set `cam1.enabled: false` to use only cam0)
- [Spyglass](https://github.com/ManliestBen/spyglass) – MJPEG server for Picamera2. Install in the same venv (see Quick start).

## Quick start

1. **Install system deps** (libcamera + Picamera2 for Spyglass):

   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2
   ```

2. **Create a virtualenv and install deps** (use `--system-site-packages` so Spyglass can use system Picamera2):

   ```bash
   cd hootcam-streamer
   python3 -m venv --system-site-packages .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install git+https://github.com/ManliestBen/spyglass.git
   ```

3. **Copy and edit config** (optional):

   ```bash
   cp config.example.yaml config.yaml
   # edit config.yaml for resolution, fps, or ports
   ```

4. **Run** (with venv activated):

   ```bash
   python -m hootcam_streamer
   # or: python -m hootcam_streamer --config /path/to/config.yaml
   ```

Streams:

- **cam0:** `http://<pi-ip>:8080/stream` (and `/snapshot`)
- **cam1:** `http://<pi-ip>:8081/stream` (and `/snapshot`)

### Testing the streams

With the streamer running, open in a browser or use curl:

- **cam0:** `http://<pi-ip>:8080/stream`
- **cam1:** `http://<pi-ip>:8081/stream`

Or from the Pi: `curl http://127.0.0.1:8080/snapshot -o snap.jpg`

## Configuring Hootcam Motion and Hootcam UI

### Hootcam Motion (NUC)

Hootcam Motion reads each camera’s **stream_url** and supports both RTSP and **MJPEG over HTTP**. For this streamer (Spyglass), use the MJPEG URLs:

1. In the UI: **Cameras → Camera 0 → Config** (or Camera 1), set **Stream URL** to:
   - **Camera 0:** `http://<pi-ip>:8080/stream`
   - **Camera 1:** `http://<pi-ip>:8081/stream`

   Replace `<pi-ip>` with your Pi’s IP (e.g. `192.168.1.10`).

2. Or via API:  
   `PATCH /cameras/0/config` with `{ "stream_url": "http://192.168.1.10:8080/stream" }`  
   `PATCH /cameras/1/config` with `{ "stream_url": "http://192.168.1.10:8081/stream" }`

OpenCV (used by Hootcam Motion) can read these MJPEG HTTP URLs the same way it reads RTSP.

### Hootcam UI

Point the UI at **Hootcam Motion** (the NUC), not at the Pi. In the UI’s `.env`:

```env
VITE_HOOTCAM_STREAMER_URL=http://<nuc-ip>:8080
```

Use your NUC’s IP and the port Hootcam Motion runs on (default 8080). The UI then gets live streams and the API from Hootcam Motion; no direct connection to the Pi is needed.

## Config (config.yaml)

| Key | Default | Description |
|-----|---------|-------------|
| `spyglass_port_cam0` / `spyglass_port_cam1` | `8080` / `8081` | Ports for the two Spyglass instances. Streams at `http://<pi-ip>:8080/stream` and `http://<pi-ip>:8081/stream`. |
| `spyglass_cam1_stagger_sec` | `5.0` | Seconds to wait after starting cam0 before starting cam1. Reduces V4L2/libcamera contention on Pi 5; increase (e.g. 7–8) if the second stream fails. |
| `cam0` / `cam1` | — | Per-camera options (see below). |

Per-camera (`cam0`, `cam1`):

| Key | Default | Description |
|-----|---------|-------------|
| `width` | `1920` | Width. |
| `height` | `1080` | Height. |
| `fps` | `25` | Framerate. |
| `bitrate` | `4000000` | Ignored by Spyglass (MJPEG). Kept for config compatibility. |
| `enabled` | `true` | Set `false` to disable a camera. |

## Troubleshooting

- **"Spyglass not found"** – Install Spyglass in the same virtualenv: `pip install git+https://github.com/ManliestBen/spyglass.git`. Spyglass needs system Picamera2: `sudo apt install -y python3-picamera2`, and use a venv with `--system-site-packages` so the venv can see it.

- **Only one camera / second stream (8081) fails** – On Pi 5 the two Spyglass processes can contend for the camera pipeline. The app waits **5 seconds** between starting cam0 and cam1 by default. If cam1 still fails, increase `spyglass_cam1_stagger_sec` in `config.yaml` (e.g. 7 or 8). Alternatively reboot and run again, or set `cam1.enabled: false` to use a single camera.

## How it works

The app starts two [Spyglass](https://github.com/ManliestBen/spyglass) processes (one per camera), each serving MJPEG at its own port. Spyglass uses Pi 5–friendly options (`--use_sw_jpg_encoding`, `--disable_webrtc`) by default. Resolution and FPS come from `cam0`/`cam1` in config.

## Stopping

Send SIGINT (Ctrl+C) or SIGTERM; the process will stop both Spyglass instances.

## Running as a service (start on boot)

To run Hootcam Streamer automatically on the Pi after reboot:

1. Copy the systemd unit: `sudo cp contrib/hootcam-streamer.service /etc/systemd/system/`
2. If your install path is not `/home/pi/hootcam-streamer`, edit the unit and set `WorkingDirectory` and the path in `ExecStart` (default uses `.venv/bin/python`).
3. Run: `sudo systemctl daemon-reload`, `sudo systemctl enable hootcam-streamer`, `sudo systemctl start hootcam-streamer`, `sudo systemctl status hootcam-streamer`.

See **contrib/README.md** for full steps and options (e.g. custom config path).

## See also

- [**Hootcam Motion**](https://github.com/ManliestBen/hootcam-motion) – Consumes these MJPEG streams (or RTSP), runs motion detection, recording, and the API. Run on the NUC. Set each camera’s `stream_url` to `http://<pi-ip>:8080/stream` and `http://<pi-ip>:8081/stream`.
- [**Hootcam UI**](https://github.com/ManliestBen/hootcam-ui) – Web frontend; point it at Hootcam Motion (not at the Pi).
- [**Spyglass**](https://github.com/ManliestBen/spyglass) – MJPEG server for Picamera2 used by this app.
