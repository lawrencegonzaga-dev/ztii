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

from fastapi import HTTPException

import backend.database as database
from backend.main import (
    discover_device,
    discover_device_dashboard,
    discover_device_legacy,
    submit_sensor_data,
)
from backend.models import DeviceDiscovery, SensorData
from backend.services.device_auth import (
    CONFIG_ENV_VAR,
    authenticate_device,
    load_device_keys,
)

# Test-only credentials. These values must never appear in runtime source.
# All device IDs used by provisioning/telemetry boundary tests must be
# enrolled here; unenrolled IDs are exercised separately to prove that
# unknown devices are rejected.
TRUSTED_CONFIG = {
    "ZTII-TEST-AUTH-001": "secret-A",
    "ZTII-TEST-AUTH-002": "secret-B",
    "ZTII-TEST-AUTH-DISC-000": "secret-A",
    "ZTII-TEST-AUTH-DISC-001": "secret-A",
    "ZTII-TEST-AUTH-DISC-002": "secret-A",
    "ZTII-TEST-AUTH-TELEM-001": "secret-A",
    "ZTII-TEST-AUTH-TELEM-002": "secret-A",
    "ZTII-TEST-AUTH-TELEM-CRIT-001": "secret-A",
}

DISCOVERY_ROUTES = (discover_device, discover_device_dashboard, discover_device_legacy)


class DeviceAuthHelperTests(unittest.TestCase):
    """Unit tests for the centralized authentication helper."""

    def setUp(self):
        self._previous_config = os.environ.get(CONFIG_ENV_VAR)
        os.environ[CONFIG_ENV_VAR] = json.dumps(TRUSTED_CONFIG)

    def tearDown(self):
        os.environ.pop(CONFIG_ENV_VAR, None)
        if self._previous_config is not None:
            os.environ[CONFIG_ENV_VAR] = self._previous_config

    def _set_config(self, raw_value):
        os.environ[CONFIG_ENV_VAR] = raw_value

    def test_correct_device_and_key_succeeds(self):
        # Must not raise.
        authenticate_device("ZTII-TEST-AUTH-001", "secret-A")
        authenticate_device("ZTII-TEST-AUTH-002", "secret-B")

    def test_missing_key_rejected_401(self):
        with self.assertRaises(HTTPException) as context:
            authenticate_device("ZTII-TEST-AUTH-001", None)
        self.assertEqual(context.exception.status_code, 401)

    def test_wrong_key_rejected_401(self):
        with self.assertRaises(HTTPException) as context:
            authenticate_device("ZTII-TEST-AUTH-001", "wrong-key")
        self.assertEqual(context.exception.status_code, 401)

    def test_unknown_device_rejected_401(self):
        with self.assertRaises(HTTPException) as context:
            authenticate_device("ZTII-TEST-UNKNOWN", "secret-A")
        self.assertEqual(context.exception.status_code, 401)

    def test_cross_device_key_rejected_401(self):
        with self.assertRaises(HTTPException) as context:
            authenticate_device("ZTII-TEST-AUTH-001", "secret-B")
        self.assertEqual(context.exception.status_code, 401)

    def test_missing_config_fails_closed_503(self):
        os.environ.pop(CONFIG_ENV_VAR, None)
        with self.assertRaises(HTTPException) as context:
            load_device_keys()
        self.assertEqual(context.exception.status_code, 503)

    def test_malformed_config_fails_closed_503(self):
        for raw in ("", "   ", "not-json", "[1, 2]", "{}", '{"ZTII-TEST-AUTH-001": 123}'):
            with self.subTest(raw=raw):
                self._set_config(raw)
                with self.assertRaises(HTTPException) as context:
                    load_device_keys()
                self.assertEqual(context.exception.status_code, 503)


