"""Async daemon for PLC-HAT EV emulator with Web UI."""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Optional, Set

import aiohttp
from aiohttp import web
import serial_asyncio

from .gpio_control import GpioController
from .protocol import build_command, normalize_incoming, parse_message
from .state import StateStore


@dataclass
class SerialConfig:
    port: str = "/dev/serial0"
    baudrate: int = 115200


class SerialManager:
    def __init__(self, state: StateStore, config: SerialConfig) -> None:
        self._state = state
        self._config = config
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._write_lock = asyncio.Lock()
        self._connected = asyncio.Event()
        self._stop = asyncio.Event()

    async def connect_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._reader, self._writer = await serial_asyncio.open_serial_connection(
                    url=self._config.port, baudrate=self._config.baudrate
                )
                self._connected.set()
                await self._state.append_log("serial connected")
                await self._read_loop()
            except Exception as exc:
                await self._state.append_log(f"serial error: {exc}")
                self._connected.clear()
                await asyncio.sleep(2.0)
            finally:
                if self._writer is not None:
                    try:
                        self._writer.close()
                        await self._writer.wait_closed()
                    except Exception:
                        pass
                self._reader = None
                self._writer = None

    async def _read_loop(self) -> None:
        assert self._reader is not None
        buffer = ""
        while not self._stop.is_set():
            data = await self._reader.read(128)
            if not data:
                raise ConnectionError("serial disconnected")
            text = normalize_incoming(data.decode(errors="ignore"))
            buffer += text
            while ";" in buffer:
                raw, buffer = buffer.split(";", 1)
                if not raw:
                    continue
                await self._handle_message(raw)

    async def wait_connected(self) -> None:
        await self._connected.wait()

    async def _handle_message(self, raw: str) -> None:
        parsed = parse_message(raw)
        await self._state.append_log(raw)
        if parsed.key is None:
            return

        key = parsed.key
        value = parsed.value or ""

        if key == "statechanged":
            await self._state.update(cp_state_detected=value)
        elif key == "pwmchanged":
            # pwmchanged=XXXX-XXXX
            await self._state.update(cp_pwm_duty=value)
        elif key == "wdt":
            await self._state.update(watchdog_status=value)
            if value == "timedout":
                await self.send_command("wdt", "reset")
        elif key == "reset":
            await self._state.update(watchdog_status="reset")
        elif key == "cp_detected":
            await self._state.update(cp_state_detected=value)
        elif key == "cp_v-":
            await self._state.update(cp_voltage_neg=value)
        elif key == "cp_v+":
            await self._state.update(cp_voltage_pos=value)
        elif key == "cp_duty":
            await self._state.update(cp_pwm_duty=value)
        elif key == "cp_set":
            await self._state.update(cp_set_state=value)
        elif key == "pp":
            await self._state.update(pp_state=value)

    async def send_command(self, command: str, arg: Optional[str] = None) -> None:
        await self._connected.wait()
        if self._writer is None:
            return
        payload = build_command(command, arg)
        async with self._write_lock:
            self._writer.write(payload.encode())
            await self._writer.drain()

    async def stop(self) -> None:
        self._stop.set()


