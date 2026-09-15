"""Real-time Binance feed with bounded async streaming and YFinance fallback."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fin_guard.backend.market_data import fetch_prices


BINANCE_SYMBOLS = {"BTCUSDT": "btcusdt", "ETHUSDT": "ethusdt", "NIFTY": "btcusdt"}


class BinanceMarketFeed:
    def __init__(self, symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "NIFTY"), endpoint: str = "wss://stream.binance.com:9443/stream"):
        self.symbols = symbols
        self.endpoint = endpoint

    @property
    def stream_url(self) -> str:
        streams = "/".join(f"{BINANCE_SYMBOLS.get(symbol, symbol.lower())}@ticker" for symbol in self.symbols)
        return f"{self.endpoint}?streams={streams}"

    async def stream(self, seconds: int = 1) -> list[dict[str, Any]]:
        import websockets
        ticks = []
        async with websockets.connect(self.stream_url, open_timeout=2) as socket:
            deadline = asyncio.get_running_loop().time() + seconds
            while asyncio.get_running_loop().time() < deadline:
                payload = json.loads(await asyncio.wait_for(socket.recv(), timeout=2))
                data = payload.get("data", payload)
                ticks.append({"timestamp": datetime.now(timezone.utc).isoformat(), "symbol": data.get("s"), "price": float(data.get("c", 0)), "source": "binance"})
        return ticks


async def get_live_ticks(seconds: int = 1) -> list[dict[str, Any]]:
    """Return exchange ticks, falling back to YFinance-compatible prices."""
    try:
        return await BinanceMarketFeed().stream(seconds)
    except Exception:
        prices = await fetch_prices("BTC-USD", "1d")
        return [{**row, "source": "yfinance"} for row in prices[-3:]]