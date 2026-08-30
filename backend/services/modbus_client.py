"""
ZTII Modbus Client
============================================================

Connects to a Modbus TCP PLC and reads industrial
machine registers.

Register Mapping:

40001 → Temperature × 10
40002 → Vibration × 100
40003 → Motor Speed
40004 → Motor Current × 10
40005 → Motor Status
"""

import os

try:
    from pymodbus.client import ModbusTcpClient
    _HAS_PYMODBUS = True
except ImportError:
    _HAS_PYMODBUS = False
    ModbusTcpClient = None


# ============================================================
# CONFIGURATION
# ============================================================

PLC_HOST = os.getenv("PLC_HOST", "127.0.0.1")
PLC_PORT = int(os.getenv("PLC_PORT", "5020"))
PLC_UNIT_ID = int(os.getenv("PLC_UNIT_ID", "1"))


# ============================================================
# REGISTER CONFIGURATION
# ============================================================

TEMP_REGISTER = 0
VIBRATION_REGISTER = 1
SPEED_REGISTER = 2
CURRENT_REGISTER = 3
STATUS_REGISTER = 4


# ============================================================
# CONNECT TO PLC
# ============================================================

def connect_to_plc():

    if not _HAS_PYMODBUS:
        print("pymodbus is not installed; real PLC connection unavailable.")
        return None

    client = ModbusTcpClient(
        host=PLC_HOST,
        port=PLC_PORT,
        timeout=3
    )

    if client.connect():

        print(f"Connected to PLC {PLC_HOST}:{PLC_PORT}")

        return client

    print(f"Failed to connect to PLC {PLC_HOST}:{PLC_PORT}")

    return None


# ============================================================
# READ PLC REGISTERS
# ============================================================

def read_plc_data():

    client = connect_to_plc()

    if client is None:

        return None

    try:

        response = client.read_holding_registers(
            address=TEMP_REGISTER,
            count=5,
            device_id=PLC_UNIT_ID
        )

        if response.isError():

            print("Modbus register read failed.")

            return None

        registers = response.registers

        # ----------------------------------------------------
        # Decode register values
        # ----------------------------------------------------

        temperature = registers[
            TEMP_REGISTER
        ] / 10

        vibration = registers[
            VIBRATION_REGISTER
        ] / 100

        motor_speed = registers[
            SPEED_REGISTER
        ]

        motor_current = registers[
            CURRENT_REGISTER
        ] / 10

        motor_status = registers[
            STATUS_REGISTER
        ]

        return {
            "temperature": temperature,
            "vibration": vibration,
            "motor_speed": motor_speed,
            "motor_current": motor_current,
            "motor_status": motor_status,
        }

    except Exception as e:

        print(f"Modbus communication error: {e}")

        return None

    finally:

        client.close()


# ============================================================
# CONNECTION TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("ZTII MODBUS CLIENT TEST")
    print("=" * 60)

    data = read_plc_data()

    if data:

        print()
        print("📡 PLC DATA RECEIVED")
        print("-" * 60)

        print(
            f"Temperature : "
            f"{data['temperature']:.1f} °C"
        )

        print(
            f"Vibration   : "
            f"{data['vibration']:.2f}"
        )

        print(
            f"Motor Speed : "
            f"{data['motor_speed']} RPM"
        )

        print(
            f"Motor Current: "
            f"{data['motor_current']:.1f} A"
        )

        print(
            f"Motor Status : "
            f"{data['motor_status']}"
        )

        print()
        print("✅ Modbus communication successful.")

    else:

        print()
        print(
            "❌ Could not read data from PLC."
        )
