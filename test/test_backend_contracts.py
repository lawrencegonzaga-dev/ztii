import unittest

from pydantic import ValidationError
from pymodbus.simulator import SimDevice

from backend.main import toggle_network
from backend.models import SensorData
from backend.services.modbus_simulator import device
from backend.services.sync_service import is_network_available, set_network_available


class BackendContractTests(unittest.TestCase):
    def tearDown(self):
        set_network_available(True)

    def test_network_toggle_changes_simulated_state(self):
        set_network_available(True)
        response = toggle_network()
        self.assertEqual(response["network"], "offline")
        self.assertFalse(is_network_available())

    def test_sensor_payload_validation(self):
        payload = SensorData(device_id="MTR-001", temperature=55.5, vibration=1.2)
        self.assertEqual(payload.device_id, "MTR-001")

        with self.assertRaises(ValidationError):
            SensorData(device_id="bad id", temperature=55.5, vibration=1.2)
        with self.assertRaises(ValidationError):
            SensorData(device_id="MTR-001", temperature=500, vibration=1.2)
        with self.assertRaises(ValidationError):
            SensorData(device_id="MTR-001", temperature=55.5, vibration=-1)

    def test_modbus_simulator_uses_current_pymodbus_contract(self):
        self.assertIsInstance(device, SimDevice)
        self.assertEqual(device.id, 1)


if __name__ == "__main__":
    unittest.main()
