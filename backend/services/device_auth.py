"""Per-device PSK authentication for device-facing write routes.

Trusted credentials come from the ZTII_DEVICE_KEYS_JSON environment
variable. The environment is the pre-enrollment source of trust for this
prototype phase; no PSK or PSK hash is ever written to SQLite.

A device is trusted only when its device_id exists in the credential map
AND the submitted X-Device-Key value matches that device's key. A
well-formed device ID alone is never trust.
"""

import hmac
import json
import os
from typing import Dict, Optional

from fastapi import HTTPException

CONFIG_ENV_VAR = "ZTII_DEVICE_KEYS_JSON"

# Public header used to transport the device credential.
DEVICE_KEY_HEADER = "X-Device-Key"

# Fail-closed message for missing or unusable configuration.
CONFIG_ERROR_DETAIL = "Device authentication is not configured."

# Shared public message for unknown devices and wrong keys so the API
# never reveals whether a device ID exists in the trusted map.
CREDENTIAL_ERROR_DETAIL = "Invalid device credentials."

# Placeholder used to keep the unknown-device path a constant-time
# digest comparison, mirroring the wrong-key path.
_DUMMY_SECRET = "ztii-no-such-device-placeholder"


def _fail_closed() -> HTTPException:

    return HTTPException(status_code=503, detail=CONFIG_ERROR_DETAIL)


def load_device_keys() -> Dict[str, str]:

    """Return the trusted device_id -> PSK map.

    Fails closed (503) on missing, empty, malformed, or unusable
    configuration so authentication can never be silently disabled.
    """

    raw = os.getenv(CONFIG_ENV_VAR)

    if raw is None or not raw.strip():
        raise _fail_closed()

    try:
        parsed = json.loads(raw)
    except ValueError:
        raise _fail_closed()

    if not isinstance(parsed, dict) or not parsed:
        raise _fail_closed()

    trusted_keys: Dict[str, str] = {}

    for device_id, secret in parsed.items():

        if not isinstance(device_id, str) or not device_id.strip():
            raise _fail_closed()

        if not isinstance(secret, str) or not secret:
            raise _fail_closed()

        trusted_keys[device_id] = secret

    return trusted_keys


def authenticate_device(device_id: str, submitted_key: Optional[str]) -> None:

    """Authenticate a device_id + submitted key pair.

    Raises HTTPException 503 when authentication is not configured and
    HTTPException 401 when the credential is missing or invalid.
    Returns None on success. Never logs or returns any key material.
    """

    trusted_keys = load_device_keys()

    if not submitted_key:
        raise HTTPException(status_code=401, detail=CREDENTIAL_ERROR_DETAIL)

    expected_key = trusted_keys.get(device_id)

    if expected_key is None:
        # Same public message and a comparable digest operation as the
        # wrong-key path so the response does not leak enrollment state.
        hmac.compare_digest(submitted_key, _DUMMY_SECRET)
        raise HTTPException(status_code=401, detail=CREDENTIAL_ERROR_DETAIL)

    if not hmac.compare_digest(submitted_key, expected_key):
        raise HTTPException(status_code=401, detail=CREDENTIAL_ERROR_DETAIL)