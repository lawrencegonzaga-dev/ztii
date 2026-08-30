from contextlib import asynccontextmanager
from datetime import datetime
import os
import sqlite3

from typing import Optional

from fastapi import FastAPI, Header, HTTPException

from backend.models import DeviceDiscovery, SensorData
from backend.services.device_auth import authenticate_device
from backend.services.device_status import derive_device_status, utc_now_iso
from backend.database import get_connection, init_db
from backend.services.ai_engine import analyze_device
from backend.services.xai_engine import explain_prediction
from backend.services.sync_service import (
    is_network_available,
    set_network_available,
    synchronize_offline_queue,
)
from backend.services.sync_worker import start_sync_worker
# ✅ ADDED: Modbus service imports
from backend.services.modbus_service import (
    write_sensor_data,
    write_ai_status,
    read_plc_state
)
from backend.services.plc_service import read_and_analyze_plc


# ============================================================
# FASTAPI APPLICATION
# ============================================================

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize shared resources once per API process."""
    init_db()
    worker = None
    stop_event = None
    if os.getenv("ZTII_ENABLE_SYNC_WORKER", "false").lower() in {"1", "true", "yes"}:
        worker, stop_event = start_sync_worker()
    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if worker is not None:
            worker.join(timeout=2)

app = FastAPI(
    title="ZTII Backend",
    description="Zero-Touch Industrial Intelligence Backend API",
    version="1.1.0",
    lifespan=lifespan,
)

print("ZTII backend loaded")




# ============================================================
# HELPER
# ============================================================

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# PLC / MODBUS
# ============================================================

@app.get("/plc-data")
def get_plc_data():

    result = read_and_analyze_plc()

    if not result["success"]:

        raise HTTPException(
            status_code=503,
            detail=result["message"]
        )

    return result


# ============================================================
# NETWORK TOGGLE (for offline demo)
# ============================================================

@app.post("/network/toggle")
def toggle_network():
    available = not is_network_available()
    set_network_available(available)
    return {"network": "online" if available else "offline"}


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def home():

    return {
        "status": "ZTII Backend Running",
        "message": "Welcome to Zero-Touch Industrial Intelligence"
    }


# ============================================================
# DEVICE DISCOVERY + ZERO-TOUCH PROVISIONING
# ============================================================

def provision_device(
    device_id: str,
    device_type: str = "Industrial Sensor",
    location: str | None = None,
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        current_time = get_current_time()

        # ====================================================
        # CHECK DEVICE REGISTRY
        # ====================================================

        cursor.execute(
            """
            SELECT *
            FROM device_registry
            WHERE device_id = ?
            """,
            (device_id,)
        )

        existing_registry = cursor.fetchone()

        # ====================================================
        # CHECK DEVICES TABLE
        # ====================================================

        cursor.execute(
            """
            SELECT *
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,)
        )

        existing_device = cursor.fetchone()

        # ====================================================
        # CHECK ASSETS TABLE
        # ====================================================

        cursor.execute(
            """
            SELECT *
            FROM assets
            WHERE device_id = ?
            """,
            (device_id,)
        )

        existing_asset = cursor.fetchone()

        already_registered = existing_registry is not None
        identity = existing_registry["identity"] if existing_registry else f"ZTII-{device_id}"

        # ====================================================
        # REGISTER DEVICE IDENTITY
        # ====================================================

        if not existing_registry:
            cursor.execute(
                """
                INSERT INTO device_registry
                (
                    device_id,
                    device_type,
                    identity,
                    status,
                    discovered_at,
                    provisioned_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    device_type,
                    identity,
                    "Provisioned",
                    current_time,
                    current_time
                )
            )

        # ====================================================
        # CREATE DEVICE CURRENT STATE
        # ====================================================

        if not existing_device:

            cursor.execute(
                """
                INSERT INTO devices
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
                """,
                (
                    device_id,
                    None,
                    None,
                    "Waiting",
                    "Normal",
                    "Low",
                    "Monitoring ready.",
                    current_time
                )
            )

        # ====================================================
        # CREATE INDUSTRIAL ASSET
        # ====================================================

        asset_id = f"ASSET-{device_id}"

        asset_type = "Industrial Motor"
        asset_location = (location or "Production Line 1").strip()

        if not existing_asset:

            cursor.execute(
                """
                INSERT INTO assets
                (
                    asset_id,
                    device_id,
                    asset_type,
                    location,
                    parent_asset,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    device_id,
                    asset_type,
                    asset_location,
                    None,
                    "Online",
                    current_time
                )
            )

        else:

            asset_id = existing_asset["asset_id"]
            asset_type = existing_asset["asset_type"]
            asset_location = existing_asset["location"]

        # ====================================================
        # CREATE TOPOLOGY RELATIONSHIP
        # ====================================================

        cursor.execute(
            """
            SELECT id
            FROM asset_topology
            WHERE asset_id = ?
              AND connected_to = ?
              AND relationship = ?
            """,
            (
                asset_id,
                asset_location,
                "MONITORS"
            )
        )

        existing_topology = cursor.fetchone()

        if not existing_topology:

            cursor.execute(
                """
                INSERT INTO asset_topology
                (
                    asset_id,
                    connected_to,
                    relationship
                )
                VALUES (?, ?, ?)
                """,
                (
                    asset_id,
                    asset_location,
                    "MONITORS"
                )
            )

        # ====================================================
        # COMMIT
        # ====================================================

        conn.commit()

        # ====================================================
        # RETURN PROVISIONING RESULT
        # ====================================================

        return {
            "status": "already_registered" if already_registered else "provisioned",
            "device_id": device_id,
            "identity": identity,
            "device_type": device_type,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "location": asset_location,
            "message": (
                "Device was already registered; missing records were repaired."
                if already_registered
                else "Device discovered, provisioned, registered and mapped automatically."
            )
        }

    except sqlite3.IntegrityError as e:

        conn.rollback()

        raise HTTPException(
            status_code=409,
            detail=f"Device provisioning conflict: {str(e)}"
        )

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Provisioning failed due to an internal storage error."
        )

    finally:

        conn.close()


