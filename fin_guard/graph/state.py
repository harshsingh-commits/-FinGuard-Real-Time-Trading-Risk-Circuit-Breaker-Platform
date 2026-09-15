"""Shared state contract passed through the LangGraph workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


class FinGuardState(TypedDict, total=False):
    market_data: list[dict[str, Any]]
    orderbook_data: dict[str, Any]
    news_data: list[str]
    portfolio_positions: list[dict[str, Any]]
    unrealized_pnl: float
    daily_drawdown: float
    volatility_score: float
    price_anomaly_score: float
    imbalance_score: float
    liquidity_score: float
    sentiment_score: float
    market_risk_score: float
    exposure_score: float
    risk_score: float
    risk_level: str
    circuit_breaker_triggered: bool
    circuit_breaker_reason: str
    human_approval: str | None
    execution_paused: bool
    audit_log: list[dict[str, Any]]
    alerts: list[str]
    timestamp: str
    scenario: str
    market_regime: str
    regime_confidence: float
    var_95: float
    expected_shortfall: float
    concentration_risk: float
    position_sizing_risk: float
    correlation_risk: float
    market_impact_score: float
    news_events: list[dict[str, Any]]
    daily_pnl: list[float]
    equity_curve: list[float]
    drawdown_curve: list[float]
    sharpe_ratio: float
    sortino_ratio: float
    realized_pnl: float
    margin_used: float
    session_equity: float
    trades: list[dict[str, Any]]
    lifecycle_events: list[dict[str, Any]]
    event_source: str


def initial_state(**overrides: Any) -> FinGuardState:
    """Create a complete state suitable for a graph invocation."""
    state: FinGuardState = {
        "market_data": [], "orderbook_data": {}, "news_data": [],
        "portfolio_positions": [], "unrealized_pnl": 0.0,
        "daily_drawdown": 0.0, "volatility_score": 0.0,
        "price_anomaly_score": 0.0, "imbalance_score": 0.0,
        "liquidity_score": 0.0, "sentiment_score": 0.0,
        "market_risk_score": 0.0, "exposure_score": 0.0,
        "risk_score": 0.0, "risk_level": "Safe",
        "circuit_breaker_triggered": False, "circuit_breaker_reason": "",
        "human_approval": None, "execution_paused": False,
        "audit_log": [], "alerts": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scenario": "normal",
        "market_regime": "Sideways Market", "regime_confidence": 0.0,
        "var_95": 0.0, "expected_shortfall": 0.0,
        "concentration_risk": 0.0, "position_sizing_risk": 0.0,
        "correlation_risk": 0.0, "market_impact_score": 0.0,
        "news_events": [], "daily_pnl": [], "equity_curve": [],
        "drawdown_curve": [], "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
        "realized_pnl": 0.0, "margin_used": 0.0, "session_equity": 100000.0,
        "trades": [], "lifecycle_events": [], "event_source": "simulation",
    }
    state.update(overrides)
    return state
