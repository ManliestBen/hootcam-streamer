# Hootcam Streamer – systemd service

## Run on boot (Pi)

1. Complete the main [README](../README.md) setup (system Picamera2, venv + `pip install -r requirements.txt` and Spyglass, optional config.yaml).

2. Copy the unit file:
   ```bash
   sudo cp contrib/hootcam-streamer.service /etc/systemd/system/
   ```

3. If your install path is not `/home/pi/hootcam-streamer`, edit the unit:
   ```bash
   sudo nano /etc/systemd/system/hootcam-streamer.service
   ```
   Update `WorkingDirectory` and the path in `ExecStart` (the default uses `.venv/bin/python`). If you did not create a venv, use system Python instead:
   ```ini
   ExecStart=/usr/bin/python3 -m hootcam_streamer
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
