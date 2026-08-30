"""Run the ZTII API and dashboard as one deployable portfolio service."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    port = os.getenv("PORT", "8501")
    api_port = os.getenv("ZTII_API_PORT", "8000")
    environment = os.environ.copy()
    environment.setdefault("ZTII_API_URL", f"http://127.0.0.1:{api_port}")

    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            api_port,
            "--workers",
            "1",
        ],
        env=environment,
    )
    dashboard = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.address",
            "0.0.0.0",
            "--server.port",
            port,
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        env=environment,
    )
    processes = [api, dashboard]

    def stop_services(*_: object) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop_services)
    signal.signal(signal.SIGTERM, stop_services)

    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    finally:
        stop_services()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    return next((process.returncode or 0 for process in processes if process.returncode), 0)


if __name__ == "__main__":
    raise SystemExit(main())
