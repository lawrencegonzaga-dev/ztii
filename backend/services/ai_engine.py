"""
ZTII AI Engine
============================================================

Real-time industrial health, risk, anomaly detection,
recommendation, and event-based alert engine for
Zero-Touch Industrial Intelligence.

Inputs:
    - Temperature
    - Vibration

Outputs:
    - Health
    - Risk
    - Recommendation

Architecture:

    Sensor Data
         ↓
    Rule-Based AI
         ↓
    Health / Risk
         ↓
    Recommendation
         ↓
    Event Detection
         ↓
    SQLite Alerts

Explainable AI (SHAP) is handled separately by:

    backend.services.xai_engine
"""

from typing import Dict, Optional
from datetime import datetime

from backend.database import get_connection


# ============================================================
# THRESHOLDS
# ============================================================

# Temperature thresholds (°C)

TEMP_WARNING = 55.0
TEMP_CRITICAL = 65.0


# Vibration thresholds

VIBRATION_WARNING = 1.0
VIBRATION_CRITICAL = 1.5


# ============================================================
# RISK SCORE BASELINES
# ============================================================

TEMP_BASELINE = 40.0
TEMP_SPAN = 40.0

VIB_BASELINE = 0.3
VIB_SPAN = 1.7


# ============================================================
# RISK SCORE
# ============================================================

def _risk_score(
    temperature: float,
    vibration: float
) -> int:
    """
    Calculate the machine risk score.

    Vibration has slightly higher weight because it is
    an important indicator of mechanical problems.

    Returns:
        Integer risk score from 1 to 99.
    """

    # --------------------------------------------------------
    # TEMPERATURE DEVIATION
    # --------------------------------------------------------

    temp_deviation = max(
        0.0,
        (temperature - TEMP_BASELINE) / TEMP_SPAN
    )

    # --------------------------------------------------------
    # VIBRATION DEVIATION
    # --------------------------------------------------------

    vibration_deviation = max(
        0.0,
        (vibration - VIB_BASELINE) / VIB_SPAN
    )

    # --------------------------------------------------------
    # WEIGHTED RISK SCORE
    # --------------------------------------------------------

    score = (
        vibration_deviation * 0.55
        +
        temp_deviation * 0.45
    ) * 100

    # --------------------------------------------------------
    # LIMIT SCORE
    # --------------------------------------------------------

    return int(
        min(
            max(score, 1),
            99
        )
    )


# ============================================================
# ALERT LIFECYCLE TRANSITION
# ============================================================
#
# An alert is OPEN while its status is ACTIVE or ACKNOWLEDGED.
# An acknowledged alert still represents an unresolved machine
# condition, so it blocks duplicate creation and is resolved
# like any other open alert.
#
# Lifecycle rules:
#
#     Normal   -> resolve every open Warning/Critical alert.
#                 No "Recovery" alert is created; recovery is
#                 expressed by the resolved rows themselves.
#     Warning  -> resolve the open Critical alert (downgrade)
#                 and create a Warning only when no open
#                 Warning exists.
#     Critical -> resolve the open Warning alert (escalation)
#                 and create a Critical only when no open
#                 Critical exists.
#
# Historical alerts remain in the database as RESOLVED rows.
#
# ============================================================

