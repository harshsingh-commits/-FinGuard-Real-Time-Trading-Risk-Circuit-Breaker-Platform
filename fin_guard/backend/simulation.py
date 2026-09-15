"""Deterministic market scenarios used by the demo and API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random


POSITIONS = [
    {"symbol": "AAPL", "quantity": 180, "entry_price": 190.0, "side": "LONG"},
    {"symbol": "NVDA", "quantity": 60, "entry_price": 118.0, "side": "LONG"},
    {"symbol": "TSLA", "quantity": 75, "entry_price": 245.0, "side": "LONG"},
]


def generate_market(scenario: str = "normal", points: int = 30, seed: int = 7) -> list[dict]:
    """Generate prices, returns, and timestamps for a named market regime."""
    rng = random.Random(seed)
    scenario = scenario.lower()
    price = 100.0
    drift = {"bull": 0.002, "bear": -0.002, "normal": 0.0}.get(scenario, 0.0)
    volatility = 0.004 if scenario not in {"high_volatility", "flash_crash"} else 0.03
    values = []
    start = datetime.now(timezone.utc) - timedelta(seconds=points)
    for index in range(points):
        change = drift + rng.gauss(0, volatility)
        if scenario == "flash_crash" and index >= points - 5:
            change = -0.03
        price *= 1 + change
        values.append({"timestamp": (start + timedelta(seconds=index)).isoformat(), "symbol": "SPY", "price": round(price, 4), "return": change})
    return values


def generate_orderbook(scenario: str = "normal") -> dict:
    """Generate a compact orderbook snapshot."""
    if scenario == "flash_crash":
        return {"bids": [[97.0, 20], [96.5, 10]], "asks": [[100.0, 500], [101.0, 350]], "spread_bps": 42, "large_orders": 2}
    return {"bids": [[99.9, 120], [99.8, 90]], "asks": [[100.1, 110], [100.2, 95]], "spread_bps": 4, "large_orders": 0}


def scenario_news(scenario: str = "normal") -> list[str]:
    """Return headlines used by the sentiment abstraction."""
    if scenario == "flash_crash":
        return ["Emergency liquidity warning triggers broad market selloff", "Regulators investigate sudden volatility spike"]
    if scenario == "bear":
        return ["Growth outlook weakens as macro uncertainty rises"]
    if scenario == "bull":
        return ["Earnings beat expectations as demand accelerates"]
    return ["Markets trade steadily ahead of scheduled economic data"]
