"""Diagnostics support for the Temtop integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS
from .coordinator import TemtopCoordinator

TO_REDACT = {CONF_ADDRESS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TemtopCoordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "runtime": {
            "connected": coordinator.connected,
            "last_error": coordinator.last_error,
            "last_ble_name": coordinator.last_ble_name,
            "last_bluetooth_source": coordinator.last_bluetooth_source,
            "last_address_type": coordinator.last_address_type,
            "last_rssi": coordinator.last_rssi,
            "last_notification": coordinator.last_notification,
            "notification_count": coordinator.notification_count,
            "last_payload_len": coordinator.last_payload_len,
            "model": data.model if data else coordinator.model,
            "has_data": data is not None,
        },
    }