# ============================================================
# DISCOVERY ENDPOINT
# ============================================================

@app.post("/discover")
def discover_device(data: DeviceDiscovery, x_device_key: Optional[str] = Header(default=None)):

    # Authenticate before any device, registry, asset, or topology write.
    authenticate_device(data.device_id, x_device_key)

    return provision_device(
        data.device_id,
        data.device_type,
        data.location
    )


# ============================================================
# DASHBOARD DISCOVERY ENDPOINT
# ============================================================

@app.post("/devices/discover")
def discover_device_dashboard(data: DeviceDiscovery, x_device_key: Optional[str] = Header(default=None)):

    # Authenticate before any device, registry, asset, or topology write.
    authenticate_device(data.device_id, x_device_key)

    return provision_device(
        data.device_id,
        data.device_type,
        data.location
    )


# ============================================================
# LEGACY DISCOVERY ENDPOINT
# ============================================================

@app.post("/discover-device")
def discover_device_legacy(data: DeviceDiscovery, x_device_key: Optional[str] = Header(default=None)):

    # Authenticate before any device, registry, asset, or topology write.
    authenticate_device(data.device_id, x_device_key)

    return provision_device(
        data.device_id,
        data.device_type,
        data.location
    )


# ============================================================
# DEVICE REGISTRY
# ============================================================

@app.get("/registry")
def get_registry():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM device_registry
            ORDER BY discovered_at DESC
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# ASSET REGISTRY
# ============================================================

@app.get("/assets")
def get_assets():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM assets
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# ASSET TOPOLOGY
# ============================================================

@app.get("/topology")
def get_topology():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM asset_topology
            ORDER BY id ASC
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# SENSOR DATA INGESTION
# ============================================================
#
# Device
#     ↓
# Sensor Data
#     ↓
# AI Engine
#     ↓
# Device State
#     ↓
# Sensor History
#     ↓
# Alerts
#
# ============================================================

# ============================================================
# SENSOR DATA INGESTION
# ============================================================
#
# Pipeline:
#
# Device
#    ↓
# Sensor Data
#    ↓
# AI Engine
#    ↓
# Local SQLite
#    ├── devices
#    ├── sensor_history
#    ├── alerts
#    └── offline_queue
#
# The offline_queue acts as the local persistence layer
# for readings that may need synchronization later.
#
# ============================================================

# ============================================================
# ENSURE DEVICE EXISTS BEFORE ANALYSIS
# ============================================================

