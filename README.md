# Annex96 Car Emulator

Python daemon for Raspberry Pi that emulates an EV (car-side) against the Annex96 PLC-HAT controller, with a live web UI.

Current version: `1.0.0`

## What This Project Does

- Talks to the PLC-HAT microcontroller over UART (`/dev/serial0`, 115200).
- Controls GPIO:
  - BCM17: UART enable
  - BCM18: MCU reset pulse
- Starts a web UI (default `http://<pi-ip>:8081`) with live telemetry over WebSocket.
- Runs as a `systemd` service for auto-start and restart on failures.
- Serves chart dependencies locally from `web/vendor` (no CDN dependency at runtime).

## Installer Script

The repository includes a full Pi installer:

- Script: `scripts/install_pi.sh`
- Run as root: `sudo bash scripts/install_pi.sh`

The installer is idempotent and performs:

1. Installs required OS packages.
2. Adds app user to `gpio` and `dialout`.
3. Enables UART in boot config (`enable_uart=1`).
4. Removes Linux serial console from `cmdline.txt`.
5. Creates/updates `.venv` and installs Python requirements.
6. Writes `/etc/systemd/system/annex96-ev-emulator.service`.
7. Enables and starts the service.

If UART/boot config changed, the script prints that a reboot is required.

## Quick Install On Raspberry Pi

1. Clone/copy this repo onto the Pi.
2. Run:

```bash
cd ~/annex96-car-emulator
sudo bash scripts/install_pi.sh
```

3. If prompted, reboot:

```bash
sudo reboot
```

4. After reboot, check service:

```bash
sudo systemctl status annex96-ev-emulator.service
```

5. Open UI in browser:

```text
http://<pi-ip>:8081
```

## Service Management

- Start: `sudo systemctl start annex96-ev-emulator.service`
- Stop: `sudo systemctl stop annex96-ev-emulator.service`
- Restart: `sudo systemctl restart annex96-ev-emulator.service`
- Enable at boot: `sudo systemctl enable annex96-ev-emulator.service`
- Disable at boot: `sudo systemctl disable annex96-ev-emulator.service`
- Logs: `sudo journalctl -u annex96-ev-emulator.service -f`

## Runtime Configuration

Configured via service environment variables:

- `PLC_SERIAL_PORT` (default: `/dev/serial0`)
- `PLC_HTTP_PORT` (default: `8081`)
- `PLC_MAINS_VOLTAGE` (default: `230`)
- `PLC_LOG_FILE` (default: `logs/telemetry.log`)
- `PLC_LOG_MAX_BYTES` (default: `1000000`)
- `PLC_LOG_BACKUP_COUNT` (default: `3`)
- `PLC_REPORT_STATE_CMD` (default: `report_state_changes`)
- `PLC_ENABLE_GETSTATE_SET` (default: `1`)
- `LOG_LEVEL` (default: `INFO`)

To change these, edit:

- `/etc/systemd/system/annex96-ev-emulator.service`

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart annex96-ev-emulator.service
```

## Manual Run (Without systemd)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m daemon.main
```

## Troubleshooting

- Service fails immediately:
  - Check logs: `sudo journalctl -u annex96-ev-emulator.service -n 200 --no-pager`
- `ModuleNotFoundError: No module named 'pip._vendor.rich'` during install:
  - Re-run installer after deleting the venv: `rm -rf .venv && sudo bash scripts/install_pi.sh`
  - The installer now auto-repairs pip and recreates the venv if pip is corrupted.
- No serial data:
  - Confirm UART enabled and serial console removed.
  - Confirm service user is in `dialout`.
  - Confirm PLC-HAT wiring and `/dev/serial0` availability.
- GPIO warnings / no reset behavior:
  - Confirm running on Raspberry Pi with `RPi.GPIO` installed.
  - Confirm service user is in `gpio`.
- Web UI not reachable:
  - Confirm service is active and port `8081` is open.
  - Check with: `ss -ltnp | grep 8081`

## Repository Layout

- `daemon/`: async emulator daemon (serial, GPIO, web server, state)
- `web/`: static frontend (`index.html`, `app.js`, `styles.css`)
- `web/vendor/`: vendored browser dependencies (`Chart.js`, `Luxon`, adapter)
- `scripts/install_pi.sh`: Pi installer script
- `scripts/annex96-ev-emulator.service`: example service template
- `documentation/*.pdf.txt`: searchable extracted hardware/API references
- `requirements.txt`: Python dependencies
- `VERSION`: release version marker
- `CHANGELOG.md`: release notes
- `AGENTS.md`: maintenance guidance for coding agents
