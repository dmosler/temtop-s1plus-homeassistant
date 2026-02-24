import asyncio
import requests
from bleak import BleakClient

MAC = "A4:C1:38:56:89:85"  # Replace with your S1+ MAC address
CHAR_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"

# Load config
config = {}
with open('/home/pi/temtop.conf') as f:
    for line in f:
        key, val = line.strip().split('=', 1)
        config[key] = val

HA_URL = config['HA_URL']
HA_TOKEN = config['HA_TOKEN']


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
    temp = data[25] / 10
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
    while True:
        try:
            values = await read_once()
            if values:
                pm25, aqi, temp, humidity = values
                print(f"PM2.5: {pm25} µg/m³ | AQI: {aqi} | Temp: {temp}°C | Humidity: {humidity}%")
                send_to_ha("pm25", pm25, "µg/m³")
                send_to_ha("aqi", aqi, "AQI")
                send_to_ha("temperature", temp, "°C")
                send_to_ha("humidity", humidity, "%")
            else:
                print("No data received, retrying...")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

        await asyncio.sleep(60)


asyncio.run(main())