def _ensure_device_exists(
    device_id: str,
    temperature: float,
    vibration: float,
    registered_at: str,
) -> None:
    """
    Guarantee that a committed devices row exists before sensor ingestion.

    The device row is inserted and committed on its own connection so
    the ingestion connection in receive_sensor() can see it (SQLite
    connections cannot read each other's uncommitted rows). The alert
    transition then runs inside the ingestion transaction, so an alert
    and its corresponding sensor reading commit atomically together.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT device_id
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,)
        )

        existing = cursor.fetchone()

        if not existing:

            cursor.execute(
                """
                INSERT INTO devices
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
                """,
                (
                    device_id,
                    temperature,
                    vibration,
                    "Waiting",
                    "Unknown",
                    "0% (Low)",
                    "Awaiting first analysis.",
                    registered_at
                )
            )

            # Commit so the ingestion connection in receive_sensor()
            # can see this row (uncommitted rows are not visible
            # across SQLite connections).

            conn.commit()

    finally:

        conn.close()


@app.post("/sensor-data")
def submit_sensor_data(data: SensorData, x_device_key: Optional[str] = Header(default=None)):

    # Authenticate at the HTTP boundary before any state can change.
    # receive_sensor() stays callable directly as the trusted internal
    # business function for unit tests and internal flows.
    authenticate_device(data.device_id, x_device_key)

    return receive_sensor(data)


def receive_sensor(data: SensorData):

    current_time = get_current_time()

    # ========================================================
    # 0. ENSURE DEVICE EXISTS BEFORE INGESTION
    # ========================================================
    #
    # The devices row is created and committed on its own
    # connection first, so the ingestion connection below can see
    # it. Alert transitions then run on the ingestion connection,
    # so an alert can never reference a missing device and always
    # commits atomically with the sensor reading.
    #
    # ========================================================

    _ensure_device_exists(
        device_id=data.device_id,
        temperature=data.temperature,
        vibration=data.vibration,
        registered_at=current_time
    )

    # ========================================================
    # 1. AI ANALYSIS + ALERT TRANSITION (SHARED TRANSACTION)
    # ========================================================
    #
    # The connection is opened BEFORE analysis so that the alert
    # lifecycle transition inside analyze_device() executes on the
    # SAME connection as the device state, sensor history, and
    # offline queue writes. Nothing commits until step 7, so an
    # alert can never exist without its corresponding sensor
    # reading.
    #
    # ========================================================

    conn = get_connection()
    cursor = conn.cursor()

    analysis = analyze_device(
        data.temperature,
        data.vibration,
        data.device_id,
        conn=conn
    )

    try:

        # ====================================================
        # 2. CHECK DEVICE
        # ====================================================

        cursor.execute(
            """
            SELECT device_id
            FROM devices
            WHERE device_id = ?
            """,
            (data.device_id,)
        )

        existing = cursor.fetchone()

        # ====================================================
        # 3. CREATE DEVICE IF NECESSARY
        # ====================================================

        if not existing:

            cursor.execute(
                """
                INSERT INTO devices
                (
                    device_id,
                    temperature,
                    vibration,
                    status,
                    health,
                    risk,
                    recommendation,
                    registered_at,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.device_id,
                    data.temperature,
                    data.vibration,
                    "Online",
                    analysis["health"],
                    analysis["risk"],
                    analysis["recommendation"],
                    current_time,
                    utc_now_iso()
                )
            )

        # ====================================================
        # 4. UPDATE CURRENT DEVICE STATE
        # ====================================================

        else:

            cursor.execute(
                """
                UPDATE devices
                SET
                    temperature = ?,
                    vibration = ?,
                    status = ?,
                    health = ?,
                    risk = ?,
                    recommendation = ?,
                    last_seen = ?
                WHERE device_id = ?
                """,
                (
                    data.temperature,
                    data.vibration,
                    "Online",
                    analysis["health"],
                    analysis["risk"],
                    analysis["recommendation"],
                    utc_now_iso(),
                    data.device_id
                )
            )

        # ====================================================
        # 5. STORE SENSOR HISTORY
        # ====================================================

        cursor.execute(
            """
            INSERT INTO sensor_history
            (
                device_id,
                temperature,
                vibration,
                recorded_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                data.device_id,
                data.temperature,
                data.vibration,
                current_time
            )
        )

        # ====================================================
        # 6. STORE READING IN OFFLINE QUEUE
        # ====================================================
        #
        # synced = 0
        #
        # means this local reading has not yet been
        # synchronized with an upstream/central system.
        #
        # ====================================================

        cursor.execute(
            """
            INSERT INTO offline_queue
            (
                device_id,
                temperature,
                vibration,
                recorded_at,
                synced
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data.device_id,
                data.temperature,
                data.vibration,
                current_time,
                0
            )
        )

        # ====================================================
        # 7. COMMIT EVERYTHING
        # ====================================================

        conn.commit()

        # ====================================================
        # 8. UPDATE MODBUS PLC (AFTER COMMIT)
        # ====================================================
        #
        # We update the simulated PLC registers with the
        # latest sensor and AI data. If this fails, the
        # sensor data is still safely stored in SQLite.
        #
        # ====================================================

        modbus_updated = False

        try:

            # Write sensor values (temperature × 10, vibration × 100)
            write_sensor_data(
                temperature=data.temperature,
                vibration=data.vibration
            )

            # Extract numeric risk score from e.g. "87% (High)"
            risk_str = analysis["risk"]
            # Remove everything after the first '%' and take the number
            risk_score = int(risk_str.split("%")[0])

            # Write AI status
            write_ai_status(
                health=analysis["health"],
                risk_score=risk_score
            )

            modbus_updated = True

        except Exception as e:

            # Log the error but don't fail the request
            print(f"Modbus update failed: {e}")

        # ====================================================
        # 9. RESPONSE
        # ====================================================

        return {
            "message": "Sensor data stored successfully",
            "device": data.device_id,

            "analysis": {
                "health": analysis["health"],
                "risk": analysis["risk"],
                "recommendation": analysis["recommendation"]
            },

            "offline_storage": {
                "stored": True,
                "synced": False
            },

            "modbus": {
                "updated": modbus_updated
            }
        }

    except Exception:

        # If anything fails, don't partially save
        # the sensor transaction.

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# GET ALL DEVICES
# ============================================================