class WebServer:
    def __init__(self, state: StateStore, serial: SerialManager) -> None:
        self._state = state
        self._serial = serial
        self._app = web.Application()
        self._app.add_routes([
            web.get("/", self._handle_index),
            web.get("/ws", self._handle_ws),
            web.get("/health", self._handle_health),
            web.get("/app.js", self._handle_app_js),
            web.get("/styles.css", self._handle_styles_css),
        ])
        self._websockets: Set[web.WebSocketResponse] = set()

    async def _handle_index(self, _request: web.Request) -> web.Response:
        with open(os.path.join("web", "index.html"), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")

    async def _handle_app_js(self, _request: web.Request) -> web.Response:
        with open(os.path.join("web", "app.js"), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="application/javascript")

    async def _handle_styles_css(self, _request: web.Request) -> web.Response:
        with open(os.path.join("web", "styles.css"), "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/css")

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "ts": time.time()})

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.add(ws)

        # send initial snapshot
        snapshot = await self._state.snapshot()
        await ws.send_str(json.dumps({"type": "snapshot", "data": snapshot.to_dict()}))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_ws_message(ws, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self._websockets.discard(ws)
        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: str) -> None:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return

        msg_type = payload.get("type")
        if msg_type == "setstate":
            value = str(payload.get("value", "")).upper()
            if value in {"A", "B", "C"}:
                await self._serial.send_command("setstate", value)
        elif msg_type == "control":
            action = str(payload.get("value", "")).lower()
            if action == "pause":
                await self._serial.send_command("setstate", "B")
            elif action == "resume":
                await self._serial.send_command("setstate", "C")
            elif action == "full":
                # Full charge: keep requesting energy (state C) by default.
                await self._serial.send_command("setstate", "C")
            elif action == "stop":
                await self._serial.send_command("setstate", "A")
        elif msg_type == "setpp":
            value = str(payload.get("value", "")).lower()
            if value in {"on", "off"}:
                await self._serial.send_command("setpp", value)
        elif msg_type == "getstate":
            await self._serial.send_command("getstate", "cp")
            await self._serial.send_command("getstate", "v-")
            await self._serial.send_command("getstate", "v+")
            await self._serial.send_command("getstate", "pwm")
            await self._serial.send_command("getstate", "set")
            await self._serial.send_command("getstate", "pp")
        await ws.send_str(json.dumps({"type": "ack", "data": msg_type}))

    async def broadcast_updates(self) -> None:
        while True:
            await self._state.wait_for_update()
            snapshot = await self._state.snapshot()
            message = json.dumps({"type": "update", "data": snapshot.to_dict()})
            dead = []
            for ws in self._websockets:
                try:
                    await ws.send_str(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._websockets.discard(ws)

    def app(self) -> web.Application:
        return self._app


async def poll_task(serial: SerialManager) -> None:
    # Periodic full snapshot polling (1 Hz)
    while True:
        await serial.send_command("getstate", "cp")
        await serial.send_command("getstate", "v-")
        await serial.send_command("getstate", "v+")
        await serial.send_command("getstate", "pwm")
        await serial.send_command("getstate", "set")
        await serial.send_command("getstate", "pp")
        await asyncio.sleep(1.0)


async def watchdog_keepalive(serial: SerialManager, interval: float = 2.5) -> None:
    while True:
        await serial.send_command("wdt", "reset")
        await asyncio.sleep(interval)


async def configure_controller(serial: SerialManager) -> None:
    await serial.send_command("report_state_changes", "enable")
    await serial.send_command("report_pwm_changes", "enable")
    await serial.send_command("watchdog", "enable")
    await serial.send_command("set_wdt_interval", "5")


async def auto_charge_session(serial: SerialManager, initial_delay: float = 1.0, to_request_delay: float = 2.0) -> None:
    # EV behavior: connect (state B) then request energy (state C)
    await asyncio.sleep(initial_delay)
    await serial.send_command("setstate", "B")
    await asyncio.sleep(to_request_delay)
    await serial.send_command("setstate", "C")


async def main() -> None:
    serial_port = os.environ.get("PLC_SERIAL_PORT", "/dev/serial0")
    http_port = int(os.environ.get("PLC_HTTP_PORT", "8081"))

    state = StateStore()
    gpio = GpioController()
    gpio.set_uart_enabled(True)
    gpio.reset_mcu()

    serial = SerialManager(state, SerialConfig(port=serial_port))

    web_server = WebServer(state, serial)

    runner = web.AppRunner(web_server.app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", http_port)
    await site.start()

    tasks = [
        asyncio.create_task(serial.connect_loop()),
        asyncio.create_task(web_server.broadcast_updates()),
        asyncio.create_task(poll_task(serial)),
        asyncio.create_task(watchdog_keepalive(serial)),
    ]

    # Configure after serial is connected
    await serial.wait_connected()
    await configure_controller(serial)
    asyncio.create_task(auto_charge_session(serial))

    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        gpio.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
