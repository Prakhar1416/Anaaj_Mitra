import sqlite3
from pathlib import Path

from backend.common import utcnow_iso
from backend.config import Settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS hamlets (
    hamlet_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    nutrition_priority INTEGER NOT NULL DEFAULT 0,
    priority_reason TEXT,
    priority_reported_by TEXT,
    priority_reported_at TEXT,
    priority_updated_at TEXT,
    last_event_id TEXT
);

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fill_percent INTEGER NOT NULL,
    capacity_kg REAL NOT NULL,
    available_stock_kg REAL NOT NULL,
    grain_type TEXT NOT NULL,
    stock_source TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS health_reports (
    report_id TEXT PRIMARY KEY,
    hamlet_id TEXT NOT NULL,
    nutrition_priority INTEGER NOT NULL,
    reason TEXT,
    reported_by TEXT,
    reported_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    event_id TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (hamlet_id) REFERENCES hamlets(hamlet_id)
);

CREATE TABLE IF NOT EXISTS health_priority_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    hamlet_id TEXT NOT NULL,
    nutrition_priority INTEGER NOT NULL,
    source TEXT NOT NULL,
    reason TEXT,
    reported_by TEXT,
    report_id TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (hamlet_id) REFERENCES hamlets(hamlet_id)
);

CREATE TABLE IF NOT EXISTS logistics_decisions (
    decision_id TEXT PRIMARY KEY,
    event_id TEXT,
    hamlet_id TEXT NOT NULL,
    warehouse_id TEXT,
    decision TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    stock_available INTEGER NOT NULL,
    feasible INTEGER NOT NULL,
    nutrition_priority INTEGER NOT NULL,
    spoilage_risk TEXT,
    delivery_completed INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (hamlet_id) REFERENCES hamlets(hamlet_id)
);

CREATE TABLE IF NOT EXISTS agent_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_id TEXT,
    hamlet_id TEXT,
    warehouse_id TEXT,
    input_summary TEXT NOT NULL,
    result TEXT NOT NULL,
    status TEXT NOT NULL,
    error_detail TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stream_state (
    stream TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (stream, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_events_hamlet
    ON health_priority_events (hamlet_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_hamlet
    ON logistics_decisions (hamlet_id, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_hamlet
    ON agent_logs (hamlet_id, log_id);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def display_name(entity_id: str) -> str:
    return entity_id.replace("-", " ").replace("_", " ").title()


def initialize_database(settings: Settings) -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = utcnow_iso()
    connection = connect(settings.database_path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        for hamlet_id in settings.hamlet_ids:
            connection.execute(
                """
                INSERT OR IGNORE INTO hamlets (hamlet_id, name, nutrition_priority)
                VALUES (?, ?, 0)
                """,
                (hamlet_id, display_name(hamlet_id)),
            )
        for warehouse_id in settings.warehouse_ids:
            connection.execute(
                """
                INSERT OR IGNORE INTO warehouses (
                    warehouse_id, name, fill_percent, capacity_kg,
                    available_stock_kg, grain_type, stock_source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    display_name(warehouse_id),
                    settings.default_warehouse_fill_percent,
                    settings.warehouse_capacity_kg,
                    settings.simulated_stock_kg,
                    settings.grain_type,
                    settings.stock_source,
                    timestamp,
                ),
            )
    finally:
        connection.close()
