import asyncio
import requests
from bleak import BleakClient
from datetime import datetime

MAC = "A4:C1:38:56:89:85"  # Replace with your S1+ MAC address
CHAR_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"
PACKET_LENGTH = 47

READ_INTERVAL = 120    # seconds between successful readings
RETRY_INTERVAL = 30    # seconds before the first retry after a failed reading
MAX_RETRY_INTERVAL = 300  # retries back off up to this
NIGHT_INTERVAL = 3600  # seconds between checks during night mode
ACTIVE_FROM = 6        # night mode ends at this hour
ACTIVE_UNTIL = 24      # night mode starts at this hour

# Consecutive failed readings before the HA entities are marked unavailable.
# Without this they would keep showing the last value indefinitely.
FAILURES_UNTIL_UNAVAILABLE = 3

# Order matches the tuple returned by parse_data(), and is also the order the
# values are pushed to Home Assistant. pm25 has to stay last: the HA automations
# trigger on sensor.temtop_pm25 and read the other three entities in their
# message template. Each send_to_ha() is its own HTTP request, so anything sent
# after pm25 is not in HA yet when the automation renders - it used to report
# the previous reading's AQI, and "unavailable" once the failure handling below
# started writing that state.
SENSORS = [
    ("aqi", "AQI"),
    ("temperature", "°C"),
    ("humidity", "%"),
    ("pm25", "µg/m³"),
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
    """Returns True if Home Assistant accepted the state."""
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
        # Without a timeout a stalled connection blocks the whole read loop
        response = requests.post(url, json=data, headers=headers, timeout=10)
        if response.status_code >= 400:
            print(f"HA rejected {sensor}: {response.status_code} {response.text}")
            return False
        return True
    except Exception as e:
        print(f"HA error: {e}")
        return False


def is_valid_packet(data):
    # The last byte is the sum of bytes 2-45, checked against captured packets
    return len(data) == PACKET_LENGTH and sum(data[2:-1]) & 0xFF == data[-1]


def parse_data(data):
    pm25 = int.from_bytes(data[22:24], 'big') / 10
    aqi = data[29]
    # Two bytes: a single byte wraps above 25.5 °C
    temp = int.from_bytes(data[24:26], 'big') / 10
    humidity = int.from_bytes(data[26:28], 'big') / 10
    return aqi, temp, humidity, pm25


async def read_once():
    result = {}
    ignored = []

    def handler(sender, data):
        # A shorter packet raises IndexError in parse_data(), a corrupted or
        # differently structured one would decode to plausible-looking garbage
        if not is_valid_packet(data):
            ignored.append(data.hex())
            return
        result['values'] = parse_data(data)

    try:
        async with BleakClient(MAC) as client:
            await client.start_notify(CHAR_UUID, handler)
            await asyncio.sleep(15)
            await client.stop_notify(CHAR_UUID)
    except Exception as e:
        if not isinstance(e, EOFError):
            print(f"Connection error: {type(e).__name__}: {e}")

    if ignored:
        print(f"Ignored {len(ignored)} invalid packet(s), last: {ignored[-1]}")
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
            aqi, temp, humidity, pm25 = values
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
            # A list, not a generator: all() would stop sending at the first
            # failure. If HA did not take every state, try again next round
            # instead of leaving the stale values in place for the whole outage.
            marked_unavailable = all([send_to_ha(sensor, "unavailable", unit)
                                      for sensor, unit in SENSORS])

        delay = min(RETRY_INTERVAL * 2 ** (failures - 1), MAX_RETRY_INTERVAL)
        print(f"No data received (attempt {failures}), retrying in {delay}s")
        await asyncio.sleep(delay)


asyncio.run(main())