def _apply_alert_transition(
    device_id: str,
    health: str,
    alert_message: Optional[str],
    conn=None,
):
    """
    Apply the alert lifecycle transition for a device's current
    health condition.

    When conn is provided, the transition executes on that
    connection WITHOUT committing, so the caller can persist the
    alert transition in the same transaction as the sensor
    reading. Otherwise a dedicated connection is opened and
    committed (standalone callers such as the PLC service).
    """

    owns_connection = conn is None

    if owns_connection:

        conn = get_connection()

    cursor = conn.cursor()
    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    try:

        # ====================================================
        # NORMAL: RESOLVE ALL OPEN WARNING/CRITICAL ALERTS
        # ====================================================

        if health == "Normal":

            cursor.execute(
                """
                UPDATE alerts
                SET status = 'RESOLVED',
                    resolved_at = ?
                WHERE device_id = ?
                  AND level IN ('Warning', 'Critical')
                  AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                """,
                (
                    now,
                    device_id
                )
            )

        # ====================================================
        # WARNING: RESOLVE OPEN CRITICAL, CREATE IF NONE OPEN
        # ====================================================

        elif health == "Warning":

            cursor.execute(
                """
                UPDATE alerts
                SET status = 'RESOLVED',
                    resolved_at = ?
                WHERE device_id = ?
                  AND level = 'Critical'
                  AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                """,
                (
                    now,
                    device_id
                )
            )

            cursor.execute(
                """
                SELECT id
                FROM alerts
                WHERE device_id = ?
                  AND level = 'Warning'
                  AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                ORDER BY id DESC
                LIMIT 1
                """,
                (device_id,)
            )

            if cursor.fetchone() is None and alert_message:

                cursor.execute(
                    """
                    INSERT INTO alerts (
                        device_id,
                        level,
                        message,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, 'ACTIVE', ?)
                    """,
                    (
                        device_id,
                        "Warning",
                        alert_message,
                        now
                    )
                )

        # ====================================================
        # CRITICAL: RESOLVE OPEN WARNING, CREATE IF NONE OPEN
        # ====================================================

        elif health == "Critical":

            cursor.execute(
                """
                UPDATE alerts
                SET status = 'RESOLVED',
                    resolved_at = ?
                WHERE device_id = ?
                  AND level = 'Warning'
                  AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                """,
                (
                    now,
                    device_id
                )
            )

            cursor.execute(
                """
                SELECT id
                FROM alerts
                WHERE device_id = ?
                  AND level = 'Critical'
                  AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                ORDER BY id DESC
                LIMIT 1
                """,
                (device_id,)
            )

            if cursor.fetchone() is None and alert_message:

                cursor.execute(
                    """
                    INSERT INTO alerts (
                        device_id,
                        level,
                        message,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, 'ACTIVE', ?)
                    """,
                    (
                        device_id,
                        "Critical",
                        alert_message,
                        now
                    )
                )

        if owns_connection:

            conn.commit()

    finally:

        if owns_connection:

            conn.close()


# ============================================================
# MAIN AI ANALYSIS
# ============================================================

