import requests
import random
import time

API_URL = "http://127.0.0.1:8000/sensor-data"

devices = [
    "ESP32_NODE_001",
    "ESP32_NODE_002",
    "ESP32_NODE_003"
]

print("🚀 ZTII Simulator Started")

while True:

    for device in devices:

        payload = {
            "device_id": device,
            "temperature": round(random.uniform(25, 40), 2),
            "vibration": round(random.uniform(0.2, 2.5), 2)
        }

        try:
            response = requests.post(API_URL, json=payload)

            print(
                f"{device} | "
                f"Temp={payload['temperature']}°C | "
                f"Vibration={payload['vibration']} | "
                f"Status={response.status_code}"
            )

        except Exception as e:
            print("Connection Error:", e)

    time.sleep(3)