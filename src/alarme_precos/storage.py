"""Persistência em SQLite: cache de buscas, log de uso, monitores e alertas."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    provider  TEXT NOT NULL,
    route     TEXT NOT NULL,
    cached    INTEGER NOT NULL,
    success   INTEGER NOT NULL,
    error     TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_log (ts);

CREATE TABLE IF NOT EXISTS monitors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    origin         TEXT NOT NULL,
    destination    TEXT NOT NULL,
    outbound_date  TEXT NOT NULL,
    target_price   REAL NOT NULL,
    interval_hours REAL NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1,
    last_checked   REAL,
    last_price     REAL,
    last_error     TEXT,
    created_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors (id),
    ts         REAL NOT NULL,
    price      REAL NOT NULL,
    airline    TEXT,
    message    TEXT NOT NULL
);
"""


class Database:
    """Conexão SQLite compartilhada entre a UI e a thread do monitor."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid or 0

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: tuple | dict = ()) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None

    # --- cache -------------------------------------------------------------
    def cache_get(self, key: str, ttl_seconds: float) -> dict | None:
        if ttl_seconds <= 0:
            return None
        rows = self.query("SELECT payload, created_at FROM cache WHERE key = ?", (key,))
        if not rows or time.time() - rows[0]["created_at"] > ttl_seconds:
            return None
        return json.loads(rows[0]["payload"])

    def cache_set(self, key: str, payload: dict) -> None:
        self.execute(
            "INSERT OR REPLACE INTO cache (key, payload, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload), time.time()),
        )

    # --- uso ---------------------------------------------------------------
    def log_usage(
        self, provider: str, route: str, cached: bool, success: bool, error: str | None = None
    ) -> None:
        self.execute(
            "INSERT INTO usage_log (ts, provider, route, cached, success, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), provider, route, int(cached), int(success), error),
        )

    def count_api_calls(self, since_ts: float, provider: str = "serpapi") -> int:
        """Buscas reais bem-sucedidas (as que o SerpApi desconta da cota)."""
        return int(
            self.scalar(
                "SELECT COUNT(*) FROM usage_log "
                "WHERE provider = ? AND cached = 0 AND success = 1 AND ts >= ?",
                (provider, since_ts),
            )
            or 0
        )

    def count_cache_hits(self, since_ts: float, provider: str = "serpapi") -> int:
        return int(
            self.scalar(
                "SELECT COUNT(*) FROM usage_log WHERE provider = ? AND cached = 1 AND ts >= ?",
                (provider, since_ts),
            )
            or 0
        )
