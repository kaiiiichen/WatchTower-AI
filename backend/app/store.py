"""SQLite persistence for probe history — survives backend restarts.

Uses stdlib sqlite3 only. Any init/read/write failure degrades gracefully to
pure in-memory history without blocking the probe loop."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

log = logging.getLogger("watchtower.store")

RETENTION_DAYS = 7
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "watchtower.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS probe_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    tier TEXT NOT NULL,
    status TEXT NOT NULL,
    health_score INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    token_rate INTEGER NOT NULL,
    qa_pass INTEGER NOT NULL
)
"""


class ProbeHistoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def init(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(_CREATE_TABLE)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_probe_history_ts ON probe_history(timestamp)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_probe_history_provider_tier "
                    "ON probe_history(provider, tier, timestamp)"
                )
                conn.commit()
        except Exception:
            log.exception("probe history store init failed; using in-memory only")
            self._enabled = False

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    @staticmethod
    def _provider_key(target: dict) -> str:
        return target.get("provider_id") or target["id"].rsplit("-", 1)[0]

    def record(
        self,
        *,
        target: dict,
        timestamp: str,
        status: str,
        health_score: int,
        latency_ms: int,
        token_rate: int,
        qa_pass: bool,
    ) -> None:
        if not self._enabled:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO probe_history
                       (timestamp, provider, tier, status, health_score,
                        latency_ms, token_rate, qa_pass)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        timestamp,
                        self._provider_key(target),
                        target["tier"],
                        status,
                        health_score,
                        latency_ms,
                        token_rate,
                        1 if qa_pass else 0,
                    ),
                )
                conn.commit()
        except Exception:
            log.exception("probe history write failed")

    def load_history(self, targets: list[dict]) -> dict[str, list[dict]]:
        """Return {target_id: [{t, ms}, ...]} in chronological order."""
        empty = {t["id"]: [] for t in targets}
        if not self._enabled:
            return empty
        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            ).isoformat()
            loaded: dict[str, list[dict]] = {}
            with self._connect() as conn:
                for t in targets:
                    rows = conn.execute(
                        """SELECT timestamp, latency_ms FROM probe_history
                           WHERE provider = ? AND tier = ? AND timestamp >= ?
                           ORDER BY timestamp DESC LIMIT ?""",
                        (
                            self._provider_key(t),
                            t["tier"],
                            cutoff,
                            config.HISTORY_LEN,
                        ),
                    ).fetchall()
                    loaded[t["id"]] = [
                        {"t": ts, "ms": ms} for ts, ms in reversed(rows)
                    ]
            return loaded
        except Exception:
            log.exception("probe history load failed")
            return empty

    def cleanup_old(self) -> None:
        if not self._enabled:
            return
        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
            ).isoformat()
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM probe_history WHERE timestamp < ?", (cutoff,)
                )
                conn.commit()
        except Exception:
            log.exception("probe history cleanup failed")
