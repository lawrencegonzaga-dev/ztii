import unittest
from datetime import datetime, timezone

from backend.services.device_status import derive_device_status

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def seen(seconds_ago):
    from datetime import timedelta

    moment = NOW - timedelta(seconds=seconds_ago)
    return moment.isoformat()


class DeriveDeviceStatusTests(unittest.TestCase):
    def test_none_last_seen_is_waiting(self):
        self.assertEqual(derive_device_status(None, now=NOW), "Waiting")

    def test_age_10_seconds_is_online(self):
        self.assertEqual(derive_device_status(seen(10), now=NOW), "Online")

    def test_exactly_30_seconds_is_online(self):
        self.assertEqual(derive_device_status(seen(30), now=NOW), "Online")

    def test_age_31_seconds_is_stale(self):
        self.assertEqual(derive_device_status(seen(31), now=NOW), "Stale")

    def test_exactly_120_seconds_is_stale(self):
        self.assertEqual(derive_device_status(seen(120), now=NOW), "Stale")

    def test_age_121_seconds_is_offline(self):
        self.assertEqual(derive_device_status(seen(121), now=NOW), "Offline")

    def test_unparseable_last_seen_is_waiting(self):
        self.assertEqual(derive_device_status("not-a-timestamp", now=NOW), "Waiting")

    def test_explicit_thresholds_override_defaults(self):
        self.assertEqual(
            derive_device_status(seen(45), now=NOW, stale_after=60, offline_after=300),
            "Online",
        )

    def test_naive_timestamp_is_treated_as_utc(self):
        naive_seen = (NOW.replace(tzinfo=None)).isoformat()
        self.assertEqual(derive_device_status(naive_seen, now=NOW), "Online")


if __name__ == "__main__":
    unittest.main()
