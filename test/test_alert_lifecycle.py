import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.database as database
from backend.main import acknowledge_alert, receive_sensor
from backend.models import SensorData


# Threshold-safe sensor values (backend/services/ai_engine.py constants):
#   Normal:   temperature < 55.0 and vibration < 1.0
#   Warning:  temperature >= 55.0 and temperature < 65.0
#   Critical: temperature >= 65.0
NORMAL_TEMP = 42.0
NORMAL_VIB = 0.35
WARNING_TEMP = 58.0
WARNING_VIB = 0.45
CRITICAL_TEMP = 72.0
CRITICAL_VIB = 1.6


class AlertLifecycleRegressionTests(unittest.TestCase):
    """
    Regression tests for the alert lifecycle transitions applied
    during sensor ingestion (Phase 4).

    The lifecycle under test:

        Normal   -> resolve every open Warning/Critical alert
        Warning  -> resolve open Critical, create one open Warning
        Critical -> resolve open Warning, create one open Critical

    "Open" means status ACTIVE or ACKNOWLEDGED. No "Recovery"
    alert is ever created. Each test runs against an isolated
    temporary database via receive_sensor(), which exercises the
    same transaction the API route uses.
    """

    def setUp(self):
        self.previous_database_path = database.DATABASE_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_dir.name) / "ztii-test.db"
        database.init_db()

    def tearDown(self):
        database.DATABASE_PATH = self.previous_database_path
        self.temp_dir.cleanup()

    def _send_reading(self, device_id, temperature, vibration):
        return receive_sensor(
            SensorData(
                device_id=device_id,
                temperature=temperature,
                vibration=vibration,
            )
        )

    def _query(self, sql, params=()):
        conn = sqlite3.connect(database.DATABASE_PATH)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _open_alerts(self, device_id):
        return self._query(
            """
            SELECT level, status FROM alerts
            WHERE device_id = ?
              AND status IN ('ACTIVE', 'ACKNOWLEDGED')
            ORDER BY id
            """,
            (device_id,),
        )

    def _all_alerts(self, device_id):
        return self._query(
            """
            SELECT level, status FROM alerts
            WHERE device_id = ?
            ORDER BY id
            """,
            (device_id,),
        )

    # --------------------------------------------------
    # TEST A — Warning creation
    # --------------------------------------------------

    def test_a_normal_to_warning_creates_single_active_warning(self):
        device_id = "ZTII-TEST-LIFE-A-001"
        self._send_reading(device_id, NORMAL_TEMP, NORMAL_VIB)
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)

        open_alerts = self._open_alerts(device_id)
        self.assertEqual(len(open_alerts), 1)
        self.assertEqual(open_alerts[0][0], "Warning")
        self.assertEqual(open_alerts[0][1], "ACTIVE")

        levels = [row[0] for row in self._all_alerts(device_id)]
        self.assertNotIn("Recovery", levels)

    # --------------------------------------------------
    # TEST B — Warning deduplication
    # --------------------------------------------------

    def test_b_repeated_warning_readings_do_not_duplicate(self):
        device_id = "ZTII-TEST-LIFE-B-001"
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)
        self._send_reading(device_id, WARNING_TEMP + 1.0, WARNING_VIB)
        self._send_reading(device_id, WARNING_TEMP + 2.0, WARNING_VIB)

        open_warnings = [
            row for row in self._open_alerts(device_id)
            if row[0] == "Warning"
        ]
        self.assertEqual(len(open_warnings), 1)
        self.assertEqual(open_warnings[0][1], "ACTIVE")
        self.assertEqual(open_warnings[0][1], "ACTIVE")

    # --------------------------------------------------
    # TEST C — Acknowledgement is idempotent
    # --------------------------------------------------

    def test_c_repeated_acknowledgement_does_not_overwrite_timestamp(self):
        device_id = "ZTII-TEST-LIFE-C-001"
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)

        alert_row = self._query(
            "SELECT id FROM alerts WHERE device_id = ? ORDER BY id",
            (device_id,),
        )
        alert_id = alert_row[0][0]

        acknowledge_alert(alert_id)
        first_ack_time = self._query(
            "SELECT status, acknowledged_at FROM alerts WHERE id = ?",
            (alert_id,),
        )[0]
        self.assertEqual(first_ack_time[0], "ACKNOWLEDGED")
        self.assertIsNotNone(first_ack_time[1])

        # Acknowledging again must be idempotent (no exception raised).
        acknowledge_alert(alert_id)
        second_ack_time = self._query(
            "SELECT status, acknowledged_at FROM alerts WHERE id = ?",
            (alert_id,),
        )[0]

        self.assertEqual(second_ack_time[0], "ACKNOWLEDGED")
        self.assertEqual(second_ack_time[1], first_ack_time[1])

        # No duplicate alert may have been created.
        all_alerts = self._all_alerts(device_id)
        self.assertEqual(len(all_alerts), 1)

    # --------------------------------------------------
    # TEST D — Warning to Critical escalation
    # --------------------------------------------------

    def test_d_warning_to_critical_resolves_warning(self):
        device_id = "ZTII-TEST-LIFE-D-001"
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)
        self._send_reading(device_id, CRITICAL_TEMP, CRITICAL_VIB)

        open_alerts = self._open_alerts(device_id)
        self.assertEqual(len(open_alerts), 1)
        self.assertEqual(open_alerts[0][0], "Critical")
        self.assertEqual(open_alerts[0][1], "ACTIVE")

        resolved_warning = self._query(
            """
            SELECT status, resolved_at FROM alerts
            WHERE device_id = ? AND level = 'Warning'
            """,
            (device_id,),
        )
        self.assertEqual(len(resolved_warning), 1)
        self.assertEqual(resolved_warning[0][0], "RESOLVED")
        self.assertIsNotNone(resolved_warning[0][1])

    # --------------------------------------------------
    # TEST E — Critical recovery
    # --------------------------------------------------

    def test_e_critical_to_normal_resolves_critical(self):
        device_id = "ZTII-TEST-LIFE-E-001"
        self._send_reading(device_id, CRITICAL_TEMP, CRITICAL_VIB)
        self._send_reading(device_id, NORMAL_TEMP, NORMAL_VIB)

        self.assertEqual(len(self._open_alerts(device_id)), 0)

        resolved_critical = self._query(
            """
            SELECT status, resolved_at FROM alerts
            WHERE device_id = ? AND level = 'Critical'
            """,
            (device_id,),
        )
        self.assertEqual(len(resolved_critical), 1)
        self.assertEqual(resolved_critical[0][0], "RESOLVED")
        self.assertIsNotNone(resolved_critical[0][1])

        levels = [row[0] for row in self._all_alerts(device_id)]
        self.assertNotIn("Recovery", levels)

    # --------------------------------------------------
    # TEST F — Warning recovery
    # --------------------------------------------------

    def test_f_warning_to_normal_resolves_warning(self):
        device_id = "ZTII-TEST-LIFE-F-001"
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)
        self._send_reading(device_id, NORMAL_TEMP, NORMAL_VIB)

        self.assertEqual(len(self._open_alerts(device_id)), 0)

        resolved_warning = self._query(
            """
            SELECT status, resolved_at FROM alerts
            WHERE device_id = ? AND level = 'Warning'
            """,
            (device_id,),
        )
        self.assertEqual(len(resolved_warning), 1)
        self.assertEqual(resolved_warning[0][0], "RESOLVED")
        self.assertIsNotNone(resolved_warning[0][1])

        levels = [row[0] for row in self._all_alerts(device_id)]
        self.assertNotIn("Recovery", levels)

    # --------------------------------------------------
    # TEST G — Critical downgrade to Warning
    # --------------------------------------------------

    def test_g_critical_to_warning_resolves_critical(self):
        device_id = "ZTII-TEST-LIFE-G-001"
        self._send_reading(device_id, CRITICAL_TEMP, CRITICAL_VIB)
        self._send_reading(device_id, WARNING_TEMP, WARNING_VIB)

        open_alerts = self._open_alerts(device_id)
        self.assertEqual(len(open_alerts), 1)
        self.assertEqual(open_alerts[0][0], "Warning")
        self.assertEqual(open_alerts[0][1], "ACTIVE")

        resolved_critical = self._query(
            """
            SELECT status FROM alerts
            WHERE device_id = ? AND level = 'Critical'
            """,
            (device_id,),
        )
        self.assertEqual(len(resolved_critical), 1)
        self.assertEqual(resolved_critical[0][0], "RESOLVED")


if __name__ == "__main__":
    unittest.main()