@app.get("/devices")
def get_devices():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                device_id,
                temperature,
                vibration,
                status,
                health,
                risk,
                recommendation,
                registered_at,
                last_seen
            FROM devices
            ORDER BY device_id
            """
        )

        rows = cursor.fetchall()

        return {
            row["device_id"]: {
                "temperature": row["temperature"],
                "vibration": row["vibration"],
                "status": derive_device_status(row["last_seen"]),
                "health": row["health"],
                "risk": row["risk"],
                "recommendation": row["recommendation"],
                "registered_at": row["registered_at"],
                "last_seen": row["last_seen"]
            }
            for row in rows
        }

    finally:

        conn.close()


# ============================================================
# GET SINGLE DEVICE
# ============================================================

@app.get("/device/{device_id}")
def get_device(device_id: str):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT *
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,)
        )

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )

        # Connectivity state is derived from last_seen, never from the legacy persisted string
        device_payload = dict(row)
        device_payload["status"] = derive_device_status(
            device_payload.get("last_seen")
        )
        return device_payload

    finally:

        conn.close()


# ============================================================
# GET SENSOR HISTORY
# ============================================================

@app.get("/history/{device_id}")
def get_history(device_id: str, limit: int = 500):

    limit = min(max(limit, 1), 2000)

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ====================================================
        # VERIFY DEVICE
        # ====================================================

        cursor.execute(
            """
            SELECT device_id
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,)
        )

        device = cursor.fetchone()

        if not device:

            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )

        # ====================================================
        # GET HISTORY
        # ====================================================

        cursor.execute(
            """
            SELECT
                temperature,
                vibration,
                recorded_at
            FROM sensor_history
            WHERE device_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (device_id, limit)
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in reversed(rows)
        ]

    finally:

        conn.close()



# ============================================================
# GET ALERTS
# ============================================================

@app.get("/alerts")
def get_alerts(include_resolved: bool = True, limit: int = 100):

    limit = min(max(limit, 1), 500)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                device_id,
                level,
                message,
                status,
                created_at,
                acknowledged_at,
                resolved_at
            FROM alerts
            WHERE (? = 1 OR status != 'RESOLVED')
            ORDER BY id DESC
            LIMIT ?
            """,
            (1 if include_resolved else 0, limit),
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


# ============================================================
# ACKNOWLEDGE ALERT
# ============================================================

@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):

    current_time = get_current_time()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, status
            FROM alerts
            WHERE id = ?
            """,
            (alert_id,)
        )

        alert = cursor.fetchone()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert not found"
            )

        if alert["status"] == "RESOLVED":
            raise HTTPException(
                status_code=400,
                detail="Alert is already resolved"
            )

        # Idempotent acknowledgement: re-acknowledging must not
        # overwrite the original acknowledged_at timestamp.
        if alert["status"] == "ACKNOWLEDGED":
            return {
                "message": "Alert already acknowledged",
                "alert_id": alert_id,
                "status": "ACKNOWLEDGED"
            }

        cursor.execute(
            """
            UPDATE alerts
            SET
                status = 'ACKNOWLEDGED',
                acknowledged_at = ?
            WHERE id = ?
            """,
            (
                current_time,
                alert_id
            )
        )

        conn.commit()

        return {
            "message": "Alert acknowledged",
            "alert_id": alert_id,
            "status": "ACKNOWLEDGED"
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# RESOLVE ALERT
# ============================================================

@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int):

    current_time = get_current_time()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, status
            FROM alerts
            WHERE id = ?
            """,
            (alert_id,)
        )

        alert = cursor.fetchone()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail="Alert not found"
            )

        if alert["status"] == "RESOLVED":
            raise HTTPException(
                status_code=400,
                detail="Alert is already resolved"
            )

        cursor.execute(
            """
            UPDATE alerts
            SET
                status = 'RESOLVED',
                resolved_at = ?
            WHERE id = ?
            """,
            (
                current_time,
                alert_id
            )
        )

        conn.commit()

        return {
            "message": "Alert resolved",
            "alert_id": alert_id,
            "status": "RESOLVED"
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# OFFLINE QUEUE SYNCHRONIZATION
# ============================================================

@app.post("/sync")
def sync_offline_data():

    result = synchronize_offline_queue()

    return result

# ============================================================
# OFFLINE QUEUE STATUS
# ============================================================

@app.get("/offline/status")
def offline_status():

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # PENDING
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM offline_queue
            WHERE synced = 0
        """)

        pending = cursor.fetchone()["count"]

        # ----------------------------------------------------
        # SYNCHRONIZED
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM offline_queue
            WHERE synced = 1
        """)

        synced = cursor.fetchone()["count"]

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        total = pending + synced

        return {
            "mode": "EDGE",
            "queue": {
                "total": total,
                "pending": pending,
                "synced": synced
            }
        }

    finally:

        conn.close()


