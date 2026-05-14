"""Config flow for Temtop BLE devices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .ble import async_has_connectable_path
from .const import CONF_MODEL, DEFAULT_NAME, DOMAIN, MODEL_AUTO, MODEL_NAMES, MODELS
from .exceptions import CannotConnect
from .protocol import detect_model


def _normalize_address(address: str) -> str:
    return address.strip().upper()


async def _async_validate_connectable_path(hass, address: str) -> None:
    """Validate that Home Assistant can currently connect to the BLE address."""
    if not async_has_connectable_path(hass, address):
        raise CannotConnect


class TemtopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Temtop BLE devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovery_model = MODEL_AUTO

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle Bluetooth discovery."""
        self._discovery_info = discovery_info
        self._discovery_model = detect_model(discovery_info.name)
        await self.async_set_unique_id(_normalize_address(discovery_info.address))
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Bluetooth discovery."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_discovery_info")

        if user_input is not None:
            name = self._discovery_info.name or DEFAULT_NAME
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: _normalize_address(self._discovery_info.address),
                    CONF_NAME: name,
                    CONF_MODEL: self._discovery_model,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or DEFAULT_NAME,
                "address": self._discovery_info.address,
                "model": MODEL_NAMES.get(self._discovery_model, MODEL_NAMES[MODEL_AUTO]),
            },
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = _normalize_address(user_input[CONF_ADDRESS])
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            try:
                await _async_validate_connectable_path(self.hass, address)
            except CannotConnect:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors=errors,
                )

            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                    CONF_MODEL: user_input[CONF_MODEL],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
        )

    def _user_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        """Return the manual setup schema."""
        user_input = user_input or {}
        address = user_input.get(CONF_ADDRESS)
        address_key = (
            vol.Required(CONF_ADDRESS, default=address)
            if address
            else vol.Required(CONF_ADDRESS)
        )
        return vol.Schema(
            {
                address_key: str,
                vol.Optional(
                    CONF_NAME,
                    default=user_input.get(CONF_NAME, DEFAULT_NAME),
                ): str,
                vol.Required(
                    CONF_MODEL,
                    default=user_input.get(CONF_MODEL, MODEL_AUTO),
                ): vol.In(MODELS),
            }
        )
