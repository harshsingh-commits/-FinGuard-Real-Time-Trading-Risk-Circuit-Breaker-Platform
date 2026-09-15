"""Async market-data adapter with WebSocket and YFinance fallback."""

from __future__ import annotations

import asyncio
from typing import Any

from fin_guard.backend.simulation import generate_market


async def websocket_stream(uri: str, seconds: int = 3) -> list[dict[str, Any]]:
    """Read JSON ticks from a WebSocket for a bounded interval."""
    import json
    import websockets
    ticks = []
    async with websockets.connect(uri) as socket:
        for _ in range(seconds):
            ticks.append(json.loads(await asyncio.wait_for(socket.recv(), timeout=2)))
    return ticks


async def fetch_prices(symbol: str = "SPY", period: str = "1d") -> list[dict[str, Any]]:
    """Use YFinance when available, otherwise return a safe local sample."""
    try:
        import yfinance as yf
        frame = await asyncio.to_thread(yf.download, symbol, period=period, progress=False, auto_adjust=False)
        if frame.empty:
            raise ValueError("empty market response")
        prices = frame["Close"].iloc[:, 0] if getattr(frame["Close"], "ndim", 1) > 1 else frame["Close"]
        return [{"timestamp": str(index), "symbol": symbol, "price": float(value)} for index, value in prices.items()]
    except Exception:
        return generate_market("normal")
