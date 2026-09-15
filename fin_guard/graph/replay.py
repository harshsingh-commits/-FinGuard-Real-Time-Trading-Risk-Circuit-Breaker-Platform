"""Checkpoint replay and state-diff engine."""

from __future__ import annotations

import json
from typing import Any

from fin_guard.database.storage import Storage


def state_diff(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = set(previous) | set(current)
    return {key: {"before": previous.get(key), "after": current.get(key)} for key in sorted(keys) if previous.get(key) != current.get(key)}


class ReplayEngine:
    def __init__(self, storage: Storage):
        self.storage = storage

    def incident_ids(self) -> list[int]:
        return [int(row["id"]) for row in self.storage.list_rows("incidents")]

    def checkpoints(self, thread_id: str | None = None) -> list[dict]:
        rows = self.storage.list_rows("checkpoints", 1000)
        if not rows:
            rows = self.storage.list_rows("state_transitions", 1000)
            for row in rows:
                row["state"] = row.pop("state")
        rows.reverse()
        if thread_id:
            rows = [row for row in rows if row["thread_id"] == thread_id]
        for row in rows:
            row["state"] = json.loads(row["state"])
        return rows

    def replay(self, thread_id: str) -> list[dict]:
        rows = self.checkpoints(thread_id)
        previous = {}
        for row in rows:
            row["diff"] = state_diff(previous, row["state"])
            previous = row["state"]
        return rows