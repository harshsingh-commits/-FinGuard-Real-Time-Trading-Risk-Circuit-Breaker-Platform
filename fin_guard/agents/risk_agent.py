"""Risk fusion agent."""

from fin_guard.backend.risk import calculate_risk
from fin_guard.backend.analytics import concentration_risk, correlation_risk, expected_shortfall, historical_var, portfolio_analytics, position_sizing_risk
from fin_guard.graph.state import FinGuardState


def risk_agent(state: FinGuardState) -> dict:
    """Calculate exposure and combine all upstream signals."""
    exposure = min(100.0, sum(abs(float(p.get("quantity", 0) * p.get("entry_price", 0))) for p in state.get("portfolio_positions", [])) / 1000)
    returns = [float(row.get("return", 0)) for row in state.get("market_data", [])]
    analytics = portfolio_analytics(returns)
    var = historical_var(returns)
    es = expected_shortfall(returns)
    concentration = concentration_risk(state.get("portfolio_positions", []))
    sizing = position_sizing_risk(state.get("portfolio_positions", []))
    correlation = correlation_risk({"market": returns, "proxy": returns})
    analytics_risk = min(100.0, var * 500 + es * 300 + concentration * 0.2 + sizing * 0.2 + correlation * 0.2)
    decision = calculate_risk(state.get("volatility_score", 0), state.get("liquidity_score", 0), max(state.get("sentiment_score", 0), analytics_risk), state.get("daily_drawdown", 0), exposure)
    return {"exposure_score": round(exposure, 2), "risk_score": decision.score, "risk_level": decision.level, "var_95": var, "expected_shortfall": es, "concentration_risk": concentration, "position_sizing_risk": sizing, "correlation_risk": correlation, **analytics}
