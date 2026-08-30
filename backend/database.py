import sqlite3
import os
from pathlib import Path


# ============================================================
# DATABASE LOCATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(
    os.getenv("ZTII_DATABASE_PATH", str(PROJECT_ROOT / "database" / "ztii.db"))
).expanduser().resolve()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a new SQLite database connection.
    """

    conn = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
        timeout=10,
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")

    return conn


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    """
    Create all required ZTII database tables.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ====================================================
        # 1. DEVICE REGISTRY
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id TEXT PRIMARY KEY,
                device_type TEXT,
                identity TEXT,
                status TEXT,
                discovered_at TEXT,
                provisioned_at TEXT
            )
        """)


        # ====================================================
        # 2. DEVICES
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                temperature REAL,
                vibration REAL,
                status TEXT,
                health TEXT,
                risk TEXT,
                recommendation TEXT,
                registered_at TEXT,
                last_seen TEXT
            )
        """)


        # ====================================================
        # 3. SENSOR HISTORY
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                temperature REAL,
                vibration REAL,
                recorded_at TEXT,

                FOREIGN KEY (device_id)
                    REFERENCES devices(device_id)
            )
        """)


        # ====================================================
        # 4. ALERTS
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                device_id TEXT NOT NULL,

                level TEXT NOT NULL,

                message TEXT NOT NULL,

                created_at TEXT NOT NULL,

                status TEXT DEFAULT 'ACTIVE',

                acknowledged_at TEXT,

                resolved_at TEXT,

                FOREIGN KEY (device_id)
                    REFERENCES devices(device_id)
            )
        """)

        # ====================================================
        # MIGRATION: ensure all expected columns exist
        # ====================================================

        # Check existing columns in the alerts table
        cursor.execute("PRAGMA table_info(alerts)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        # Define columns that must exist, with their SQL type and default
        required_columns = {
            "status": "TEXT DEFAULT 'ACTIVE'",
            "acknowledged_at": "TEXT",
            "resolved_at": "TEXT"
        }

        # Add any missing columns
        for col, col_type in required_columns.items():
            if col not in existing_columns:
                print(f"Adding column '{col}' to alerts table...")
                cursor.execute(f"ALTER TABLE alerts ADD COLUMN {col} {col_type}")
                conn.commit()

        # Existing databases created before last_seen tracking need the column added
        cursor.execute("PRAGMA table_info(devices)")
        device_columns = [row[1] for row in cursor.fetchall()]
        if "last_seen" not in device_columns:
            print("Adding column 'last_seen' to devices table...")
            cursor.execute("ALTER TABLE devices ADD COLUMN last_seen TEXT")
            conn.commit()


        # ====================================================
        # 5. ASSETS
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                device_id TEXT UNIQUE,
                asset_type TEXT,
                location TEXT,
                parent_asset TEXT,
                status TEXT,
                created_at TEXT,

                FOREIGN KEY (device_id)
                    REFERENCES device_registry(device_id)
            )
        """)


        # ====================================================
        # 6. ASSET TOPOLOGY
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asset_topology (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT,
                connected_to TEXT,
                relationship TEXT,

                FOREIGN KEY (asset_id)
                    REFERENCES assets(asset_id)
            )
        """)


        # ====================================================
        # 7. OFFLINE QUEUE
        # ====================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                device_id TEXT NOT NULL,

                temperature REAL NOT NULL,

                vibration REAL NOT NULL,

                recorded_at TEXT NOT NULL,

                synced INTEGER DEFAULT 0
            )
        """)


        # ====================================================
        # INDEX FOR FASTER SYNC QUERIES
        # ====================================================

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_offline_queue_synced
            ON offline_queue(synced)
        """)


        # ====================================================
        # INDEX FOR DEVICE HISTORY
        # ====================================================

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_history_device
            ON sensor_history(device_id)
        """)


        # ====================================================
        # INDEX FOR ALERTS
        # ====================================================

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_device
            ON alerts(device_id)
        """)


        # ====================================================
        # SAVE DATABASE CHANGES
        # ====================================================

        conn.commit()

        print("ZTII database initialized successfully.")
        print(f"Database: {DATABASE_PATH}")

    finally:

        conn.close()
