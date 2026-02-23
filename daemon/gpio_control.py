"""GPIO control for BCM17 (UART enable) and BCM18 (MCU reset).

Uses RPi.GPIO when available, otherwise falls back to a no-op stub.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


class _StubGPIO:
    BCM = "BCM"
    OUT = "OUT"
    HIGH = 1
    LOW = 0

    def setmode(self, *_args, **_kwargs):
        pass

    def setup(self, *_args, **_kwargs):
        pass

    def output(self, *_args, **_kwargs):
        pass

    def cleanup(self, *_args, **_kwargs):
        pass


try:
    import RPi.GPIO as _GPIO  # type: ignore
except Exception:  # pragma: no cover - non-Pi environments
    _GPIO = _StubGPIO()


@dataclass(frozen=True)
class GpioPins:
    uart_enable_bcm: int = 17
    reset_bcm: int = 18


class GpioController:
    def __init__(self, pins: GpioPins = GpioPins()) -> None:
        self._gpio = _GPIO
        self._pins = pins
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setup(self._pins.uart_enable_bcm, self._gpio.OUT)
        self._gpio.setup(self._pins.reset_bcm, self._gpio.OUT)
        self._initialized = True

    def set_uart_enabled(self, enabled: bool) -> None:
        self.initialize()
        self._gpio.output(self._pins.uart_enable_bcm, self._gpio.HIGH if enabled else self._gpio.LOW)

    def reset_mcu(self, hold_ms: int = 150) -> None:
        self.initialize()
        # HIGH holds reset, then release LOW
        self._gpio.output(self._pins.reset_bcm, self._gpio.HIGH)
        time.sleep(hold_ms / 1000.0)
        self._gpio.output(self._pins.reset_bcm, self._gpio.LOW)

    def cleanup(self) -> None:
        if not self._initialized:
            return
        self._gpio.cleanup()
        self._initialized = False