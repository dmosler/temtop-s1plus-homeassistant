"""Sensor platform for Temtop BLE devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN, MODEL_AUTO, MODEL_C1PLUS, MODEL_NAMES, MODEL_S1PLUS
from .coordinator import TemtopCoordinator
from .protocol import TemtopReading

PARALLEL_UPDATES = 0
_NO_PATH_PREFIX = "No connectable Bluetooth path"
_DISCONNECTED_PREFIX = "UpdateFailed: Bluetooth connection dropped"


@dataclass(frozen=True, kw_only=True)
class TemtopSensorEntityDescription(SensorEntityDescription):
    """Entity description for a Temtop sensor."""

    models: set[str]
    value_fn: Callable[[TemtopReading], int | float | None]


SENSOR_DESCRIPTIONS: tuple[TemtopSensorEntityDescription, ...] = (
    TemtopSensorEntityDescription(
        key="co2",
        translation_key="co2",
        models={MODEL_C1PLUS},
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.co2_ppm,
    ),
    TemtopSensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        models={MODEL_S1PLUS},
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.pm25_ug_m3,
    ),
    TemtopSensorEntityDescription(
        key="aqi",
        translation_key="aqi",
        models={MODEL_S1PLUS},
        native_unit_of_measurement="AQI",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.aqi,
    ),
    TemtopSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        models={MODEL_C1PLUS, MODEL_S1PLUS},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.temperature_c,
    ),
    TemtopSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        models={MODEL_C1PLUS, MODEL_S1PLUS},
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.humidity_pct,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Temtop sensors."""
    coordinator: TemtopCoordinator = entry.runtime_data
    model = coordinator.data.model if coordinator.data else coordinator.model
    entities: list[SensorEntity] = [
        TemtopSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
        if model == MODEL_AUTO or model in description.models
    ]
    entities.append(TemtopConnectionStatusSensor(coordinator, entry))
    async_add_entities(entities)


def _device_info(coordinator: TemtopCoordinator, entry: ConfigEntry) -> DeviceInfo:
    """Build shared device info."""
    model = coordinator.data.model if coordinator.data else coordinator.model
    return DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Temtop",
        model=MODEL_NAMES.get(model, model),
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        connections={("bluetooth", coordinator.address)},
    )


def _has_real_bluetooth_problem(coordinator: TemtopCoordinator) -> bool:
    """Return whether Home Assistant has evidence that BLE is actually down."""
    if coordinator.connected:
        return False
    last_error = coordinator.last_error or ""
    return last_error.startswith(_NO_PATH_PREFIX) or last_error.startswith(_DISCONNECTED_PREFIX)


def _connection_attributes(coordinator: TemtopCoordinator) -> dict[str, Any]:
    """Return diagnostic attributes that are useful even before data arrives."""
    attributes: dict[str, Any] = {
        "address": coordinator.address,
        "configured_model": MODEL_NAMES.get(coordinator.model, coordinator.model),
        "connected": not _has_real_bluetooth_problem(coordinator),
    }
    if coordinator.last_error:
        attributes["last_error"] = coordinator.last_error
    if coordinator.last_bluetooth_source:
        attributes["bluetooth_source"] = coordinator.last_bluetooth_source
    if coordinator.last_rssi is not None:
        attributes["rssi"] = coordinator.last_rssi
    if coordinator.last_ble_name:
        attributes["ble_name"] = coordinator.last_ble_name
    if coordinator.last_address_type is not None:
        attributes["address_type"] = coordinator.last_address_type
    if coordinator.last_notification:
        attributes["last_notification"] = coordinator.last_notification
    attributes["notification_count"] = coordinator.notification_count
    if coordinator.last_payload_len is not None:
        attributes["last_payload_len"] = coordinator.last_payload_len
    return attributes


class TemtopSensor(CoordinatorEntity[TemtopCoordinator], SensorEntity):
    """Temtop sensor entity."""

    entity_description: TemtopSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TemtopCoordinator,
        entry: ConfigEntry,
        description: TemtopSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = _device_info(coordinator, entry)

    @property
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Values remain available until a real Bluetooth failure happens."""
        return self.coordinator.data is not None and not _has_real_bluetooth_problem(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attributes = _connection_attributes(self.coordinator)
        if self.coordinator.data is None:
            return attributes
        attributes["model"] = MODEL_NAMES.get(self.coordinator.data.model, self.coordinator.data.model)
        if self.coordinator.data.device_timestamp:
            attributes["device_timestamp"] = self.coordinator.data.device_timestamp
        return attributes


class TemtopConnectionStatusSensor(CoordinatorEntity[TemtopCoordinator], SensorEntity):
    """Diagnostic sensor that exposes the BLE connection state."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bluetooth"

    def __init__(self, coordinator: TemtopCoordinator, entry: ConfigEntry) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_connection_status"
        self._attr_device_info = _device_info(coordinator, entry)

    @property
    def native_value(self) -> str:
        """Return the current BLE connection state."""
        if self.coordinator.connected and self.coordinator.data is not None:
            return "connected"
        if self.coordinator.connected:
            return "connected_waiting_for_data"
        if self.coordinator.last_error:
            if self.coordinator.last_error.startswith(_NO_PATH_PREFIX):
                return "no_connectable_path"
            if not _has_real_bluetooth_problem(self.coordinator):
                return "connected"
            return "error"
        return "initializing"

    @property
    def available(self) -> bool:
        """Keep the diagnostic state visible while measurement sensors are unavailable."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return _connection_attributes(self.coordinator)