def analyze_device(
    temperature: float,
    vibration: float,
    device_id: Optional[str] = None,
    conn=None,
) -> Dict[str, str]:
    """
    Analyze industrial sensor data.

    Determines:

        - Health status
        - Risk level
        - Risk score
        - Maintenance recommendation
        - Alert lifecycle transition

    Alert lifecycle:

        Normal   resolves open Warning/Critical alerts
        Warning  resolves an open Critical, opens one Warning
        Critical resolves an open Warning, opens one Critical

    Repeated readings in the same state do NOT create duplicate
    alerts, and acknowledged alerts still count as open.

    Args:
        temperature:
            Current temperature in °C.

        vibration:
            Current vibration value.

        device_id:
            Optional device identifier.

        conn:
            Optional shared database connection. When provided,
            the alert transition is executed on it without
            committing, so the caller can persist the alert in
            the same transaction as the sensor reading.

    Returns:
        Dictionary containing:

            health
            risk
            recommendation
    """

    # ========================================================
    # CONVERT INPUTS
    # ========================================================

    temperature = float(temperature)
    vibration = float(vibration)

    # ========================================================
    # CHECK THRESHOLDS
    # ========================================================

    temp_critical = (
        temperature >= TEMP_CRITICAL
    )

    vibration_critical = (
        vibration >= VIBRATION_CRITICAL
    )

    temp_warning = (
        temperature >= TEMP_WARNING
    )

    vibration_warning = (
        vibration >= VIBRATION_WARNING
    )

    # ========================================================
    # CALCULATE RISK SCORE
    # ========================================================

    score = _risk_score(
        temperature,
        vibration
    )

    # Alert message for the current condition. It is set by the
    # Warning/Critical branches below and consumed by the alert
    # lifecycle transition when a new alert must be created.

    alert_message = None

    # ========================================================
    # CRITICAL CONDITION
    # ========================================================

    if temp_critical or vibration_critical:

        health = "Critical"
        risk = f"{score}% (High)"

        # ----------------------------------------------------
        # BOTH CRITICAL
        # ----------------------------------------------------

        if temp_critical and vibration_critical:

            recommendation = (
                "Immediate inspection recommended — "
                "temperature and vibration are both "
                "above critical limits."
            )

            alert_message = (
                f"Critical condition detected. "
                f"Temperature: {temperature:.1f}°C, "
                f"Vibration: {vibration:.2f}"
            )

        # ----------------------------------------------------
        # VIBRATION CRITICAL
        # ----------------------------------------------------

        elif vibration_critical:

            recommendation = (
                "Inspect motor bearings and mechanical "
                "components — vibration exceeds the "
                "critical limit."
            )

            alert_message = (
                f"Critical vibration detected. "
                f"Vibration: {vibration:.2f}"
            )

        # ----------------------------------------------------
        # TEMPERATURE CRITICAL
        # ----------------------------------------------------

        else:

            recommendation = (
                "Inspect cooling system — "
                "temperature exceeds the critical limit."
            )

            alert_message = (
                f"Critical temperature detected. "
                f"Temperature: {temperature:.1f}°C"
            )

    # ========================================================
    # WARNING CONDITION
    # ========================================================

    elif temp_warning or vibration_warning:

        health = "Warning"
        risk = f"{score}% (Medium)"

        # ----------------------------------------------------
        # BOTH WARNING
        # ----------------------------------------------------

        if temp_warning and vibration_warning:

            recommendation = (
                "Schedule inspection — "
                "temperature and vibration are elevated."
            )

            alert_message = (
                f"Warning condition detected. "
                f"Temperature: {temperature:.1f}°C, "
                f"Vibration: {vibration:.2f}"
            )

        # ----------------------------------------------------
        # VIBRATION WARNING
        # ----------------------------------------------------

        elif vibration_warning:

            recommendation = (
                "Monitor vibration trend — "
                "vibration is approaching unsafe levels."
            )

            alert_message = (
                f"Elevated vibration detected. "
                f"Vibration: {vibration:.2f}"
            )

        # ----------------------------------------------------
        # TEMPERATURE WARNING
        # ----------------------------------------------------

        else:

            recommendation = (
                "Monitor temperature trend — "
                "temperature is approaching unsafe levels."
            )

            alert_message = (
                f"Elevated temperature detected. "
                f"Temperature: {temperature:.1f}°C"
            )

    # ========================================================
    # NORMAL CONDITION
    # ========================================================

    else:

        health = "Normal"
        risk = f"{score}% (Low)"

        recommendation = (
            "No immediate action required — "
            "operating within normal parameters."
        )

    # ========================================================
    # ALERT LIFECYCLE TRANSITION
    # ========================================================
    #
    # Opening/resolution of alerts is delegated to the lifecycle
    # transition. With conn=None the transition commits on its
    # own connection (standalone callers such as the PLC
    # service); with a conn provided it joins the caller's
    # transaction without committing.

    if device_id:

        _apply_alert_transition(
            device_id,
            health,
            alert_message,
            conn=conn
        )

    # ========================================================
    # RETURN ANALYSIS
    # ========================================================

    return {
        "health": health,
        "risk": risk,
        "recommendation": recommendation
    }


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    tests = [
        (40.0, 0.30),   # Normal
        (58.0, 0.60),   # Warning
        (58.0, 0.60),   # Same Warning - no duplicate
        (70.0, 1.80),   # Critical
        (70.0, 1.80),   # Same Critical - no duplicate
        (42.0, 0.35),   # Recovery
        (42.0, 0.35),   # Normal - no duplicate
        (45.0, 1.20),   # Warning again
        (42.0, 0.35),   # Recovery again
    ]

    print()
    print("ZTII AI ENGINE EVENT TEST")
    print("=" * 100)

    for temperature, vibration in tests:

        result = analyze_device(
            temperature,
            vibration,
            device_id="TEST-001"
        )

        print(
            f"T={temperature:>5.1f}°C | "
            f"V={vibration:>4.2f} | "
            f"{result['health']:<14} | "
            f"{result['risk']:<14} | "
            f"{result['recommendation']}"
        )

    print()
    print("=" * 100)
    print("AI ENGINE EVENT TEST COMPLETE")
