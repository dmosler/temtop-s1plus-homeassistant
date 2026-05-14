# Temtop Home Assistant Integration

Temtop is a custom Home Assistant integration for selected Temtop BLE air quality
monitors. It connects through Home Assistant's Bluetooth stack, including local
Bluetooth adapters and connectable ESPHome Bluetooth proxies, subscribes to the
device notification characteristic, and exposes the decoded measurements as
native Home Assistant sensors.

This implementation builds on the original S1+ script and extends it with the
C1+ protocol mapping derived from local BLE captures.

## Development note

This project was developed end-to-end in a vibe-coded, AI-assisted workflow.
That includes the BLE reverse engineering, payload validation against the
physical display, protocol documentation, Home Assistant integration code,
HACS packaging, and the Bronze-oriented cleanup.

The reverse engineering was performed from local captures of a Temtop C1+
device and comparison with the physical device display. The S1+ support is
derived from the reference repository linked above.

## Supported devices

Known supported devices:

- Temtop C1+: CO2, temperature, humidity
- Temtop S1+: PM2.5, AQI, temperature, humidity

Unsupported or unverified devices:

- Other Temtop models are not supported unless they use the same notification
  protocol.
- Cloud/app-only features are not implemented.

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories**.
2. Add this repository URL as type **Integration**:

   ```text
   https://github.com/dmosler/temtop-s1plus-homeassistant
   ```

3. Install **Temtop** from HACS.
4. Restart Home Assistant.

### Manual installation

1. Copy `custom_components/temtop` into your Home Assistant config directory:

   ```text
   config/custom_components/temtop
   ```

2. Restart Home Assistant.

## Setup

1. Make sure Bluetooth is enabled in Home Assistant.
2. If the Temtop is not near the Home Assistant host, use a connectable ESPHome
   Bluetooth proxy close to the device.
3. Open **Settings > Devices & services > Add integration**.
4. Search for **Temtop**.
5. If Bluetooth discovery finds the device, confirm the discovered device.
6. If it is not discovered automatically, enter the BLE address manually and
   select the device model.

Setup parameters:

- **Bluetooth address**: BLE MAC address of the Temtop device, for example
  `A4:C1:38:BE:1F:4A`.
- **Name**: Device name shown in Home Assistant.
- **Model**: `C1+`, `S1+`, or `Auto` when the model can be detected from the
  BLE name or payload.

The config flow checks that Home Assistant currently has a connectable
Bluetooth path before accepting manual setup.

## Entities

The integration creates one Home Assistant device per Temtop monitor.

C1+ entities:

- **CO2**: Carbon dioxide in ppm
- **Temperature**: Temperature in Celsius
- **Humidity**: Relative humidity in percent
- **Connection status**: Diagnostic BLE connection state

S1+ entities:

- **PM2.5**: Fine particulate matter in ug/m3
- **AQI**: Air quality index
- **Temperature**: Temperature in Celsius
- **Humidity**: Relative humidity in percent
- **Connection status**: Diagnostic BLE connection state

## Data updates

The integration is `local_push`. It keeps a BLE notification subscription open
and updates entities when the device sends a notification. If the Bluetooth path
is lost, measurement entities become unavailable and the coordinator retries the
connection.

## Service actions

This integration does not provide Home Assistant service actions. It only
creates sensor entities.

## Removal

1. Open **Settings > Devices & services**.
2. Select **Temtop**.
3. Remove the config entry for the device.
4. If installed manually, delete `custom_components/temtop`.
5. Restart Home Assistant.

## Development

Install test dependencies:

```powershell
python -m pip install -e ".[test]"
```

Run tests:

```powershell
python -m pytest
```

The integration includes a `quality_scale.yaml` checklist for the Home Assistant
Bronze rules. For a Home Assistant Core contribution, branding assets still need
to be submitted to the upstream
[home-assistant/brands](https://github.com/home-assistant/brands) repository.
