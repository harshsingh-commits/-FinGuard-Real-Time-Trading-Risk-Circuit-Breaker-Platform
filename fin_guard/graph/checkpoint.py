"""Durable LangGraph checkpoint helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


_connections: list[sqlite3.Connection] = []


def durable_checkpoint(path: str | Path) -> SqliteSaver:
    """Create a SQLite-backed checkpointer whose connection lives with the process."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    _connections.append(connection)
    return saver


def memory_checkpoint():
    """Compatibility helper for isolated unit tests."""
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
