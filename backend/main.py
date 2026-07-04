from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

registered_devices = {}

@app.get("/")
def home():
    return {"status": "ZTII Backend Running"}

@app.post("/sensor-data")
def receive_sensor(data: dict):

    device_id = data["device_id"]

    # Auto-register if new
    if device_id not in registered_devices:
        registered_devices[device_id] = {
            "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ONLINE"
        }

        print(f"✅ New device automatically registered: {device_id}")

    return {
        "message": "Sensor data received",
        "device": device_id
    }

@app.get("/devices")
def get_devices():
    return registered_devices