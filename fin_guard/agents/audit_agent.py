"""Audit event generation agent."""

from datetime import datetime, timezone
from fin_guard.graph.state import FinGuardState


def audit_agent(state: FinGuardState) -> dict:
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "state_transition", "risk_score": state.get("risk_score", 0), "risk_level": state.get("risk_level", "Safe"), "circuit_breaker": state.get("circuit_breaker_triggered", False)}
    return {"audit_log": [*state.get("audit_log", []), event], "timestamp": event["timestamp"]}
