"""Price action analysis agent."""

from __future__ import annotations

import statistics
from fin_guard.graph.state import FinGuardState


def price_agent(state: FinGuardState) -> dict:
    """Score realized volatility and abrupt price movement."""
    returns = [float(row.get("return", 0.0)) for row in state.get("market_data", [])]
    if not returns:
        return {"volatility_score": 0.0, "price_anomaly_score": 0.0}
    volatility = min(100.0, statistics.pstdev(returns) * 1800)
    worst_move = abs(min(returns)) if min(returns) < 0 else max(returns)
    anomaly = min(100.0, worst_move * 900)
    return {"volatility_score": round(volatility, 2), "price_anomaly_score": round(anomaly, 2)}
