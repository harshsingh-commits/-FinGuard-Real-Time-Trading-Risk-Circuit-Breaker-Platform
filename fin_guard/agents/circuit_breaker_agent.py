"""Circuit-breaker governance agent."""

from fin_guard.backend.risk import calculate_risk
from fin_guard.backend.config import settings
from fin_guard.graph.state import FinGuardState


def circuit_breaker_agent(state: FinGuardState) -> dict:
    decision = calculate_risk(state.get("volatility_score", 0), state.get("liquidity_score", 0), state.get("sentiment_score", 0), state.get("daily_drawdown", 0), state.get("exposure_score", 0))
    volatility_limit = float(state.get("dynamic_volatility_limit", settings.risk_limits.max_volatility_score))
    triggered = decision.score > settings.risk_limits.critical_risk_score or state.get("daily_drawdown", 0) > settings.risk_limits.max_drawdown_pct or state.get("volatility_score", 0) > volatility_limit
    reason = decision.reason or ("governance threshold breached" if triggered else "")
    return {"circuit_breaker_triggered": triggered, "circuit_breaker_reason": reason, "execution_paused": triggered, "alerts": [f"CIRCUIT BREAKER: {reason}"] if triggered else []}
