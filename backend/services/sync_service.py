"""
ZTII Offline Synchronization Service
============================================================

Handles synchronization of locally buffered sensor readings.

Architecture:

    /sensor-data
          ↓
    SQLite offline_queue
          ↓
    sync_service
          ↓
    Upstream / Central System
          ↓
    Mark reading as synced

Phase I:
    The upstream transmission is simulated.

Future:
    Replace transmit_readings() with an actual
    central/cloud API request.
"""

from typing import List, Dict, Any

from backend.database import get_connection


_NETWORK_AVAILABLE = True


def set_network_available(available: bool) -> None:
    """Set the simulated upstream network state used by the demo."""
    global _NETWORK_AVAILABLE
    _NETWORK_AVAILABLE = bool(available)


def is_network_available() -> bool:
    return _NETWORK_AVAILABLE


# ============================================================
# GET PENDING READINGS
# ============================================================

def get_pending_readings(
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Retrieve unsynchronized sensor readings.

    Args:
        limit:
            Maximum number of readings to retrieve
            during one synchronization cycle.

    Returns:
        List of pending sensor readings.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                device_id,
                temperature,
                vibration,
                recorded_at
            FROM offline_queue
            WHERE synced = 0
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# TRANSMIT READINGS
# ============================================================

def transmit_readings(
    readings: List[Dict[str, Any]]
) -> bool:
    """
    Simulate transmission of readings to an
    upstream/central system.

    Phase I:
        Transmission is simulated locally.

    Future:
        Replace this function with something like:

            requests.post(
                CENTRAL_API_URL,
                json=readings
            )

    Args:
        readings:
            Sensor readings waiting for synchronization.

    Returns:
        True if transmission succeeds.
    """

    if not readings:
        return True

    if not is_network_available():
        return False

    # --------------------------------------------------------
    # PHASE I SIMULATION
    # --------------------------------------------------------
    #
    # We assume the central system successfully
    # receives the readings.
    #
    # --------------------------------------------------------

    print(f"Simulated upstream transmission: {len(readings)} reading(s)")

    return True


# ============================================================
# MARK READINGS AS SYNCED
# ============================================================

def mark_as_synced(
    reading_ids: List[int]
) -> int:
    """
    Mark successfully transmitted readings as synced.

    Args:
        reading_ids:
            IDs of readings that were successfully
            transmitted.

    Returns:
        Number of readings marked as synced.
    """

    if not reading_ids:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    try:

        placeholders = ",".join(
            "?"
            for _ in reading_ids
        )

        cursor.execute(
            f"""
            UPDATE offline_queue
            SET synced = 1
            WHERE id IN ({placeholders})
            """,
            reading_ids
        )

        synced_count = cursor.rowcount

        conn.commit()

        return synced_count

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# SYNCHRONIZE OFFLINE QUEUE
# ============================================================

def synchronize_offline_queue(
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Synchronize pending offline sensor readings.

    Process:

        1. Get pending readings
        2. Transmit readings
        3. If transmission succeeds,
           mark them as synced

    Important:
        Readings are ONLY marked as synced after
        successful transmission.

    Args:
        batch_size:
            Maximum number of readings processed
            in one synchronization cycle.

    Returns:
        Synchronization result.
    """

    # ========================================================
    # 1. GET PENDING READINGS
    # ========================================================

    pending = get_pending_readings(
        limit=batch_size
    )

    if not pending:

        return {
            "status": "nothing_to_sync",
            "pending": 0,
            "synced": 0
        }

    # ========================================================
    # 2. TRANSMIT
    # ========================================================

    transmission_successful = transmit_readings(
        pending
    )

    # ========================================================
    # 3. TRANSMISSION FAILED
    # ========================================================

    if not transmission_successful:

        return {
            "status": "sync_failed",
            "pending": len(pending),
            "synced": 0
        }

    # ========================================================
    # 4. GET READING IDS
    # ========================================================

    reading_ids = [
        reading["id"]
        for reading in pending
    ]

    # ========================================================
    # 5. MARK AS SYNCED
    # ========================================================

    synced_count = mark_as_synced(
        reading_ids
    )

    # ========================================================
    # 6. RETURN RESULT
    # ========================================================

    return {
        "status": "synchronized",
        "pending": len(pending),
        "synced": synced_count
    }


# ============================================================
# CHECK OFFLINE QUEUE STATUS
# ============================================================

def get_sync_status() -> Dict[str, int]:
    """
    Return the current offline queue status.

    Useful for:

        - Dashboard
        - Debugging
        - Offline mode demonstration
        - Monitoring synchronization
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # PENDING
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM offline_queue
            WHERE synced = 0
            """
        )

        pending = cursor.fetchone()["count"]

        # ----------------------------------------------------
        # SYNCHRONIZED
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM offline_queue
            WHERE synced = 1
            """
        )

        synced = cursor.fetchone()["count"]

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM offline_queue
            """
        )

        total = cursor.fetchone()["count"]

        return {
            "total": total,
            "pending": pending,
            "synced": synced
        }

    finally:

        conn.close()
