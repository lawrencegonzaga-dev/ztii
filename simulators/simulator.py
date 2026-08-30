import requests
import time
import math
import random
import json
import os
from typing import Dict, List, Tuple

# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

DISCOVERY_URL = f"{BASE_URL}/discover-device"
SENSOR_URL = f"{BASE_URL}/sensor-data"

# Multiple devices with different IDs
DEVICE_IDS = ["ESP32-001", "ESP32-002", "ESP32-003"]

# How long each scenario phase lasts
PHASE_DURATION = 10  # seconds


# ============================================================
# DEVICE AUTHENTICATION
# ============================================================

def load_device_keys() -> Dict[str, str]:
    """
    Loads per-device pre-shared keys from the environment.

    ZTII_DEVICE_KEYS_JSON holds a JSON object mapping device IDs to
    keys. ZTII_DEVICE_KEY provides one key shared by every device in
    DEVICE_IDS for single-device runs. Keys are never hard-coded.

    Returns:
        Dict mapping device_id -> PSK (possibly empty)
    """

    raw_map = os.getenv("ZTII_DEVICE_KEYS_JSON", "")

    if raw_map.strip():

        try:
            parsed = json.loads(raw_map)
        except ValueError:
            parsed = None

        if isinstance(parsed, dict) and parsed:
            return {
                str(device_id): str(key)
                for device_id, key in parsed.items()
                if isinstance(key, str) and key
            }

    single_key = os.getenv("ZTII_DEVICE_KEY", "")

    if single_key.strip():
        return {device_id: single_key.strip() for device_id in DEVICE_IDS}

    return {}


DEVICE_KEYS = load_device_keys()


def get_device_key(device_id: str) -> str:
    """
    Returns the configured PSK for a device (empty when unconfigured).
    """

    return DEVICE_KEYS.get(device_id, "")


# ============================================================
# SENSOR SCENARIOS
# ============================================================

