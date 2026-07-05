from fastapi import FastAPI, HTTPException
from datetime import datetime

from backend.models import SensorData
from backend.database import get_connection, init_db
from backend.services.ai_engine import analyze_device

# ----------------------------------------
# Initialize Database
# ----------------------------------------
init_db()

app = FastAPI(
    title="ZTII Backend",
    description="Zero-Touch Industrial Intelligence Backend API",
    version="1.0.0"
)

print("✅ ZTII Backend Loaded")


# ========================================
# HOME
# ========================================
@app.get("/")
def home():
    return {
        "status": "ZTII Backend Running",
        "message": "Welcome to Zero-Touch Industrial Intelligence"
    }


# ========================================
# SENSOR DATA INGESTION
# ========================================
@app.post("/sensor-data")
def receive_sensor(data: SensorData):

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ----------------------------------------
    # AI ANALYSIS (CORE INTELLIGENCE LAYER)
    # ----------------------------------------
    analysis = analyze_device(
        data.temperature,
        data.vibration
    )

    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------------------
    # STORE DEVICE LATEST STATE + AI RESULT
    # ----------------------------------------
    cursor.execute("""
        INSERT OR REPLACE INTO devices
        (
            device_id,
            temperature,
            vibration,
            status,
            health,
            risk,
            recommendation,
            registered_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.device_id,
        data.temperature,
        data.vibration,
        "Online",
        analysis["health"],
        analysis["risk"],
        analysis["recommendation"],
        current_time
    ))

    # ----------------------------------------
    # STORE SENSOR HISTORY (RAW DATA)
    # ----------------------------------------
    cursor.execute("""
        INSERT INTO sensor_history
        (
            device_id,
            temperature,
            vibration,
            recorded_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        data.device_id,
        data.temperature,
        data.vibration,
        current_time
    ))

    conn.commit()
    conn.close()

    return {
        "message": "Sensor data stored successfully",
        "device": data.device_id
    }


# ========================================
# GET ALL DEVICES (WITH AI DATA)
# ========================================
@app.get("/devices")
def get_devices():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM devices")
    rows = cursor.fetchall()
    conn.close()

    return {
        row["device_id"]: {
            "temperature": row["temperature"],
            "vibration": row["vibration"],
            "status": row["status"],
            "health": row["health"],
            "risk": row["risk"],
            "recommendation": row["recommendation"],
            "registered_at": row["registered_at"]
        }
        for row in rows
    }


# ========================================
# GET SINGLE DEVICE
# ========================================
@app.get("/device/{device_id}")
def get_device(device_id: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM devices WHERE device_id = ?",
        (device_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return dict(row)


# ========================================
# GET HISTORY
# ========================================
@app.get("/history/{device_id}")
def get_history(device_id: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            temperature,
            vibration,
            recorded_at
        FROM sensor_history
        WHERE device_id = ?
        ORDER BY id ASC
    """, (device_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]