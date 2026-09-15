"""Pure risk fusion and circuit-breaker decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    score: float
    level: str
    triggered: bool
    reason: str


def risk_level(score: float) -> str:
    if score <= 30:
        return "Safe"
    if score <= 60:
        return "Monitor"
    if score <= 80:
        return "Warning"
    return "Critical"


def calculate_risk(volatility: float, liquidity: float, sentiment: float, drawdown: float, exposure: float) -> RiskDecision:
    """Fuse normalized factors into a 0-100 governance score."""
    score = round(min(100.0, max(0.0, volatility * 0.30 + liquidity * 0.20 + sentiment * 0.20 + min(drawdown * 5, 100) * 0.20 + exposure * 0.10)), 2)
    reason_parts = []
    if score > 80:
        reason_parts.append(f"risk score {score:.1f} > 80")
    if drawdown > 10:
        reason_parts.append(f"drawdown {drawdown:.1f}% > 10%")
    if volatility > 78:
        reason_parts.append(f"volatility {volatility:.1f} > threshold")
    return RiskDecision(score, risk_level(score), bool(reason_parts), "; ".join(reason_parts))
