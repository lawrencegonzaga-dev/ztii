from datetime import datetime

from backend.database import get_connection


# ============================================================
# GET ALL ALERTS
# ============================================================

def get_alerts(
    status: str | None = None
):
    """
    Return alerts ordered from newest to oldest.

    If status is provided, only alerts with that
    status are returned.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        if status:

            cursor.execute(
                """
                SELECT
                    id,
                    device_id,
                    level,
                    message,
                    created_at,
                    status,
                    acknowledged_at,
                    resolved_at
                FROM alerts
                WHERE status = ?
                ORDER BY id DESC
                """,
                (status,)
            )

        else:

            cursor.execute(
                """
                SELECT
                    id,
                    device_id,
                    level,
                    message,
                    created_at,
                    status,
                    acknowledged_at,
                    resolved_at
                FROM alerts
                ORDER BY id DESC
                """
            )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:

        conn.close()


# ============================================================
# ACKNOWLEDGE ALERT
# ============================================================

def acknowledge_alert(
    alert_id: int
) -> bool:

    conn = get_connection()
    cursor = conn.cursor()

    try:

        acknowledged_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute(
            """
            UPDATE alerts
            SET
                status = 'acknowledged',
                acknowledged_at = ?
            WHERE id = ?
              AND status = 'active'
            """,
            (
                acknowledged_at,
                alert_id
            )
        )

        updated = cursor.rowcount

        conn.commit()

        return updated > 0

    finally:

        conn.close()


# ============================================================
# RESOLVE ALERT
# ============================================================

def resolve_alert(
    alert_id: int
) -> bool:

    conn = get_connection()
    cursor = conn.cursor()

    try:

        resolved_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute(
            """
            UPDATE alerts
            SET
                status = 'resolved',
                resolved_at = ?
            WHERE id = ?
              AND status IN (
                  'active',
                  'acknowledged'
              )
            """,
            (
                resolved_at,
                alert_id
            )
        )

        updated = cursor.rowcount

        conn.commit()

        return updated > 0

    finally:

        conn.close()