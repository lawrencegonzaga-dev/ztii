"""Background synchronization worker with graceful shutdown support."""

from __future__ import annotations

import os
import threading

from backend.services.sync_service import synchronize_offline_queue


def sync_worker(stop_event: threading.Event, interval_seconds: int) -> None:
    print("ZTII offline sync worker started")
    while not stop_event.is_set():
        try:
            result = synchronize_offline_queue()
            if result["synced"] > 0:
                print(f"Synced {result['synced']} offline reading(s)")
        except Exception as exc:
            print(f"Sync worker error: {exc}")
        stop_event.wait(interval_seconds)


def start_sync_worker() -> tuple[threading.Thread, threading.Event]:
    """Start one daemon worker and return its thread and stop event."""
    interval = max(1, int(os.getenv("SYNC_INTERVAL_SECONDS", "5")))
    stop_event = threading.Event()
    worker = threading.Thread(
        target=sync_worker,
        args=(stop_event, interval),
        daemon=True,
        name="ztii-sync-worker",
    )
    worker.start()
    return worker, stop_event
