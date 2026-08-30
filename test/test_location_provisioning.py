import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.database as database
from backend.main import discover_device, receive_sensor
from backend.models import DeviceDiscovery, SensorData


class LocationProvisioningRegressionTests(unittest.TestCase):
    """
    Regression tests for location-aware provisioning.

    The discovery routes previously dropped the operator-supplied
    location, so every asset was persisted with the default
    "Production Line 1" while the dashboard displayed the user's
    choice. These tests run against isolated temporary databases and
    call the route handler directly: entering the app through
    TestClient would trigger lifespan startup (sync worker plus
    production database initialization), which is out of scope here.
    """

    LOCATION_DEVICE_IDS = (
        "ZTII-TEST-LOCATION-001",
        "ZTII-TEST-LOCATION-002",
        "ZTII-TEST-LOCATION-003",
    )
    LOCATION_DEVICE_KEY = "secret-location-A"

    def setUp(self):
        self.previous_database_path = database.DATABASE_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_dir.name) / "ztii-test.db"
        database.init_db()

        # Discovery is now an authenticated route: enroll the devices
        # these tests provision so the auth boundary can be exercised.
        self.previous_device_keys = os.environ.get("ZTII_DEVICE_KEYS_JSON")
        os.environ["ZTII_DEVICE_KEYS_JSON"] = json.dumps(
            {device_id: self.LOCATION_DEVICE_KEY for device_id in self.LOCATION_DEVICE_IDS}
        )

    def tearDown(self):
        database.DATABASE_PATH = self.previous_database_path
        if self.previous_device_keys is None:
            os.environ.pop("ZTII_DEVICE_KEYS_JSON", None)
        else:
            os.environ["ZTII_DEVICE_KEYS_JSON"] = self.previous_device_keys
        self.temp_dir.cleanup()

    def _query(self, sql, params=()):
        conn = sqlite3.connect(database.DATABASE_PATH)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _provision(self, device_id, location):
        return discover_device(
            DeviceDiscovery(device_id=device_id, location=location),
            x_device_key=self.LOCATION_DEVICE_KEY,
        )

    def test_custom_location_persists_and_is_reported(self):
        response = self._provision("ZTII-TEST-LOCATION-001", "Assembly Line 4")

        self.assertEqual(response["status"], "provisioned")
        self.assertEqual(response["location"], "Assembly Line 4")

        assets = self._query(
            "SELECT location FROM assets WHERE device_id = ?",
            ("ZTII-TEST-LOCATION-001",),
        )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0][0], "Assembly Line 4")

        topology = self._query(
            """
            SELECT t.connected_to
            FROM asset_topology t
            JOIN assets a ON t.asset_id = a.asset_id
            WHERE a.device_id = ?
              AND t.relationship = 'MONITORS'
            """,
            ("ZTII-TEST-LOCATION-001",),
        )
        self.assertEqual(len(topology), 1)
        self.assertEqual(topology[0][0], "Assembly Line 4")

    def test_location_survives_later_telemetry(self):
        self._provision("ZTII-TEST-LOCATION-001", "Assembly Line 4")

        receive_sensor(
            SensorData(
                device_id="ZTII-TEST-LOCATION-001",
                temperature=40.0,
                vibration=0.3,
            )
        )

        devices = self._query(
            "SELECT device_id FROM devices WHERE device_id = ?",
            ("ZTII-TEST-LOCATION-001",),
        )
        self.assertEqual(len(devices), 1)

        assets = self._query(
            "SELECT location FROM assets WHERE device_id = ?",
            ("ZTII-TEST-LOCATION-001",),
        )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0][0], "Assembly Line 4")

    def test_custom_location_does_not_become_default(self):
        response = self._provision("ZTII-TEST-LOCATION-002", "Packaging Area B")

        self.assertEqual(response["location"], "Packaging Area B")

        persisted = self._query(
            "SELECT location FROM assets WHERE device_id = ?",
            ("ZTII-TEST-LOCATION-002",),
        )
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0][0], "Packaging Area B")
        self.assertNotEqual(persisted[0][0], "Production Line 1")

    def test_location_with_surrounding_whitespace_is_trimmed(self):
        response = self._provision(
            "ZTII-TEST-LOCATION-003", "  Assembly Line 4  "
        )

        self.assertEqual(response["location"], "Assembly Line 4")

        persisted = self._query(
            "SELECT location FROM assets WHERE device_id = ?",
            ("ZTII-TEST-LOCATION-003",),
        )
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0][0], "Assembly Line 4")