# Temtop S1+ Home Assistant Integration

Read Temtop S1+ air quality data via BLE and send it to Home Assistant — **no app required**.

This is believed to be the **first open-source integration** for the Temtop S1+ without the official app.

## What it does

Connects to the Temtop S1+ air quality monitor via Bluetooth Low Energy (BLE), reads the sensor data every 2 minutes, and sends it directly to Home Assistant via the REST API.

Between midnight and 6 a.m. the script switches to night mode and only checks once per hour, which saves the S1+ battery. The intervals and the night window are constants at the top of `temtop.py`.

**Sensors available:**
- PM2.5 (µg/m³)
- AQI
- Temperature (°C)
- Humidity (%)

## Hardware Requirements

- Temtop S1+ air quality monitor
- Raspberry Pi (any model with Bluetooth, or Pi 1/2 with a USB Bluetooth dongle)
- USB Bluetooth 4.0+ dongle (if your Pi doesn't have built-in Bluetooth)
  - Tested with: TP-Link UB500

## Software Requirements

- Raspberry Pi OS (Bullseye or newer)
- Python 3
- [bleak](https://github.com/hbldh/bleak) library
- [requests](https://requests.readthedocs.io/) library
- Home Assistant with a Long-Lived Access Token

## Installation

### 1. Install dependencies

```bash
sudo apt update
sudo apt install -y bluetooth bluez python3-pip
pip3 install bleak --break-system-packages
```

### 2. Find your S1+ MAC address

Make sure the Temtop app is **closed** on your phone, then run:

```bash
sudo hcitool lescan
```

Look for a device named `S1+_...` and note the MAC address (e.g. `A4:C1:38:56:89:85`).

### 3. Clone this repository

```bash
cd /home/pi
git clone https://github.com/dmosler/temtop-s1plus-homeassistant.git
cd temtop-s1plus-homeassistant
```

### 4. Configure

```bash
cp temtop.conf.example temtop.conf
nano temtop.conf
```

Fill in your values:

```
HA_TOKEN=your_long_lived_access_token_here
HA_URL=http://your_home_assistant_ip:8123
```

**How to get a Long-Lived Access Token in Home Assistant:**
Go to your profile → Security → Long-Lived Access Tokens → Create Token

⚠️ Never share your token publicly!

### 5. Update the MAC address

Edit `temtop.py` and replace the MAC address with yours:

```python
MAC = "A4:C1:38:56:89:85"  # Replace with your S1+ MAC address
```

### 6. Test it

```bash
python3 /home/pi/temtop-s1plus-homeassistant/temtop.py
```

You should see output like:
```
PM2.5: 1.4 µg/m³ | AQI: 8 | Temp: 20.1°C | Humidity: 50.8%
```

### 7. Run as a service (autostart on boot)

```bash
sudo cp temtop.service /etc/systemd/system/
sudo systemctl enable temtop
sudo systemctl start temtop
sudo systemctl status temtop
```

## Home Assistant Dashboard

Add this YAML as a new card in your Lovelace dashboard:

```yaml
type: entities
title: Temtop S1+ Air Quality
entities:
  - entity: sensor.temtop_pm25
    name: PM2.5
    icon: mdi:air-filter
  - entity: sensor.temtop_aqi
    name: AQI
    icon: mdi:leaf
  - entity: sensor.temtop_temperature
    name: Temperature
    icon: mdi:thermometer
  - entity: sensor.temtop_humidity
    name: Humidity
    icon: mdi:water-percent
```

## How it works

The Temtop S1+ broadcasts data via BLE GATT notifications on characteristic `00010203-0405-0607-0809-0a0b0c0d2b10`.

The data packet is 46 bytes. The relevant byte positions (reverse-engineered):

| Sensor | Bytes | Calculation |
|--------|-------|-------------|
| PM2.5 | 22-23 | `int(bytes) / 10` |
| Temperature | 24-25 | `int(bytes) / 10` |
| Humidity | 26-27 | `int(bytes) / 10` |
| AQI | 29 | direct value |

Temperature must be read as **two** bytes. Earlier versions read only byte 25, which silently wraps above 25.5 °C (e.g. 30.3 °C was reported as 4.7 °C).

## Important Notes

- **Close the Temtop app** on your phone before running the script — the app holds the BLE connection and blocks other clients.
- The script connects every 2 minutes, reads data, then disconnects. This is battery-friendly for the S1+.
- First reading may take up to 20 seconds after the script starts.
- Repeated `BleakDeviceNotFoundError` usually means the S1+ battery is low — it stops advertising before it stops showing a reading on its display. Verify with `sudo timeout 15 hcitool lescan | grep A4:C1:38` and charge it via USB.

## Tested with

- Temtop S1+ firmware as of February 2026
- Raspberry Pi 1 Model B (2011) with TP-Link UB500 Bluetooth dongle
- Raspberry Pi OS Bullseye
- Home Assistant

## Contributing

Found a bug or improvement? Pull requests welcome!

## License

MIT
