"""Portfolio and tail-risk analytics with deterministic, dependency-light math."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable


def historical_var(returns: Iterable[float], confidence: float = 0.95) -> float:
    values = sorted(float(value) for value in returns)
    if not values:
        return 0.0
    index = max(0, min(len(values) - 1, math.ceil((1 - confidence) * len(values)) - 1))
    return round(max(0.0, -values[index]), 6)


def expected_shortfall(returns: Iterable[float], confidence: float = 0.95) -> float:
    values = sorted(float(value) for value in returns)
    if not values:
        return 0.0
    cutoff = max(1, math.ceil((1 - confidence) * len(values)))
    return round(max(0.0, -statistics.fmean(values[:cutoff])), 6)


def concentration_risk(positions: list[dict]) -> float:
    notionals = [abs(float(item.get("quantity", 0)) * float(item.get("entry_price", 0))) for item in positions]
    total = sum(notionals)
    return round(max((value / total for value in notionals), default=0.0) * 100, 2) if total else 0.0


def position_sizing_risk(positions: list[dict], equity: float = 100_000.0) -> float:
    total = sum(abs(float(item.get("quantity", 0)) * float(item.get("entry_price", 0))) for item in positions)
    return round(min(100.0, total / max(equity, 1.0) * 100), 2)


def correlation_risk(returns_by_asset: dict[str, list[float]]) -> float:
    series = list(returns_by_asset.values())
    if len(series) < 2:
        return 0.0
    aligned = list(zip(*series))
    average = [statistics.fmean(row) for row in aligned]
    dispersion = statistics.pstdev(average) if len(average) > 1 else 0.0
    return round(min(100.0, dispersion * 10_000), 2)


def portfolio_analytics(returns: Iterable[float], starting_equity: float = 100_000.0) -> dict:
    values = [float(value) for value in returns]
    daily_pnl = [round(starting_equity * value, 2) for value in values]
    equity = []
    current = starting_equity
    peak = starting_equity
    drawdowns = []
    for pnl in daily_pnl:
        current += pnl
        peak = max(peak, current)
        equity.append(round(current, 2))
        drawdowns.append(round((peak - current) / peak * 100, 4))
    mean = statistics.fmean(values) if values else 0.0
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    downside = [value for value in values if value < 0]
    downside_std = statistics.pstdev(downside) if len(downside) > 1 else 0.0
    return {"daily_pnl": daily_pnl, "equity_curve": equity, "drawdown_curve": drawdowns, "sharpe_ratio": round(mean / std * math.sqrt(252), 4) if std else 0.0, "sortino_ratio": round(mean / downside_std * math.sqrt(252), 4) if downside_std else 0.0}