def get_sensor_values(elapsed: float, device_offset: float = 0) -> Tuple[float, float, str]:
    """
    Automatically cycles through:
        NORMAL -> WARNING -> CRITICAL -> RECOVERY -> NORMAL -> repeat

    Args:
        elapsed: Time elapsed since start
        device_offset: Offset to make devices behave differently

    Returns:
        Tuple of (temperature, vibration, phase_name)
    """

    # Add offset so devices are at different phases
    adjusted_elapsed = elapsed + device_offset

    # 5 phases:
    # 0 = NORMAL
    # 1 = WARNING
    # 2 = CRITICAL
    # 3 = RECOVERY
    # 4 = NORMAL

    phase = int(adjusted_elapsed // PHASE_DURATION) % 5
    phase_time = adjusted_elapsed % PHASE_DURATION

    # ========================================================
    # 1. NORMAL
    # ========================================================

    if phase == 0:

        temperature = 40 + math.sin(phase_time) * 1.5
        vibration = 0.30 + math.sin(phase_time) * 0.03
        phase_name = "NORMAL"

    # ========================================================
    # 2. WARNING
    # ========================================================

    elif phase == 1:

        progress = phase_time / PHASE_DURATION
        temperature = 40 + (58 - 40) * progress
        vibration = 0.30 + (1.20 - 0.30) * progress
        phase_name = "WARNING"

    # ========================================================
    # 3. CRITICAL
    # ========================================================

    elif phase == 2:

        progress = phase_time / PHASE_DURATION
        temperature = 58 + (70 - 58) * progress
        vibration = 1.20 + (1.80 - 1.20) * progress
        phase_name = "CRITICAL"

    # ========================================================
    # 4. RECOVERY
    # ========================================================

    elif phase == 3:

        progress = phase_time / PHASE_DURATION
        temperature = 70 - (70 - 42) * progress
        vibration = 1.80 - (1.80 - 0.35) * progress
        phase_name = "RECOVERY"

    # ========================================================
    # 5. NORMAL AGAIN
    # ========================================================

    else:

        temperature = 42 + math.sin(phase_time) * 1.0
        vibration = 0.35 + math.sin(phase_time) * 0.02
        phase_name = "NORMAL"

    return temperature, vibration, phase_name


# ============================================================
# ZERO-TOUCH DEVICE DISCOVERY
# ============================================================

def discover_device(device_id: str) -> bool:
    """
    Sends the simulated device to the ZTII backend.

    Args:
        device_id: The device ID to discover

    Returns:
        True if discovery successful, False otherwise
    """

    # Initial sensor values for registration
    temperature = 40.0
    vibration = 0.30

    # Authentication is mandatory; fail clearly instead of sending
    # unauthenticated requests that the backend must reject.

    device_key = get_device_key(device_id)

    if not device_key:

        print(f"   Device {device_id}: No device key configured (set ZTII_DEVICE_KEYS_JSON or ZTII_DEVICE_KEY).")
        return False

    payload = {
        "device_id": device_id,
        "temperature": temperature,
        "vibration": vibration
    }

    print(f"   Discovering device: {device_id}...")

    try:

        response = requests.post(
            DISCOVERY_URL,
            json=payload,
            headers={"X-Device-Key": device_key},
            timeout=3
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            result = response.json()
            print(f"   Device {device_id}: {result.get('status')} - {result.get('message')}")
            return True

        # ----------------------------------------------------
        # VALIDATION ERROR
        # ----------------------------------------------------

        elif response.status_code == 422:

            print(f"   Device {device_id}: Backend rejected the discovery data.")
            return False

        # ----------------------------------------------------
        # OTHER BACKEND ERROR
        # ----------------------------------------------------

        else:

            print(f"   Device {device_id}: Discovery failed - HTTP {response.status_code}")
            return False

    # --------------------------------------------------------
    # BACKEND NOT RUNNING
    # --------------------------------------------------------

    except requests.exceptions.ConnectionError:

        print(f"   Device {device_id}: Backend not running.")
        return False

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        print(f"   Device {device_id}: Discovery request timed out.")
        return False

    # --------------------------------------------------------
    # OTHER ERROR
    # --------------------------------------------------------

    except Exception as e:

        print(f"   Device {device_id}: Discovery error - {e}")
        return False


def discover_all_devices(device_ids: List[str]) -> bool:
    """
    Discover all devices.

    Args:
        device_ids: List of device IDs to discover

    Returns:
        True if all devices discovered successfully, False otherwise
    """

    print()
    print("Discovering devices...")
    print("-" * 40)

    all_successful = True

    for device_id in device_ids:
        if not discover_device(device_id):
            all_successful = False

    print("-" * 40)

    if all_successful:
        print("All devices discovered successfully!")
    else:
        print("Some devices failed to discover.")

    return all_successful


# ============================================================
# SENSOR TRANSMISSION
# ============================================================

def send_sensor_data(
    device_id: str,
    temperature: float,
    vibration: float,
    phase_name: str,
) -> bool:
    """
    Sends current simulated sensor values to FastAPI.

    Args:
        device_id: The device ID
        temperature: Current temperature
        vibration: Current vibration

    Returns:
        True if transmission successful, False otherwise
    """

    device_key = get_device_key(device_id)

    if not device_key:

        print(f"{device_id}: No device key configured (set ZTII_DEVICE_KEYS_JSON or ZTII_DEVICE_KEY).")
        return False

    payload = {
        "device_id": device_id,
        "temperature": round(temperature, 2),
        "vibration": round(vibration, 2)
    }

    try:

        response = requests.post(
            SENSOR_URL,
            json=payload,
            headers={"X-Device-Key": device_key},
            timeout=3
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            result = response.json()
            analysis = result.get("analysis", {})
            health = analysis.get("health", "N/A")
            risk = analysis.get("risk", "N/A")

            # Print compact status
            print(
                f"{device_id:<12} | "
                f"[{phase_name:<8}] | "
                f"Temp: {temperature:>5.2f} C | "
                f"Vibration: {vibration:>4.2f} | "
                f"Health: {health:<8} | "
                f"Risk: {risk}"
            )

            return True

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        else:

            print(f"{device_id}: Backend error - HTTP {response.status_code}")
            return False

    # --------------------------------------------------------
    # BACKEND NOT RUNNING
    # --------------------------------------------------------

    except requests.exceptions.ConnectionError:

        print(f"{device_id}: Backend not running.")
        return False

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        print(f"{device_id}: Sensor request timed out.")
        return False

    # --------------------------------------------------------
    # OTHER ERROR
    # --------------------------------------------------------

    except Exception as e:

        print(f"{device_id}: Sensor error - {e}")
        return False


# ============================================================
# MAIN SIMULATOR
# ============================================================

def main():

    print()
    print("=" * 80)
    print("          ZTII INDUSTRIAL SENSOR SIMULATOR")
    print("=" * 80)
    print()

    print(f"Device IDs: {', '.join(DEVICE_IDS)}")

    unconfigured_devices = [d for d in DEVICE_IDS if not get_device_key(d)]

    if unconfigured_devices:

        print()
        print("Missing device keys for: " + ", ".join(unconfigured_devices))
        print("Set ZTII_DEVICE_KEYS_JSON (JSON object of device_id -> key)")
        print("or ZTII_DEVICE_KEY (single-device runs) before starting.")
        print()

        return

    print()
    print("Automatic demonstration:")
    print("   NORMAL -> WARNING -> CRITICAL -> RECOVERY -> NORMAL")
    print()
    print(f"Phase duration: {PHASE_DURATION} seconds per phase")
    print("Sensor interval: 2 seconds per device")
    print()
    print("Each device cycles through phases with different timing.")
    print("Press CTRL+C to stop.")
    print()

    # ========================================================
    # ZERO-TOUCH PROVISIONING
    # ========================================================

    if not discover_all_devices(DEVICE_IDS):

        print()
        print("Cannot start sensor transmission.")
        print("   Start the ZTII backend first.")
        print()

        return

    print()
    print("Starting automatic sensor transmission...")
    print()
    print("-" * 80)
    print(
        f"{'Device ID':<12} | "
        f"{'Phase':<8} | "
        f"{'Temp':<12} | "
        f"{'Vibration':<12} | "
        f"{'Health':<8} | "
        f"{'Risk'}"
    )
    print("-" * 80)

    # ========================================================
    # START SIMULATION
    # ========================================================

    start_time = time.time()
    previous_phases = {device_id: None for device_id in DEVICE_IDS}
    last_print_time = 0

    try:

        while True:

            elapsed = time.time() - start_time
            current_time = time.time()
            send_due = current_time - last_print_time >= 2

            # Process each device
            for idx, device_id in enumerate(DEVICE_IDS):
                # Different offset for each device
                device_offset = idx * (PHASE_DURATION / 3)  # Staggered phases

                # Generate sensor values for this device
                temperature, vibration, phase = get_sensor_values(
                    elapsed,
                    device_offset
                )

                # Only print phase changes
                if phase != previous_phases[device_id]:
                    previous_phases[device_id] = phase
                    print()
                    print(f"Device {device_id} -> Phase: {phase}")
                    print("-" * 80)
                    print(
                        f"{'Device ID':<12} | "
                        f"{'Phase':<8} | "
                        f"{'Temp':<12} | "
                        f"{'Vibration':<12} | "
                        f"{'Health':<8} | "
                        f"{'Risk'}"
                    )
                    print("-" * 80)

                # Send sensor data (only if enough time has passed since last send)
                if send_due:
                    send_sensor_data(device_id, temperature, vibration, phase)

            if send_due:
                last_print_time = current_time

            # Wait 0.5 seconds before next cycle
            time.sleep(0.5)

    except KeyboardInterrupt:

        print()
        print()
        print("=" * 80)
        print("ZTII SENSOR SIMULATOR STOPPED")
        print("=" * 80)
        print()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
