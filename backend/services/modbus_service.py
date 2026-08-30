"""
ZTII Modbus Service
============================================================

Provides the Modbus PLC communication layer for ZTII.

Phase I:
    Uses an in-memory simulated PLC.

Phase II:
    Can be replaced with a real Modbus TCP PLC.

Register Mapping:
    40001 -> Temperature
    40002 -> Vibration
    40003 -> Health
    40004 -> Risk Score
    40005 -> Alarm
"""

from typing import Dict, Optional


# ============================================================
# MODBUS REGISTER DEFINITIONS
# ============================================================

REG_TEMPERATURE = 40001
REG_VIBRATION = 40002
REG_HEALTH = 40003
REG_RISK = 40004
REG_ALARM = 40005


# ============================================================
# SIMULATED PLC MEMORY
# ============================================================

_plc_registers: Dict[int, int] = {

    REG_TEMPERATURE: 0,

    REG_VIBRATION: 0,

    REG_HEALTH: 0,

    REG_RISK: 0,

    REG_ALARM: 0,
}


# ============================================================
# HEALTH VALUES
# ============================================================

HEALTH_NORMAL = 0
HEALTH_WARNING = 1
HEALTH_CRITICAL = 2


# ============================================================
# ALARM VALUES
# ============================================================

ALARM_NORMAL = 0
ALARM_WARNING = 1
ALARM_CRITICAL = 2


# ============================================================
# WRITE REGISTER
# ============================================================

def write_register(
    address: int,
    value: int
) -> bool:
    """
    Write a value to a simulated PLC register.
    """

    if address not in _plc_registers:

        raise ValueError(
            f"Invalid Modbus register: {address}"
        )

    _plc_registers[address] = int(value)

    return True


# ============================================================
# READ REGISTER
# ============================================================

def read_register(
    address: int
) -> int:
    """
    Read a value from a simulated PLC register.
    """

    if address not in _plc_registers:

        raise ValueError(
            f"Invalid Modbus register: {address}"
        )

    return _plc_registers[address]


# ============================================================
# WRITE SENSOR DATA
# ============================================================

def write_sensor_data(
    temperature: float,
    vibration: float
) -> bool:
    """
    Write sensor values into the simulated PLC.

    Temperature is stored multiplied by 10
    to preserve one decimal place.

    Example:

        65.4°C
        ↓
        654
    """

    write_register(
        REG_TEMPERATURE,
        round(temperature * 10)
    )

    write_register(
        REG_VIBRATION,
        round(vibration * 100)
    )

    return True


# ============================================================
# WRITE AI STATUS
# ============================================================

def write_ai_status(
    health: str,
    risk_score: int
) -> bool:
    """
    Write AI health and risk information
    into the simulated PLC.
    """

    # --------------------------------------------------------
    # HEALTH
    # --------------------------------------------------------

    if "Critical" in health:

        health_value = HEALTH_CRITICAL

    elif "Warning" in health:

        health_value = HEALTH_WARNING

    else:

        health_value = HEALTH_NORMAL

    # --------------------------------------------------------
    # WRITE HEALTH
    # --------------------------------------------------------

    write_register(
        REG_HEALTH,
        health_value
    )

    # --------------------------------------------------------
    # WRITE RISK
    # --------------------------------------------------------

    write_register(
        REG_RISK,
        int(risk_score)
    )

    # --------------------------------------------------------
    # ALARM
    # --------------------------------------------------------

    if health_value == HEALTH_CRITICAL:

        alarm = ALARM_CRITICAL

    elif health_value == HEALTH_WARNING:

        alarm = ALARM_WARNING

    else:

        alarm = ALARM_NORMAL

    write_register(
        REG_ALARM,
        alarm
    )

    return True


# ============================================================
# READ PLC STATE
# ============================================================

def read_plc_state() -> Dict[str, int]:
    """
    Return the complete simulated PLC state.
    """

    return {

        "temperature": (
            read_register(REG_TEMPERATURE)
            / 10
        ),

        "vibration": (
            read_register(REG_VIBRATION)
            / 100
        ),

        "health": read_register(
            REG_HEALTH
        ),

        "risk": read_register(
            REG_RISK
        ),

        "alarm": read_register(
            REG_ALARM
        ),
    }


# ============================================================
# RESET PLC
# ============================================================

def reset_plc() -> None:
    """
    Reset all simulated PLC registers.
    """

    for address in _plc_registers:

        _plc_registers[address] = 0


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("ZTII MODBUS SERVICE TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # SENSOR DATA
    # --------------------------------------------------------

    write_sensor_data(
        temperature=65.4,
        vibration=1.72
    )

    # --------------------------------------------------------
    # AI STATUS
    # --------------------------------------------------------

    write_ai_status(
        health="🔴 Critical",
        risk_score=87
    )

    # --------------------------------------------------------
    # READ PLC
    # --------------------------------------------------------

    state = read_plc_state()

    print()
    print("Simulated PLC State:")
    print(state)

    print()
    print("Raw Registers:")

    for address, value in _plc_registers.items():

        print(
            f"Register {address}: {value}"
        )

    print()
    print("MODBUS TEST COMPLETE")
    print("=" * 60)