class DeviceAuthBoundaryTests(unittest.TestCase):
    """
    HTTP-boundary authentication regression tests.

    TestClient is unavailable (httpx is not installed and importing the
    app triggers lifespan startup), so each test invokes the route
    functions directly with an explicit x_device_key value. The routes
    perform authentication internally before any state change, so this
    exercises the same credential enforcement as the HTTP layer.

    Each test runs against an isolated temporary database; the trusted
    credential map is supplied through the environment and restored
    afterwards.
    """

    def setUp(self):
        self.previous_database_path = database.DATABASE_PATH
        self.previous_config = os.environ.get(CONFIG_ENV_VAR)
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_dir.name) / "ztii-test.db"
        database.init_db()
        os.environ[CONFIG_ENV_VAR] = json.dumps(TRUSTED_CONFIG)

    def tearDown(self):
        database.DATABASE_PATH = self.previous_database_path
        os.environ.pop(CONFIG_ENV_VAR, None)
        if self.previous_config is not None:
            os.environ[CONFIG_ENV_VAR] = self.previous_config
        self.temp_dir.cleanup()

    def _query(self, sql, params=()):
        conn = sqlite3.connect(database.DATABASE_PATH)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def _mutation_counts(self):
        return {
            table: self._query(f"SELECT COUNT(*) FROM {table}")[0][0]
            for table in ("devices", "device_registry", "assets", "asset_topology")
        }

    def _discovery_body(self, device_id):
        return DeviceDiscovery(device_id=device_id)

    def test_correct_key_provisions_on_all_discovery_routes(self):
        for index, route in enumerate(DISCOVERY_ROUTES):
            device_id = f"ZTII-TEST-AUTH-DISC-{index:03d}"
            response = route(self._discovery_body(device_id), x_device_key="secret-A")

            self.assertEqual(response["device_id"], device_id)
            self.assertEqual(
                self._query(
                    "SELECT device_id FROM devices WHERE device_id = ?", (device_id,)
                ),
                [(device_id,)],
            )
            self.assertEqual(
                len(self._query(
                    "SELECT device_id FROM device_registry WHERE device_id = ?",
                    (device_id,),
                )),
                1,
            )
            self.assertEqual(
                len(self._query(
                    "SELECT asset_id FROM assets WHERE device_id = ?", (device_id,)
                )),
                1,
            )
            self.assertEqual(
                len(self._query(
                    "SELECT t.id FROM asset_topology t JOIN assets a "
                    "ON t.asset_id = a.asset_id WHERE a.device_id = ?",
                    (device_id,),
                )),
                1,
            )

    def test_wrong_key_discovery_rejected_with_zero_mutation(self):
        before = self._mutation_counts()

        with self.assertRaises(HTTPException) as context:
            discover_device(
                self._discovery_body("ZTII-TEST-AUTH-001"), x_device_key="wrong-key"
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(self._mutation_counts(), before)

    def test_missing_key_discovery_rejected_with_zero_mutation(self):
        before = self._mutation_counts()

        for route in DISCOVERY_ROUTES:
            with self.assertRaises(HTTPException) as context:
                route(self._discovery_body("ZTII-TEST-AUTH-001"), x_device_key=None)
            self.assertEqual(context.exception.status_code, 401)

        self.assertEqual(self._mutation_counts(), before)

    def test_unknown_device_discovery_rejected_with_zero_mutation(self):
        before = self._mutation_counts()

        with self.assertRaises(HTTPException) as context:
            discover_device(
                self._discovery_body("ZTII-TEST-AUTH-UNENROLLED"),
                x_device_key="secret-A",
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(self._mutation_counts(), before)

    def test_cross_device_key_discovery_rejected_with_zero_mutation(self):
        before = self._mutation_counts()

        with self.assertRaises(HTTPException) as context:
            discover_device(
                self._discovery_body("ZTII-TEST-AUTH-001"), x_device_key="secret-B"
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(self._mutation_counts(), before)


    def test_correct_key_telemetry_accepted_and_processed(self):
        device_id = "ZTII-TEST-AUTH-TELEM-001"

        discover_device(self._discovery_body(device_id), x_device_key="secret-A")

        response = submit_sensor_data(
            SensorData(device_id=device_id, temperature=42.0, vibration=0.5),
            x_device_key="secret-A",
        )

        self.assertEqual(response["device"], device_id)
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM sensor_history WHERE device_id = ?", (device_id,)
            )[0][0],
            1,
        )
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM offline_queue WHERE device_id = ?", (device_id,)
            )[0][0],
            1,
        )

    def test_wrong_key_telemetry_rejected_with_zero_mutation(self):
        device_id = "ZTII-TEST-AUTH-TELEM-002"

        discover_device(self._discovery_body(device_id), x_device_key="secret-A")
        submit_sensor_data(
            SensorData(device_id=device_id, temperature=42.0, vibration=0.5),
            x_device_key="secret-A",
        )

        before_counts = {
            "sensor_history": self._query(
                "SELECT COUNT(*) FROM sensor_history WHERE device_id = ?", (device_id,)
            )[0][0],
            "offline_queue": self._query(
                "SELECT COUNT(*) FROM offline_queue WHERE device_id = ?", (device_id,)
            )[0][0],
            "alerts": self._query("SELECT COUNT(*) FROM alerts")[0][0],
        }
        before_device = self._query(
            "SELECT health, risk, temperature, vibration FROM devices WHERE device_id = ?",
            (device_id,),
        )

        with self.assertRaises(HTTPException) as context:
            submit_sensor_data(
                SensorData(device_id=device_id, temperature=90.0, vibration=2.0),
                x_device_key="wrong-key",
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM sensor_history WHERE device_id = ?", (device_id,)
            )[0][0],
            before_counts["sensor_history"],
        )
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM offline_queue WHERE device_id = ?", (device_id,)
            )[0][0],
            before_counts["offline_queue"],
        )
        self.assertEqual(
            self._query("SELECT COUNT(*) FROM alerts")[0][0],
            before_counts["alerts"],
        )
        self.assertEqual(
            self._query(
                "SELECT health, risk, temperature, vibration FROM devices WHERE device_id = ?",
                (device_id,),
            ),
            before_device,
        )

    def test_unknown_device_telemetry_not_auto_created(self):
        before = self._mutation_counts()

        with self.assertRaises(HTTPException) as context:
            submit_sensor_data(
                SensorData(
                    device_id="ZTII-TEST-AUTH-TELEM-UNENROLLED",
                    temperature=42.0,
                    vibration=0.5,
                ),
                x_device_key="some-arbitrary-key",
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(self._mutation_counts(), before)

    def test_phase1_critical_first_reading_works_over_authenticated_route(self):
        device_id = "ZTII-TEST-AUTH-TELEM-CRIT-001"

        response = submit_sensor_data(
            SensorData(device_id=device_id, temperature=82.0, vibration=1.8),
            x_device_key="secret-A",
        )

        self.assertEqual(response["device"], device_id)
        self.assertEqual(
            self._query(
                "SELECT health FROM devices WHERE device_id = ?", (device_id,)
            ),
            [("Critical",)],
        )
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM alerts WHERE device_id = ? AND level = 'Critical' "
                "AND status = 'ACTIVE'",
                (device_id,),
            )[0][0],
            1,
        )
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM sensor_history WHERE device_id = ?", (device_id,)
            )[0][0],
            1,
        )
        self.assertEqual(
            self._query(
                "SELECT COUNT(*) FROM offline_queue WHERE device_id = ?", (device_id,)
            )[0][0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
