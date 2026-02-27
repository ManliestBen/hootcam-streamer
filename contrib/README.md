# Hootcam Streamer – systemd service

## Run on boot (Pi)

1. Complete the main [README](../README.md) setup (MediaMTX, ffmpeg, libcamera-apps, optional config.yaml).

2. Copy the unit file:
   ```bash
   sudo cp contrib/hootcam-streamer.service /etc/systemd/system/
   ```

3. If your install path is not `/home/pi/hootcam-streamer`, edit the unit:
   ```bash
   sudo nano /etc/systemd/system/hootcam-streamer.service
   ```
   Update `WorkingDirectory` to your repo path. If you use a virtualenv, set `ExecStart` to that Python, e.g.:
   ```ini
   ExecStart=/home/pi/hootcam-streamer/.venv/bin/python -m hootcam_streamer
   ```

4. Optional: use a config file elsewhere (e.g. `/etc/hootcam-streamer/config.yaml`). Edit the unit and use:
   ```ini
   ExecStart=/usr/bin/python3 -m hootcam_streamer --config /etc/hootcam-streamer/config.yaml
   ```

5. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable hootcam-streamer
   sudo systemctl start hootcam-streamer
   sudo systemctl status hootcam-streamer
   ```

**Useful commands:** `sudo systemctl stop hootcam-streamer`, `sudo systemctl restart hootcam-streamer`, `sudo journalctl -u hootcam-streamer -f`
