"""
ZTII PLC Service
============================================================

Reads industrial machine data from a Modbus TCP PLC and
passes temperature/vibration data into the existing
ZTII AI Engine.
"""

from datetime import datetime

from backend.services.modbus_client import read_plc_data
from backend.services.ai_engine import analyze_device


# ============================================================
# PLC DEVICE ID
# ============================================================

PLC_DEVICE_ID = "PLC-MOTOR-001"


# ============================================================
# READ + ANALYZE PLC
# ============================================================

def read_and_analyze_plc():
    """
    Read current PLC registers and analyze the machine state.
    """

    plc_data = read_plc_data()

    if plc_data is None:

        return {
            "success": False,
            "message": "Unable to communicate with PLC."
        }

    # --------------------------------------------------------
    # Extract sensor values
    # --------------------------------------------------------

    temperature = plc_data["temperature"]
    vibration = plc_data["vibration"]

    # --------------------------------------------------------
    # Run existing ZTII AI engine
    # --------------------------------------------------------

    analysis = analyze_device(
        temperature=temperature,
        vibration=vibration,
        device_id=PLC_DEVICE_ID
    )

    return {
        "success": True,
        "device_id": PLC_DEVICE_ID,

        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "plc": {
            "temperature": temperature,
            "vibration": vibration,
            "motor_speed": plc_data["motor_speed"],
            "motor_current": plc_data["motor_current"],
            "motor_status": plc_data["motor_status"],
        },

        "analysis": {
            "health": analysis["health"],
            "risk": analysis["risk"],
            "recommendation": analysis["recommendation"],
        }
    }