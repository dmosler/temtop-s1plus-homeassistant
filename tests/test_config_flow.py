"""Tests for the Temtop config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.temtop.const import CONF_MODEL, DOMAIN, MODEL_C1PLUS, MODEL_S1PLUS

ADDRESS = "A4:C1:38:BE:1F:4A"


async def test_user_flow_success(hass, enable_custom_integrations) -> None:
    """Test a successful manual config flow."""
    with patch(
        "custom_components.temtop.config_flow.async_has_connectable_path",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_ADDRESS: ADDRESS.lower(),
                CONF_NAME: "Bedroom Temtop",
                CONF_MODEL: MODEL_C1PLUS,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom Temtop"
    assert result["data"] == {
        CONF_ADDRESS: ADDRESS,
        CONF_NAME: "Bedroom Temtop",
        CONF_MODEL: MODEL_C1PLUS,
    }


async def test_user_flow_requires_connectable_path(hass, enable_custom_integrations) -> None:
    """Test manual setup fails when no connectable Bluetooth path exists."""
    with patch(
        "custom_components.temtop.config_flow.async_has_connectable_path",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_ADDRESS: ADDRESS,
                CONF_NAME: "Bedroom Temtop",
                CONF_MODEL: MODEL_C1PLUS,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_flow_success(hass, enable_custom_integrations) -> None:
    """Test a successful Bluetooth discovery flow."""
    discovery = SimpleNamespace(address=ADDRESS, name="S1+_1234")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=discovery,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "S1+_1234"
    assert result["data"][CONF_MODEL] == MODEL_S1PLUS


async def test_bluetooth_duplicate_is_aborted(hass, enable_custom_integrations) -> None:
    """Test duplicate Bluetooth discovery is aborted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        data={
            CONF_ADDRESS: ADDRESS,
            CONF_NAME: "Temtop",
            CONF_MODEL: MODEL_C1PLUS,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=SimpleNamespace(address=ADDRESS, name="C1+_1234"),
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
