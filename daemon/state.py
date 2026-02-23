"""Shared state store for UI and telemetry."""
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TelemetryState:
    cp_state_detected: str | None = None
    cp_voltage_pos: str | None = None
    cp_voltage_neg: str | None = None
    cp_pwm_duty: str | None = None
    cp_set_state: str | None = None
    pp_state: str | None = None
    watchdog_status: str | None = None
    last_message_ts: float | None = None
    raw_log_tail: List[str] = field(default_factory=list)
    pwm_history: List[Dict[str, float]] = field(default_factory=list)
    mains_voltage: float | None = None
    energy_kwh: float = 0.0
    _last_pwm_ts: float | None = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "cp_state_detected": self.cp_state_detected,
            "cp_voltage_pos": self.cp_voltage_pos,
            "cp_voltage_neg": self.cp_voltage_neg,
            "cp_pwm_duty": self.cp_pwm_duty,
            "cp_set_state": self.cp_set_state,
            "pp_state": self.pp_state,
            "watchdog_status": self.watchdog_status,
            "last_message_ts": self.last_message_ts,
            "raw_log_tail": list(self.raw_log_tail),
            "pwm_history": list(self.pwm_history),
            "mains_voltage": self.mains_voltage,
            "energy_kwh": self.energy_kwh,
        }


class StateStore:
    def __init__(
        self,
        log_tail_max: int = 200,
        pwm_history_max: int = 600,
        log_file: Optional[str] = None,
        log_max_bytes: int = 1_000_000,
        log_backup_count: int = 3,
    ) -> None:
        self._state = TelemetryState()
        self._lock = asyncio.Lock()
        self._updated = asyncio.Event()
        self._log_tail_max = log_tail_max
        self._pwm_history_max = pwm_history_max
        self._log_file = log_file
        self._log_logger: Optional[logging.Logger] = None
        if self._log_file:
            os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
            self._log_logger = logging.getLogger("telemetry_log")
            self._log_logger.setLevel(logging.INFO)
            handler = logging.handlers.RotatingFileHandler(
                self._log_file, maxBytes=log_max_bytes, backupCount=log_backup_count
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self._log_logger.addHandler(handler)

    async def snapshot(self) -> TelemetryState:
        async with self._lock:
            return TelemetryState(**self._state.to_dict())

    async def update(self, **kwargs: object) -> None:
        async with self._lock:
            changed = False
            for key, value in kwargs.items():
                if hasattr(self._state, key) and getattr(self._state, key) != value:
                    setattr(self._state, key, value)
                    changed = True
            if changed:
                self._state.last_message_ts = time.time()
                self._updated.set()

    async def append_log(self, line: str) -> None:
        async with self._lock:
            self._state.raw_log_tail.append(line)
            if len(self._state.raw_log_tail) > self._log_tail_max:
                self._state.raw_log_tail = self._state.raw_log_tail[-self._log_tail_max :]
            self._state.last_message_ts = time.time()
            self._updated.set()
            if self._log_logger:
                self._log_logger.info(line)

    async def add_pwm_sample(self, duty: float, amps: float, kw: float) -> None:
        async with self._lock:
            now = time.time()
            if self._state._last_pwm_ts is not None:
                dt_hours = (now - self._state._last_pwm_ts) / 3600.0
                self._state.energy_kwh += kw * dt_hours
            self._state._last_pwm_ts = now
            self._state.pwm_history.append(
                {
                    "ts": now,
                    "duty": duty,
                    "amps": amps,
                    "kw": kw,
                    "kwh": self._state.energy_kwh,
                }
            )
            if len(self._state.pwm_history) > self._pwm_history_max:
                self._state.pwm_history = self._state.pwm_history[-self._pwm_history_max :]
            self._updated.set()

    async def wait_for_update(self) -> None:
        await self._updated.wait()
        self._updated.clear()
