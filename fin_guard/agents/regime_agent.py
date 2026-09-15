"""Market regime classifier and dynamic risk threshold adjustment."""

from __future__ import annotations

import statistics

from fin_guard.graph.state import FinGuardState


REGIME_THRESHOLDS = {"Bull Market": 1.10, "Bear Market": 0.90, "Sideways Market": 1.0, "High Volatility Market": 0.75}


def regime_agent(state: FinGuardState) -> dict:
    prices = [float(row.get("price", 0)) for row in state.get("market_data", [])]
    returns = [float(row.get("return", 0)) for row in state.get("market_data", [])]
    if len(prices) < 2:
        regime, confidence = "Sideways Market", 0.0
    elif statistics.pstdev(returns) > 0.02:
        regime, confidence = "High Volatility Market", 0.9
    elif prices[-1] > prices[0] * 1.02:
        regime, confidence = "Bull Market", min(1.0, abs(prices[-1] / prices[0] - 1) * 10)
    elif prices[-1] < prices[0] * 0.98:
        regime, confidence = "Bear Market", min(1.0, abs(prices[-1] / prices[0] - 1) * 10)
    else:
        regime, confidence = "Sideways Market", 0.8
    return {"market_regime": regime, "regime_confidence": round(confidence, 3), "dynamic_volatility_limit": REGIME_THRESHOLDS[regime] * 78}