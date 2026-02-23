# Implementation Plan: Annex96 Car Emulator

## Goals
- Run a Python daemon on the Raspberry Pi that emulates an EV (EVCC-side) using the PLC-HAT microcontroller API.
- Correctly handle GPIO pin control (UART enable and microcontroller reset) and provide reset/boot handling per docs.
- Collect CP state/voltage/PWM data in real time and present it on a lightweight web UI on port 80.
- Use a push-based transport (WebSocket) for low-latency updates and automatic refresh.

## Key Hardware/Protocol Constraints (from docs)
- Serial connection: `/dev/serial0` at `115200 8N1`, messages terminated by `;`, command/arg separated by `:`.
- GPIO:
  - BCM17 = UART enable. Must be HIGH to allow serial communication to the ATmega.
  - BCM18 = microcontroller reset. HIGH holds reset; toggle to reset MCU.
- CP/PP control and telemetry via microcontroller API:
  - Commands: `getstate:*`, `setstate:*`, `setpp:*`, `report_state_changes:*`, `report_pwm_changes:*`, `watchdog:*`, `wdt:reset`, `set_wdt_interval:*`.
  - Async messages: `statechanged=..`, `pwmchanged=..`, `wdt=timedout`, `wdt=resettriggered`, `reset=done`.
- Default watchdog interval is 5s; it must be patted (send `wdt:reset`) in response to `wdt=timedout` or via periodic keepalive.

## Architecture Overview
- **daemon/** Python service that:
  - Initializes GPIOs (BCM17/18), ensures UART enabled, resets MCU cleanly.
  - Manages serial IO to the application controller (ATmega328P) using asyncio + `pyserial-asyncio`.
  - Parses responses/events and maintains a shared in-memory state store.
  - Exposes a WebSocket server and a minimal HTTP server on port 80.
- **web/** Static UI (HTML/CSS/JS) served by the daemon, connects via WebSocket and renders live data.

## Transport Choice
- **WebSocket**: lowest latency and simplest for continuous streaming of new telemetry. Clients auto-reconnect.
- HTTP is only for serving the UI; all data updates via WebSocket.

## Data Model (in-memory)
- `cp_state_detected` (A1/B1/C1/... per API)
- `cp_voltage_pos` (V+), `cp_voltage_neg` (V-)
- `cp_pwm_duty` (0.01% resolution)
- `cp_set_state` (A/B/C)
- `pp_state` (on/off)
- `watchdog_status` (ok/timedout/resettriggered)
- `last_message_ts` (for UI freshness)
- `raw_log_tail` (bounded ring buffer for troubleshooting)

## Implementation Steps
1. **Bootstrap project structure**
   - Create `daemon/`, `web/`, `scripts/` directories.
   - Add `requirements.txt` (`pyserial`, `pyserial-asyncio`, `fastapi` or `aiohttp`, `uvicorn` if FastAPI is chosen).

2. **GPIO control layer**
   - Use `gpiozero` or `RPi.GPIO` (prefer `gpiozero` if available) to set BCM17 HIGH and control BCM18 reset.
   - Reset sequence: set BCM18 HIGH for 100–250 ms, then LOW. Ensure BCM17 HIGH before serial open.

3. **Serial protocol layer**
   - Async reader that buffers until `;`, strips whitespace, ignores CR/LF/spaces.
   - Command writer with simple request/response matching (single outstanding request) and timeout.
   - Parser for:
     - `key=value` messages (`statechanged`, `pwmchanged`, `wdt`, `reset`) and `getstate:*` responses.

4. **Watchdog handling**
   - On `wdt=timedout`, immediately send `wdt:reset`.
   - Optional periodic keepalive (every 2–3s) to avoid timeouts.
   - Expose watchdog status in UI.

5. **State polling + event streaming**
   - Enable `report_state_changes:enable` and `report_pwm_changes:enable` at boot.
   - Poll `getstate:*` at a low rate (e.g., 1 Hz) for full snapshot (voltages, duty, set state, pp).
   - On any change, update state store and broadcast to all WebSocket clients.

6. **Web server + WebSocket**
   - Run on port 80 (note: may require root or setcap for binding).
   - Serve `web/index.html`, `web/app.js`, `web/styles.css`.
   - WebSocket endpoint `/ws` streams JSON messages.
   - Include simple health endpoint `/health`.

7. **UI layout**
   - “Live Status” card with CP state, voltages, PWM duty, PP state.
   - “Controls” card for `setstate` (A/B/C) and `setpp` (on/off).
   - “Watchdog” card with status and last reset timestamp.
   - “Log tail” panel showing last N raw messages.
   - Auto-reconnect JS and visual stale-data indicator.

8. **Daemonization**
   - Provide a `systemd` service file:
     - ExecStart: `python -m daemon.main`
     - Restart: on-failure
     - User: `pi`
     - After: `network.target`
   - Document how to enable on boot (`systemctl enable` + `start`).

9. **Safety & Recovery**
   - If serial disconnects, attempt reconnect with backoff.
   - If MCU reset is detected (`reset=done`), re-apply config (report_* enable, watchdog settings).
   - Guard against invalid commands; surface errors to UI.

## Open Questions / Assumptions to Confirm
- Confirm EV emulator behavior: do we want to actively drive `setstate` (B/C) or only observe CP?
- Confirm whether PP control (setpp) is wired and desired for UI control.
- Confirm if binding to port 80 should be done via root or using `setcap cap_net_bind_service=+ep`.

## Deliverables
- `daemon/main.py` (async daemon: GPIO, serial, web server)
- `daemon/protocol.py` (serial framing + parsing)
- `daemon/state.py` (shared state store)
- `web/index.html`, `web/app.js`, `web/styles.css`
- `requirements.txt`
- `scripts/annex96.service` (systemd unit)
- `README.md` with setup/boot instructions