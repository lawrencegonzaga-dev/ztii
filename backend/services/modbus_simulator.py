"""
ZTII Modbus TCP PLC Simulator
============================================================

Simulates an industrial PLC exposing machine data
through Modbus TCP holding registers.

Register Mapping:

40001 → Temperature × 10
40002 → Vibration × 100
40003 → Motor Speed
40004 → Motor Current × 10
40005 → Motor Status

Example:
Temperature 58.4°C → register value 584
Vibration 1.12     → register value 112
"""

import random
import time

try:
    from pymodbus.server import StartTcpServer
    from pymodbus.simulator import SimData, SimDevice
    from pymodbus.simulator.simutils import DataType
    _HAS_PYMODBUS = True
except ImportError:
    _HAS_PYMODBUS = False


# ============================================================
# CONFIGURATION
# ============================================================

PLC_HOST = "127.0.0.1"
PLC_PORT = 5020
PLC_UNIT_ID = 1


# ============================================================
# REGISTER ADDRESSES
# ============================================================

TEMP_REGISTER = 0
VIBRATION_REGISTER = 1
SPEED_REGISTER = 2
CURRENT_REGISTER = 3
STATUS_REGISTER = 4


# ============================================================
# INITIAL VALUES
# ============================================================

temperature = 40.0
vibration = 0.30
motor_speed = 1750
motor_current = 4.0
motor_status = 1


# ============================================================
# CREATE MODBUS DATA STORE
# ============================================================

async def refresh_registers(
    function_code,
    start_address,
    address,
    count,
    current_registers,
    set_values,
):
    """Refresh register values immediately before a Modbus request."""
    values = [
        int(temperature * 10),
        int(vibration * 100),
        motor_speed,
        int(motor_current * 10),
        motor_status,
    ]
    for index, value in enumerate(values):
        register_index = index - start_address
        if 0 <= register_index < len(current_registers):
            current_registers[register_index] = value


if _HAS_PYMODBUS:
    device = SimDevice(
        id=PLC_UNIT_ID,
        simdata=SimData(
            address=0,
            values=[
                int(temperature * 10),
                int(vibration * 100),
                motor_speed,
                int(motor_current * 10),
                motor_status,
            ],
            datatype=DataType.REGISTERS,
        ),
        action=refresh_registers,
    )
else:
    device = None


# ============================================================
# UPDATE SIMULATED PLC DATA
# ============================================================

def update_registers():

    global temperature
    global vibration
    global motor_speed
    global motor_current

    while True:

        # ----------------------------------------------------
        # Simulate normal machine variation
        # ----------------------------------------------------

        temperature += random.uniform(
            -0.5,
            0.5
        )

        vibration += random.uniform(
            -0.05,
            0.05
        )

        motor_speed += random.randint(
            -10,
            10
        )

        motor_current += random.uniform(
            -0.2,
            0.2
        )

        # ----------------------------------------------------
        # Keep values within realistic limits
        # ----------------------------------------------------

        temperature = max(
            35.0,
            min(75.0, temperature)
        )

        vibration = max(
            0.2,
            min(2.0, vibration)
        )

        motor_speed = max(
            0,
            min(2000, motor_speed)
        )

        motor_current = max(
            0.0,
            min(10.0, motor_current)
        )

        print(
            f"PLC DATA | "
            f"Temp={temperature:.1f}°C | "
            f"Vibration={vibration:.2f} | "
            f"Speed={motor_speed} RPM | "
            f"Current={motor_current:.1f} A"
        )

        time.sleep(2)


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    if not _HAS_PYMODBUS:
        print("pymodbus is not installed. Install it to run the PLC simulator:")
        print("  pip install pymodbus")
        import sys
        sys.exit(1)

    print()
    print("=" * 60)
    print("ZTII MODBUS TCP PLC SIMULATOR")
    print("=" * 60)

    print(
        f"PLC Address: {PLC_HOST}:{PLC_PORT}"
    )

    print()
    print("Register Mapping:")
    print("40001 → Temperature")
    print("40002 → Vibration")
    print("40003 → Motor Speed")
    print("40004 → Motor Current")
    print("40005 → Motor Status")
    print()

    import threading

    updater = threading.Thread(
        target=update_registers,
        daemon=True
    )

    updater.start()

    print("🟢 PLC simulator started.")
    print("Waiting for Modbus clients...")
    print()

    StartTcpServer(
        device,
        address=(
            PLC_HOST,
            PLC_PORT
        )
    )
