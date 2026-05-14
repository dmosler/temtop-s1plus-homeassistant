"""Bluetooth helpers for the Temtop integration."""

from __future__ import annotations

from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant


def async_get_connectable_device(
    hass: HomeAssistant,
    address: str,
) -> BLEDevice | None:
    """Return the current connectable Bluetooth device for an address."""
    return bluetooth.async_ble_device_from_address(hass, address, connectable=True)


def async_has_connectable_path(hass: HomeAssistant, address: str) -> bool:
    """Return whether Home Assistant currently has a connectable BLE path."""
    return async_get_connectable_device(hass, address) is not None
