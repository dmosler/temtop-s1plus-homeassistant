"""Data coordinator for Temtop BLE devices."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble import async_get_connectable_device
from .const import (
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    DEFAULT_NAME,
    MODEL_AUTO,
    NOTIFICATION_IDLE_TIMEOUT,
    NOTIFY_UUID,
    RECONNECT_DELAY_SECONDS,
)
from .protocol import TemtopReading, decode_payload

_LOGGER = logging.getLogger(__name__)


class TemtopCoordinator(DataUpdateCoordinator[TemtopReading]):
    """Maintain a live BLE notification connection to a Temtop device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.address: str = entry.data[CONF_ADDRESS]
        self.name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self.model: str = entry.data.get(CONF_MODEL, MODEL_AUTO)

        self.connected = False
        self.last_error: str | None = None
        self.last_ble_name: str | None = None
        self.last_bluetooth_source: str | None = None
        self.last_address_type: int | None = None
        self.last_rssi: int | None = None
        self.last_notification: str | None = None
        self.notification_count = 0
        self.last_payload_len: int | None = None
        self._logged_unavailable = False

        self._runner_task: asyncio.Task | None = None
        self._stopped = asyncio.Event()
        self._client: BleakClientWithServiceCache | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=self.name,
            update_interval=None,
            config_entry=entry,
        )

    async def async_start(self) -> None:
        """Start the background BLE worker."""
        if self._runner_task is not None:
            return
        self._stopped.clear()
        self._runner_task = self.hass.async_create_task(self._async_run())

    async def async_stop(self) -> None:
        """Stop the background BLE worker."""
        self._stopped.set()
        if self._runner_task is not None:
            self._runner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._runner_task
            self._runner_task = None
        await self._async_disconnect()

    async def _async_update_data(self) -> TemtopReading:
        """Support manual refresh requests from Home Assistant."""
        if self.data is not None:
            return self.data
        raise UpdateFailed(self.last_error or "Temtop has not produced any readings yet")

    def _remember_ble_device(self, ble_device) -> str:
        """Store the HA Bluetooth source selected for the next connection attempt."""
        details = getattr(ble_device, "details", {}) or {}
        source = details.get("source") if isinstance(details, dict) else None
        address_type = details.get("address_type") if isinstance(details, dict) else None
        rssi = getattr(ble_device, "rssi", None)
        name = getattr(ble_device, "name", None)

        changed = (
            name != self.last_ble_name
            or source != self.last_bluetooth_source
            or address_type != self.last_address_type
            or rssi != self.last_rssi
        )

        self.last_ble_name = name
        self.last_bluetooth_source = source
        self.last_address_type = address_type
        self.last_rssi = rssi

        if changed:
            self.async_update_listeners()

        parts = []
        if source:
            parts.append(f"source={source}")
        if rssi is not None:
            parts.append(f"rssi={rssi}")
        if name:
            parts.append(f"name={name}")
        if address_type is not None:
            parts.append(f"address_type={address_type}")
        return ", ".join(parts) or "source=unknown"

    def _set_connected(self, connected: bool, error: str | None = None) -> None:
        """Update connection state and notify entities if availability changed."""
        changed = connected != self.connected
        self.connected = connected
        self.last_error = error
        if connected and self._logged_unavailable:
            _LOGGER.info("Temtop Bluetooth connection restored for %s", self.address)
            self._logged_unavailable = False
        if changed:
            self.async_update_listeners()

    def _mark_unavailable(self, message: str) -> None:
        """Mark the device unavailable and log only the first failure in a run."""
        if not self._logged_unavailable:
            _LOGGER.warning("Temtop unavailable for %s: %s", self.address, message)
            self._logged_unavailable = True
        self._set_connected(False, message)

    async def _async_disconnect(self) -> None:
        """Disconnect the current BLE client if present."""
        client = self._client
        self._client = None
        if client and client.is_connected:
            with contextlib.suppress(Exception):
                await client.disconnect()

    def _handle_payload(self, payload: bytes, seen_event: asyncio.Event) -> None:
        """Decode a payload on the HA loop and mark it as seen."""
        self.last_notification = datetime.now(UTC).isoformat(timespec="seconds")
        self.notification_count += 1
        self.last_payload_len = len(payload)
        try:
            reading = decode_payload(payload, self.model, self.name)
        except Exception as exc:
            self.last_error = f"Decode error: {type(exc).__name__}: {exc}"
            _LOGGER.error("Failed to decode Temtop payload from %s: %s", self.address, self.last_error)
            self.async_update_listeners()
        else:
            self.last_error = None
            self.async_set_updated_data(reading)
        finally:
            seen_event.set()

    async def _async_run(self) -> None:
        """Keep a BLE notify subscription alive and reconnect on failures."""
        while not self._stopped.is_set():
            ble_device = async_get_connectable_device(self.hass, self.address)
            if ble_device is None:
                message = (
                    f"No connectable Bluetooth path to {self.address}; "
                    "Home Assistant has not seen this address on an active connectable Bluetooth source"
                )
                self._mark_unavailable(message)
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                continue

            ble_context = self._remember_ble_device(ble_device)

            disconnected = asyncio.Event()
            seen_notification = asyncio.Event()

            def _ble_device_callback():
                return async_get_connectable_device(self.hass, self.address)

            def _disconnected_callback(_client) -> None:
                self.hass.loop.call_soon_threadsafe(disconnected.set)

            def _notification_handler(_sender, data: bytearray) -> None:
                self.hass.loop.call_soon_threadsafe(
                    self._handle_payload, bytes(data), seen_notification
                )

            try:
                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.name,
                    ble_device_callback=_ble_device_callback,
                )
                self._client.set_disconnected_callback(_disconnected_callback)
                await self._client.start_notify(NOTIFY_UUID, _notification_handler)
                self._set_connected(True)
                _LOGGER.debug(
                    "Temtop connected and subscribed: %s (%s)",
                    self.address,
                    ble_context,
                )

                while not self._stopped.is_set():
                    seen_notification.clear()
                    wait_tasks = [
                        asyncio.create_task(disconnected.wait()),
                        asyncio.create_task(seen_notification.wait()),
                        asyncio.create_task(self._stopped.wait()),
                    ]
                    done, pending = await asyncio.wait(
                        wait_tasks,
                        timeout=NOTIFICATION_IDLE_TIMEOUT,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        with contextlib.suppress(Exception):
                            task.result()
                    for task in pending:
                        task.cancel()
                    for task in pending:
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                    if self._stopped.is_set():
                        break
                    if disconnected.is_set():
                        raise UpdateFailed("Bluetooth connection dropped")
                    if seen_notification.is_set():
                        continue
                    raise UpdateFailed(
                        f"No Temtop notification received for {NOTIFICATION_IDLE_TIMEOUT}s"
                    )

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                _LOGGER.debug(
                    "Temtop connection cycle failed for %s (%s): %s",
                    self.address,
                    ble_context,
                    message,
                )
                self._mark_unavailable(message)
                await self._async_disconnect()
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
            else:
                self._set_connected(False, "Disconnected")
                await self._async_disconnect()
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
