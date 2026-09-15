"""Simulated trading-day position lifecycle and accounting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def mark_to_market(positions: list[dict], prices: dict[str, float]) -> tuple[float, float, list[dict]]:
    unrealized = 0.0
    margin = 0.0
    enriched = []
    for position in positions:
        symbol = position["symbol"]
        quantity = float(position.get("quantity", 0))
        entry = float(position.get("entry_price", 0))
        current = float(prices.get(symbol, entry))
        pnl = (current - entry) * quantity if position.get("side", "LONG") == "LONG" else (entry - current) * quantity
        notional = abs(current * quantity)
        unrealized += pnl
        margin += notional * 0.5
        enriched.append({**position, "current_price": current, "unrealized_pnl": round(pnl, 2), "notional": round(notional, 2), "status": position.get("status", "OPEN")})
    return round(unrealized, 2), round(margin, 2), enriched


def close_position(position: dict, price: float, timestamp: str | None = None) -> tuple[dict, dict]:
    quantity = float(position.get("quantity", 0))
    entry = float(position.get("entry_price", 0))
    pnl = (price - entry) * quantity if position.get("side", "LONG") == "LONG" else (entry - price) * quantity
    trade = {"symbol": position["symbol"], "quantity": quantity, "entry_price": entry, "exit_price": price, "realized_pnl": round(pnl, 2), "timestamp": timestamp or datetime.now(timezone.utc).isoformat()}
    return {**position, "quantity": 0, "status": "CLOSED", "exit_price": price, "realized_pnl": round(pnl, 2)}, trade


def lifecycle_agent(state: dict[str, Any]) -> dict[str, Any]:
    prices = {row.get("symbol", "SPY"): float(row.get("price", 0)) for row in state.get("market_data", [])}
    unrealized, margin, positions = mark_to_market(state.get("portfolio_positions", []), prices)
    close_symbols = set(state.get("close_positions", []))
    trades = list(state.get("trades", []))
    for index, position in enumerate(positions):
        if position["symbol"] in close_symbols and position.get("quantity", 0):
            closed, trade = close_position(position, position["current_price"])
            positions[index] = closed
            trades.append(trade)
    realized = round(sum(float(trade.get("realized_pnl", 0)) for trade in trades), 2)
    equity = round(float(state.get("session_equity", 100000.0)) + realized + unrealized, 2)
    return {"portfolio_positions": positions, "unrealized_pnl": unrealized, "realized_pnl": realized, "margin_used": margin, "session_equity": equity, "trades": trades, "lifecycle_events": [*state.get("lifecycle_events", []), {"event": "mark_to_market", "timestamp": datetime.now(timezone.utc).isoformat(), "equity": equity}]}
