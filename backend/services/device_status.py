"""Authoritative device connectivity state, derived from last_seen.

Status is calculated at read time from the timestamp of the last accepted
telemetry. No background job mutates devices.status; a stale or offline
device is the natural result of time advancing.
"""

import os
from datetime import datetime, timezone

DEFAULT_STALE_AFTER_SECONDS = 30
DEFAULT_OFFLINE_AFTER_SECONDS = 120


def _positive_int(value):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _threshold(env_name, default):
    return _positive_int(os.environ.get(env_name)) or default


# Invalid or non-positive configuration falls back to documented defaults.
STALE_AFTER_SECONDS = _threshold("ZTII_STALE_AFTER_SECONDS", DEFAULT_STALE_AFTER_SECONDS)
OFFLINE_AFTER_SECONDS = _threshold("ZTII_OFFLINE_AFTER_SECONDS", DEFAULT_OFFLINE_AFTER_SECONDS)

# The offline threshold must be strictly greater than the stale threshold.
if OFFLINE_AFTER_SECONDS <= STALE_AFTER_SECONDS:
    STALE_AFTER_SECONDS = DEFAULT_STALE_AFTER_SECONDS
    OFFLINE_AFTER_SECONDS = DEFAULT_OFFLINE_AFTER_SECONDS


def utc_now_iso():
    """Current UTC time as ISO-8601 with an explicit offset."""
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value):
    """Parse an ISO-8601 timestamp; naive values are interpreted as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def derive_device_status(last_seen, now=None, stale_after=None, offline_after=None):
    """Derive connectivity state from the last accepted telemetry time.

    last_seen is None -> "Waiting" (provisioned, never seen).
    age <= stale threshold -> "Online"
    stale < age <= offline threshold -> "Stale"
    age > offline threshold -> "Offline"
    """
    stale_limit = stale_after if stale_after is not None else STALE_AFTER_SECONDS
    offline_limit = offline_after if offline_after is not None else OFFLINE_AFTER_SECONDS

    seen_at = parse_timestamp(last_seen)
    if seen_at is None:
        return "Waiting"

    reference = now if now is not None else datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    age_seconds = (reference - seen_at).total_seconds()
    if age_seconds <= stale_limit:
        return "Online"
    if age_seconds <= offline_limit:
        return "Stale"
    return "Offline"
