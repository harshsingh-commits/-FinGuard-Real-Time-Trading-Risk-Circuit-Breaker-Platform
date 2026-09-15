"""Order-book imbalance and liquidity analysis agent."""

from fin_guard.graph.state import FinGuardState


def orderbook_agent(state: FinGuardState) -> dict:
    """Convert bid/ask depth, spread, and large orders to risk scores."""
    book = state.get("orderbook_data", {})
    bids = sum(float(level[1]) for level in book.get("bids", []))
    asks = sum(float(level[1]) for level in book.get("asks", []))
    total = max(bids + asks, 1.0)
    imbalance = min(100.0, abs(bids - asks) / total * 200)
    spread = float(book.get("spread_bps", 0))
    large_orders = float(book.get("large_orders", 0))
    liquidity = min(100.0, spread * 1.5 + large_orders * 15 + max(0, 100 - total / 5))
    return {"imbalance_score": round(imbalance, 2), "liquidity_score": round(liquidity, 2)}
