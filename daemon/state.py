"""Shared state store for UI and telemetry."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List


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
        }


class StateStore:
    def __init__(self, log_tail_max: int = 200) -> None:
        self._state = TelemetryState()
        self._lock = asyncio.Lock()
        self._updated = asyncio.Event()
        self._log_tail_max = log_tail_max

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

    async def wait_for_update(self) -> None:
        await self._updated.wait()
        self._updated.clear()