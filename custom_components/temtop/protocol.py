"""Protocol helpers for Temtop BLE notifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .const import MODEL_AUTO, MODEL_C1PLUS, MODEL_S1PLUS

C1PLUS_PACKET_LENGTH = 47
C1PLUS_PACKET_HEADER = b"\xd5\xc8"
S1PLUS_MIN_PACKET_LENGTH = 30


@dataclass(frozen=True)
class TemtopReading:
    """Decoded Temtop sensor reading."""

    model: str
    temperature_c: float
    humidity_pct: float
    raw_hex: str
    co2_ppm: int | None = None
    pm25_ug_m3: float | None = None
    aqi: int | None = None
    device_timestamp: str | None = None


def _u16be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def decode_c1plus_payload(data: bytes) -> TemtopReading:
    """Decode a C1+ 47-byte notification payload."""
    if len(data) != C1PLUS_PACKET_LENGTH:
        raise ValueError(f"expected {C1PLUS_PACKET_LENGTH} bytes, got {len(data)}")
    if data[:2] != C1PLUS_PACKET_HEADER:
        raise ValueError(f"unexpected C1+ header {data[:2].hex()}")

    device_timestamp = datetime(
        _u16be(data, 15),
        data[17],
        data[18],
        data[19],
        data[20],
    ).isoformat(timespec="minutes")

    return TemtopReading(
        model=MODEL_C1PLUS,
        temperature_c=_u16be(data, 24) / 10,
        humidity_pct=_u16be(data, 26) / 10,
        co2_ppm=_u16be(data, 30),
        device_timestamp=device_timestamp,
        raw_hex=data.hex(),
    )


def decode_s1plus_payload(data: bytes) -> TemtopReading:
    """Decode an S1+ notification payload using the reference integration offsets."""
    if len(data) < S1PLUS_MIN_PACKET_LENGTH:
        raise ValueError(f"expected at least {S1PLUS_MIN_PACKET_LENGTH} bytes, got {len(data)}")

    return TemtopReading(
        model=MODEL_S1PLUS,
        pm25_ug_m3=_u16be(data, 22) / 10,
        temperature_c=data[25] / 10,
        humidity_pct=_u16be(data, 26) / 10,
        aqi=data[29],
        raw_hex=data.hex(),
    )


def detect_model(name: str | None, payload: bytes | None = None) -> str:
    """Detect a Temtop model from BLE name and, if available, payload shape."""
    normalized = (name or "").upper()
    if normalized.startswith("C1+"):
        return MODEL_C1PLUS
    if normalized.startswith("S1+"):
        return MODEL_S1PLUS
    if payload and len(payload) == C1PLUS_PACKET_LENGTH and payload[:2] == C1PLUS_PACKET_HEADER:
        return MODEL_C1PLUS
    return MODEL_AUTO


def decode_payload(data: bytes, model: str = MODEL_AUTO, name: str | None = None) -> TemtopReading:
    """Decode a Temtop notification payload."""
    selected_model = model if model != MODEL_AUTO else detect_model(name, data)
    if selected_model == MODEL_C1PLUS:
        return decode_c1plus_payload(data)
    if selected_model == MODEL_S1PLUS:
        return decode_s1plus_payload(data)

    if len(data) == C1PLUS_PACKET_LENGTH and data[:2] == C1PLUS_PACKET_HEADER:
        return decode_c1plus_payload(data)
    return decode_s1plus_payload(data)
