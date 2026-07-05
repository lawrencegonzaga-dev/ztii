import sqlite3
from pathlib import Path

# ---------------------------------------
# Database location
# ---------------------------------------
db_folder = Path("database")
db_folder.mkdir(exist_ok=True)

DATABASE_PATH = db_folder / "ztii.db"


# ---------------------------------------
# Connection
# ---------------------------------------
def get_connection():
    """Create a new SQLite connection"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------
# Initialize database
# ---------------------------------------
def init_db():
    """Create all required tables"""

    conn = get_connection()
    cursor = conn.cursor()

    # =====================================================
    # Devices Table (LATEST STATE + AI OUTPUT)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        device_id TEXT PRIMARY KEY,
        temperature REAL,
        vibration REAL,
        status TEXT,
        health TEXT,
        risk TEXT,
        recommendation TEXT,
        registered_at TEXT
    )
    """)

    # =====================================================
    # Sensor History Table (RAW DATA ONLY)
    # =====================================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        temperature REAL,
        vibration REAL,
        recorded_at TEXT
    )
    """)

    conn.commit()
    conn.close()