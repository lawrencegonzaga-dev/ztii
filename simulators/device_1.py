import requests
import time
import random

# Each one will act like:

# a machine sensor
# sending temperature
# sending vibration
# connecting to your FastAPI system

DEVICE_ID = "ESP32_NODE_001"

while True:
    data = {
        "device_id": DEVICE_ID,
        "temperature": round(random.uniform(28, 40), 2),
        "vibration": round(random.uniform(0.1, 2.5), 2)
    }

    try:
        response = requests.post(
            "http://127.0.0.1:8000/sensor-data",
            json=data
        )
        print("Sent:", data, "Response:", response.text)

    except Exception as e:
        print("Error:", e)

    time.sleep(3)