"""Temtop BLE integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .ble import async_has_connectable_path
from .const import CONF_ADDRESS
from .coordinator import TemtopCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Temtop from a config entry."""
    address = entry.data[CONF_ADDRESS]
    if not async_has_connectable_path(hass, address):
        raise ConfigEntryNotReady(f"No connectable Bluetooth path to {address}")

    coordinator = TemtopCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TemtopCoordinator = entry.runtime_data
        await coordinator.async_stop()
    return unload_ok
