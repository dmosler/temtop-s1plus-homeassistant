import asyncio
import requests
from bleak import BleakClient
from datetime import datetime

MAC = "A4:C1:38:56:89:85"  # Replace with your S1+ MAC address
CHAR_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"

READ_INTERVAL = 120    # seconds between successful readings
RETRY_INTERVAL = 30    # seconds before the first retry after a failed reading
MAX_RETRY_INTERVAL = 300  # retries back off up to this
NIGHT_INTERVAL = 3600  # seconds between checks during night mode
ACTIVE_FROM = 6        # night mode ends at this hour
ACTIVE_UNTIL = 24      # night mode starts at this hour

# Consecutive failed readings before the HA entities are marked unavailable.
# Without this they would keep showing the last value indefinitely.
FAILURES_UNTIL_UNAVAILABLE = 3

# Order matches the tuple returned by parse_data()
SENSORS = [
    ("pm25", "µg/m³"),
    ("aqi", "AQI"),
    ("temperature", "°C"),
    ("humidity", "%"),
]

# Load config
config = {}
with open('/home/pi/temtop.conf') as f:
    for line in f:
        key, val = line.strip().split('=', 1)
        config[key] = val

HA_URL = config['HA_URL']
HA_TOKEN = config['HA_TOKEN']


def is_active_time():
    return ACTIVE_FROM <= datetime.now().hour < ACTIVE_UNTIL


def send_to_ha(sensor, value, unit):
    url = f"{HA_URL}/api/states/sensor.temtop_{sensor}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "state": value,
        "attributes": {"unit_of_measurement": unit}
    }
    try:
        requests.post(url, json=data, headers=headers)
    except Exception as e:
        print(f"HA error: {e}")


def parse_data(data):
    pm25 = int.from_bytes(data[22:24], 'big') / 10
    aqi = data[29]
    # Two bytes: a single byte wraps above 25.5 °C
    temp = int.from_bytes(data[24:26], 'big') / 10
    humidity = int.from_bytes(data[26:28], 'big') / 10
    return pm25, aqi, temp, humidity


async def read_once():
    result = {}

    def handler(sender, data):
        pm25, aqi, temp, humidity = parse_data(data)
        result['values'] = (pm25, aqi, temp, humidity)

    try:
        async with BleakClient(MAC) as client:
            await client.start_notify(CHAR_UUID, handler)
            await asyncio.sleep(15)
            await client.stop_notify(CHAR_UUID)
    except Exception as e:
        if not isinstance(e, EOFError):
            print(f"Connection error: {type(e).__name__}: {e}")

    return result.get('values')


async def main():
    print("Temtop S1+ monitor started")
    failures = 0
    marked_unavailable = False

    while True:
        if not is_active_time():
            print("Night mode - next reading in 1 hour")
            await asyncio.sleep(NIGHT_INTERVAL)
            continue

        values = None
        try:
            values = await read_once()
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

        if values:
            pm25, aqi, temp, humidity = values
            print(f"PM2.5: {pm25} µg/m³ | AQI: {aqi} | Temp: {temp}°C | Humidity: {humidity}%")
            for (sensor, unit), value in zip(SENSORS, values):
                send_to_ha(sensor, value, unit)
            failures = 0
            marked_unavailable = False
            await asyncio.sleep(READ_INTERVAL)
            continue

        failures += 1

        # The S1+ stops advertising before its display goes dark, so a run of
        # failures usually means an empty battery rather than a script problem.
        if failures >= FAILURES_UNTIL_UNAVAILABLE and not marked_unavailable:
            print(f"No data after {failures} attempts - marking sensors unavailable")
            for sensor, unit in SENSORS:
                send_to_ha(sensor, "unavailable", unit)
            marked_unavailable = True

        delay = min(RETRY_INTERVAL * 2 ** (failures - 1), MAX_RETRY_INTERVAL)
        print(f"No data received (attempt {failures}), retrying in {delay}s")
        await asyncio.sleep(delay)


asyncio.run(main())
