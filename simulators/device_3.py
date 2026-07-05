import time
import random
import requests

SERVER_URL = "http://127.0.0.1:8000/sensor-data"

DEVICE_ID = "ESP32_NODE_003"

while True:

    payload = {
        "device_id": DEVICE_ID,
        "temperature": round(random.uniform(28, 35), 2),
        "vibration": round(random.uniform(0.1, 1.5), 2)
    }

    try:
        response = requests.post(SERVER_URL, json=payload)

        print("--------------------------------")
        print("Device:", DEVICE_ID)
        print("Temperature:", payload["temperature"])
        print("Vibration:", payload["vibration"])
        print("Server:", response.json())

    except Exception as e:
        print("Connection Error:", e)

    time.sleep(5)