# ============================================================
# EXPLAINABLE AI — SHAP
# ============================================================
#
# Flow:
#
# Dashboard
#     ↓
# GET /explain/{device_id}
#     ↓
# main.py gets latest sensor values
#     ↓
# xai_engine.explain_prediction()
#     ↓
# SHAP
#     ↓
# Explanation + contribution percentages
#
# ============================================================

@app.get("/explain/{device_id}")
def explain_device(device_id: str):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ====================================================
        # GET CURRENT DEVICE DATA
        # ====================================================

        cursor.execute(
            """
            SELECT
                device_id,
                temperature,
                vibration,
                health,
                risk
            FROM devices
            WHERE device_id = ?
            """,
            (device_id,)
        )

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )

        # ====================================================
        # SENSOR VALUES
        # ====================================================

        temperature = float(
            row["temperature"] or 0
        )

        vibration = float(
            row["vibration"] or 0
        )

        # ====================================================
        # SHAP EXPLANATION
        # ====================================================

        explanation = explain_prediction(
            temperature,
            vibration
        )

        # ====================================================
        # RETURN XAI RESULT
        # ====================================================

        return {
            "device_id": device_id,

            "explanation": explanation,

            "sensor_data": {
                "temperature": temperature,
                "vibration": vibration
            },

            "health": row["health"],
            "risk": row["risk"]
        }

    finally:

        conn.close()


# ============================================================
# ✅ NEW: PLC STATUS ENDPOINT
# ============================================================

@app.get("/plc/status")
def get_plc_status():

    return {
        "status": "online",
        "mode": "simulated",
        "registers": read_plc_state()
    }
