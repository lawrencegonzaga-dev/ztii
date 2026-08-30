import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.database as database
from backend.main import receive_sensor
from backend.models import SensorData


class SensorIngestionRegressionTests(unittest.TestCase):
    """
    Regression tests for the first Warning/Critical reading of a
    brand-new device.

    analyze_device() persists alerts through a separate connection
    referencing devices(device_id), so the device row must exist and
    be committed before analysis runs. Each test runs against an
    isolated temporary database.
    """

    def setUp(self):
        self.previous_database_path = database.DATABASE_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_dir.name) / "ztii-test.db"
        database.init_db()

    def tearDown(self):
        database.DATABASE_PATH = self.previous_database_path
        self.temp_dir.cleanup()

    def _query(self, sql, params=()):
        conn = sqlite3.connect(database.DATABASE_PATH)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def test_first_critical_reading_provisions_device_without_error(self):
        response = receive_sensor(
            SensorData(
                device_id="ZTII-TEST-CRITICAL-001",
                temperature=82.0,
                vibration=1.8,
            )
        )

        self.assertEqual(response["analysis"]["health"], "Critical")

        devices = self._query(
            "SELECT health, status FROM devices WHERE device_id = ?",
            ("ZTII-TEST-CRITICAL-001",),
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], "Critical")
        self.assertEqual(devices[0][1], "Online")

        history = self._query(
            "SELECT temperature, vibration FROM sensor_history WHERE device_id = ?",
            ("ZTII-TEST-CRITICAL-001",),
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0], 82.0)
        self.assertEqual(history[0][1], 1.8)

        queue = self._query(
            "SELECT synced FROM offline_queue WHERE device_id = ?",
            ("ZTII-TEST-CRITICAL-001",),
        )
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0][0], 0)

        alerts = self._query(
            "SELECT level, status FROM alerts WHERE device_id = ?",
            ("ZTII-TEST-CRITICAL-001",),
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "Critical")
        self.assertEqual(alerts[0][1], "ACTIVE")

    def test_first_warning_reading_provisions_device_without_error(self):
        response = receive_sensor(
            SensorData(
                device_id="ZTII-TEST-WARNING-001",
                temperature=58.0,
                vibration=0.4,
            )
        )

        self.assertEqual(response["analysis"]["health"], "Warning")

        devices = self._query(
            "SELECT health FROM devices WHERE device_id = ?",
            ("ZTII-TEST-WARNING-001",),
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], "Warning")

        history = self._query(
            "SELECT id FROM sensor_history WHERE device_id = ?",
            ("ZTII-TEST-WARNING-001",),
        )
        self.assertEqual(len(history), 1)

        alerts = self._query(
            "SELECT level, status FROM alerts WHERE device_id = ?",
            ("ZTII-TEST-WARNING-001",),
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "Warning")
        self.assertEqual(alerts[0][1], "ACTIVE")

    def test_first_normal_reading_creates_device_without_alert(self):
        response = receive_sensor(
            SensorData(
                device_id="ZTII-TEST-NORMAL-001",
                temperature=40.0,
                vibration=0.3,
            )
        )

        self.assertEqual(response["analysis"]["health"], "Normal")

        devices = self._query(
            "SELECT health FROM devices WHERE device_id = ?",
            ("ZTII-TEST-NORMAL-001",),
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], "Normal")

        alerts = self._query(
            "SELECT id FROM alerts WHERE device_id = ?",
            ("ZTII-TEST-NORMAL-001",),
        )
        self.assertEqual(len(alerts), 0)
