"""Tests for SQLite probe history persistence."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import config
from app.probes import ProbeResult, ProbeState
from app.store import ProbeHistoryStore, RETENTION_DAYS


def _make_targets():
    return [
        {
            "id": "claude-flagship",
            "provider_id": "claude",
            "name": "Claude",
            "tier": "flagship",
            "model": "claude-opus-4",
            "probe": None,
            "has_key": True,
        },
        {
            "id": "gpt-flagship",
            "provider_id": "gpt",
            "name": "GPT",
            "tier": "flagship",
            "model": "gpt-5",
            "probe": None,
            "has_key": True,
        },
    ]


def _result(latency_ms: int) -> ProbeResult:
    return ProbeResult(
        available=True,
        latency_ms=latency_ms,
        qa_correct=True,
        token_rate=80,
        http_status=200,
    )


class TestProbeHistoryStore:
    def test_init_creates_table(self, tmp_path):
        db = tmp_path / "watchtower.db"
        store = ProbeHistoryStore(db)
        store.init()
        assert db.exists()
        assert store.enabled

    def test_record_and_load(self, tmp_path):
        targets = _make_targets()
        store = ProbeHistoryStore(tmp_path / "watchtower.db")
        store.init()
        state = ProbeState(targets, history_store=store)
        for i in range(3):
            state.apply(targets[0], _result(100 + i * 10))

        loaded = store.load_history(targets)
        assert len(loaded["claude-flagship"]) == 3
        assert loaded["claude-flagship"][0]["ms"] == 100
        assert loaded["claude-flagship"][-1]["ms"] == 120
        assert loaded["gpt-flagship"] == []

    def test_history_survives_restart(self, tmp_path):
        """Simulate backend restart: new ProbeState reads prior sqlite rows."""
        db = tmp_path / "watchtower.db"
        targets = _make_targets()

        store1 = ProbeHistoryStore(db)
        store1.init()
        state1 = ProbeState(targets, history_store=store1)
        for i in range(5):
            state1.apply(targets[0], _result(200 + i))

        store2 = ProbeHistoryStore(db)
        store2.init()
        loaded = store2.load_history(targets)
        state2 = ProbeState(targets, history_store=store2, initial_history=loaded)

        claude = next(
            p for p in state2.snapshot()["providers"] if p["id"] == "claude-flagship"
        )
        assert len(claude["latencyHistory"]) == 5
        assert claude["latencyHistory"][0]["ms"] == 200
        assert claude["latencyHistory"][-1]["ms"] == 204

    def test_load_respects_history_len(self, tmp_path):
        targets = _make_targets()
        store = ProbeHistoryStore(tmp_path / "watchtower.db")
        store.init()
        state = ProbeState(targets, history_store=store)
        for i in range(config.HISTORY_LEN + 5):
            state.apply(targets[0], _result(100))

        loaded = store.load_history(targets)
        assert len(loaded["claude-flagship"]) == config.HISTORY_LEN

    def test_cleanup_drops_old_rows(self, tmp_path):
        db = tmp_path / "watchtower.db"
        store = ProbeHistoryStore(db)
        store.init()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS + 1)
        ).isoformat()
        with store._connect() as conn:
            conn.execute(
                """INSERT INTO probe_history
                   (timestamp, provider, tier, status, health_score,
                    latency_ms, token_rate, qa_pass)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (old_ts, "claude", "flagship", "operational", 100, 50, 80, 1),
            )
            conn.commit()

        store.cleanup_old()
        loaded = store.load_history(_make_targets())
        assert loaded["claude-flagship"] == []

    def test_init_failure_degrades_gracefully(self, tmp_path, monkeypatch):
        db = tmp_path / "watchtower.db"
        store = ProbeHistoryStore(db)

        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "mkdir", boom)
        store.init()
        assert not store.enabled
        # Writes/loads are no-ops, probes still work in memory.
        targets = _make_targets()
        state = ProbeState(targets, history_store=store)
        state.apply(targets[0], _result(300))
        assert len(state.snapshot()["providers"][0]["latencyHistory"]) == 1

    def test_write_failure_does_not_block_apply(self, tmp_path, monkeypatch):
        targets = _make_targets()
        store = ProbeHistoryStore(tmp_path / "watchtower.db")
        store.init()

        def boom(*_a, **_k):
            raise sqlite3.Error("locked")

        monkeypatch.setattr(store, "_connect", boom)
        state = ProbeState(targets, history_store=store)
        state.apply(targets[0], _result(400))
        claude = next(
            p for p in state.snapshot()["providers"] if p["id"] == "claude-flagship"
        )
        assert len(claude["latencyHistory"]) == 1
        assert claude["latencyMs"] == 400
