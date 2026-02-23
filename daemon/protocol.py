"""Protocol framing and parsing for the PLC-HAT application controller."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedMessage:
    raw: str
    key: Optional[str] = None
    value: Optional[str] = None


def normalize_incoming(chunk: str) -> str:
    # Incoming strings may include spaces/CR/LF which should be ignored.
    return "".join(ch for ch in chunk if ch not in " \r\n\t")


def parse_message(raw: str) -> ParsedMessage:
    if "=" in raw:
        key, value = raw.split("=", 1)
        return ParsedMessage(raw=raw, key=key, value=value)
    return ParsedMessage(raw=raw)


def build_command(command: str, arg: Optional[str] = None) -> str:
    if arg is None:
        return f"{command};"
    return f"{command}:{arg};"