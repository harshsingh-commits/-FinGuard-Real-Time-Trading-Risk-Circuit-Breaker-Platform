"""Small SQLite repository for incidents, snapshots, checkpoints, and approvals."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fin_guard.backend.structured_logging import get_logger


logger = get_logger("finguard.storage")


class Storage:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, timestamp TEXT, reason TEXT, risk_score REAL, status TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS risk_snapshots (id INTEGER PRIMARY KEY, timestamp TEXT, risk_score REAL, risk_level TEXT, drawdown REAL, volatility REAL, sentiment REAL, payload TEXT);
                CREATE TABLE IF NOT EXISTS checkpoints (id INTEGER PRIMARY KEY, thread_id TEXT, timestamp TEXT, state TEXT);
                CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, timestamp TEXT, event TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY, timestamp TEXT, decision TEXT, thread_id TEXT);
                CREATE TABLE IF NOT EXISTS state_transitions (id INTEGER PRIMARY KEY, thread_id TEXT, node TEXT, timestamp TEXT, state TEXT, diff TEXT);
            """)

    def save_state(self, state: dict[str, Any], thread_id: str = "default") -> None:
        timestamp = state.get("timestamp", datetime.now(timezone.utc).isoformat())
        payload = json.dumps(state, default=str)
        with self.connect() as db:
            db.execute("INSERT INTO checkpoints(thread_id,timestamp,state) VALUES(?,?,?)", (thread_id, timestamp, payload))
            db.execute("INSERT INTO risk_snapshots(timestamp,risk_score,risk_level,drawdown,volatility,sentiment,payload) VALUES(?,?,?,?,?,?,?)", (timestamp, state.get("risk_score", 0), state.get("risk_level", "Safe"), state.get("daily_drawdown", 0), state.get("volatility_score", 0), state.get("sentiment_score", 0), payload))
            for event in state.get("audit_log", []):
                db.execute("INSERT INTO audit_logs(timestamp,event,payload) VALUES(?,?,?)", (event.get("timestamp", timestamp), event.get("event", "state_transition"), json.dumps(event)))
            if state.get("circuit_breaker_triggered"):
                db.execute("INSERT INTO incidents(timestamp,reason,risk_score,status,payload) VALUES(?,?,?,?,?)", (timestamp, state.get("circuit_breaker_reason", "threshold breach"), state.get("risk_score", 0), "OPEN", payload))

    def save_transition(self, state: dict[str, Any], thread_id: str, node: str, diff: dict[str, Any] | None = None) -> None:
        timestamp = state.get("timestamp", datetime.now(timezone.utc).isoformat())
        with self.connect() as db:
            db.execute("INSERT INTO state_transitions(thread_id,node,timestamp,state,diff) VALUES(?,?,?,?,?)", (thread_id, node, timestamp, json.dumps(state, default=str), json.dumps(diff or {}, default=str)))
        logger.info("state_transition thread_id=%s node=%s", thread_id, node)

    def save_history(self, history: list[dict[str, Any]], thread_id: str) -> None:
        for item in history:
            self.save_transition(item.get("state", item), thread_id, item.get("node", "graph"), item.get("diff", {}))

    def list_rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {"incidents", "risk_snapshots", "checkpoints", "audit_logs", "approvals", "state_transitions"}
        if table not in allowed:
            raise ValueError("unsupported table")
        with self.connect() as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def get_incident(self, incident_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            return dict(row) if row else None

    def record_approval(self, decision: str, thread_id: str):
        with self.connect() as db:
            db.execute("INSERT INTO approvals(timestamp,decision,thread_id) VALUES(?,?,?)", (datetime.now(timezone.utc).isoformat(), decision, thread_id))
        logger.info("approval decision=%s thread_id=%s", decision, thread_id)
