"""Human-in-the-loop review node."""

from langgraph.types import interrupt
from fin_guard.graph.state import FinGuardState


def human_review_agent(state: FinGuardState) -> dict:
    """Pause a triggered workflow until an operator chooses an action."""
    if not state.get("circuit_breaker_triggered") or state.get("human_approval"):
        return {}
    decision = interrupt({"type": "risk_approval", "risk_score": state.get("risk_score", 0), "reason": state.get("circuit_breaker_reason", "")})
    decision = str(decision).upper()
    updates = {"human_approval": decision, "execution_paused": decision != "APPROVE"}
    if decision == "FORCE CLOSE POSITIONS":
        updates["portfolio_positions"] = [{**position, "quantity": 0, "status": "FORCE_CLOSED"} for position in state.get("portfolio_positions", [])]
    return updates
