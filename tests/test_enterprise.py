import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from fin_guard.agents.news_agent import extract_events, news_agent
from fin_guard.agents.regime_agent import regime_agent
from fin_guard.audit.report import export_audit_pdf, root_cause_summary
from fin_guard.backend.analytics import (correlation_risk, concentration_risk, expected_shortfall,
                                          historical_var, portfolio_analytics, position_sizing_risk)
from fin_guard.backend.market_feed import BinanceMarketFeed
from fin_guard.backend.event_stream import InMemoryEventBus, publish_market_event
from fin_guard.backend.portfolio_lifecycle import close_position, lifecycle_agent
from fin_guard.backend.simulation import POSITIONS, generate_market, generate_orderbook, scenario_news
from fin_guard.backend.structured_logging import JsonFormatter
from fin_guard.database.storage import Storage
from fin_guard.graph.replay import ReplayEngine, state_diff
from fin_guard.graph.state import initial_state
from fin_guard.graph.workflow import workflow
from langgraph.types import Command


@pytest.mark.parametrize("returns, expected", [([-0.1, -0.02, 0.01, 0.02], 0.1), ([], 0.0), ([-0.01, 0.0], 0.01)])
def test_var_calculation(returns, expected):
    assert historical_var(returns, 0.75) == expected


@pytest.mark.parametrize("returns", [[], [-0.1, -0.02, 0.01], [-0.05, -0.04, -0.03, 0.01]])
def test_expected_shortfall_is_nonnegative(returns):
    assert expected_shortfall(returns) >= 0


@pytest.mark.parametrize("positions", [([], 0.0), (POSITIONS, 57.33)])
def test_concentration_risk(positions):
    assert concentration_risk(positions[0]) == positions[1]


def test_position_size_and_correlation():
    assert position_sizing_risk(POSITIONS) > 0
    assert correlation_risk({"a": [0.01, 0.02], "b": [0.01, 0.02]}) >= 0


def test_portfolio_analytics_curves():
    result = portfolio_analytics([0.01, -0.02, 0.03])
    assert len(result["equity_curve"]) == 3
    assert len(result["drawdown_curve"]) == 3
    assert "sharpe_ratio" in result and "sortino_ratio" in result


@pytest.mark.parametrize("scenario, regime", [("bull", "Bull Market"), ("bear", "Bear Market"), ("normal", "Sideways Market"), ("high_volatility", "High Volatility Market")])
def test_regime_detection(scenario, regime):
    state = initial_state(market_data=generate_market(scenario))
    assert regime_agent(state)["market_regime"] == regime


def test_news_event_extraction():
    events = extract_events(["Emergency liquidity warning after geopolitical sanctions"])
    assert {"fear", "liquidity", "geopolitical"}.issubset(events[0]["categories"])
    assert news_agent(initial_state(news_data=scenario_news("flash_crash")))["market_impact_score"] > 0


def test_binance_stream_url_contains_required_symbols():
    url = BinanceMarketFeed().stream_url
    assert "btcusdt@ticker" in url and "ethusdt@ticker" in url


def test_market_feed_falls_back_to_yfinance(monkeypatch):
    import fin_guard.backend.market_feed as market_feed

    async def unavailable(self, seconds=1):
        raise OSError("socket unavailable")

    async def fallback(symbol, period):
        return [{"symbol": symbol, "price": 100.0}]

    monkeypatch.setattr(market_feed.BinanceMarketFeed, "stream", unavailable)
    monkeypatch.setattr(market_feed, "fetch_prices", fallback)
    ticks = asyncio.run(market_feed.get_live_ticks())
    assert ticks[0]["source"] == "yfinance"


def test_state_diff_only_returns_changes():
    assert state_diff({"risk_score": 10, "same": 1}, {"risk_score": 90, "same": 1}) == {"risk_score": {"before": 10, "after": 90}}


def test_replay_engine_reads_ordered_checkpoints(tmp_path):
    storage = Storage(tmp_path / "replay.db")
    storage.save_transition({"timestamp": "1", "risk_score": 10}, "thread", "price")
    storage.save_transition({"timestamp": "2", "risk_score": 90}, "thread", "risk")
    replay = ReplayEngine(storage).replay("thread")
    assert len(replay) == 2
    assert replay[1]["state"]["risk_score"] == 90


def test_audit_pdf_export():
    pdf = export_audit_pdf({"reason": "volatility", "risk_score": 91}, [{"timestamp": "now", "event": "breaker"}])
    assert pdf.startswith(b"%PDF")
    assert "volatility" in root_cause_summary({"reason": "volatility", "risk_score": 91})


def test_json_logging_formatter():
    import logging
    record = logging.LogRecord("test", logging.INFO, "", 0, "transition", (), None)
    assert json.loads(JsonFormatter().format(record))["event"] == "transition"


def test_interrupt_recovery_and_force_close():
    thread_id = "enterprise-interrupt"
    state = initial_state(scenario="flash_crash", market_data=generate_market("flash_crash"), orderbook_data=generate_orderbook("flash_crash"), news_data=scenario_news("flash_crash"), portfolio_positions=POSITIONS, daily_drawdown=12.0)
    from fin_guard.graph.workflow import build_graph
    fresh_workflow = build_graph()
    first = fresh_workflow.invoke(state, config={"configurable": {"thread_id": thread_id}})
    assert first.get("circuit_breaker_triggered") is True
    result = fresh_workflow.invoke(Command(resume="FORCE CLOSE POSITIONS"), config={"configurable": {"thread_id": thread_id}})
    assert result["human_approval"] == "FORCE CLOSE POSITIONS"
    assert all(position["quantity"] == 0 for position in result["portfolio_positions"])


def test_sqlite_checkpointer_reopens_state(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from fin_guard.graph.workflow import build_graph

    path = tmp_path / "durable-checkpoints.db"
    connection = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    graph = build_graph(saver)
    thread_id = "durable-reopen"
    graph.invoke(initial_state(), config={"configurable": {"thread_id": thread_id}})
    connection.close()
    reopened = sqlite3.connect(path, check_same_thread=False)
    reopened_saver = SqliteSaver(reopened)
    assert reopened_saver.get_tuple({"configurable": {"thread_id": thread_id}}) is not None
    reopened.close()


def test_structured_llm_provider_invokes_model():
    from fin_guard.agents.news_agent import LangChainNewsProvider, NewsAnalysis

    class StubModel:
        def invoke(self, prompt):
            assert "earnings" in prompt
            return NewsAnalysis(sentiment_score=64, market_impact_score=72, events=[])

    provider = object.__new__(LangChainNewsProvider)
    provider.model = StubModel()
    sentiment, impact = provider.score(["earnings beat expectations"])
    assert (sentiment, impact) == (64, 72)


def test_kafka_transport_has_local_fallback(monkeypatch):
    from fin_guard.backend.event_stream import KafkaEventBus

    async def unavailable(self, event):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(KafkaEventBus, "publish", unavailable)
    assert asyncio.run(publish_market_event({"symbol": "BTCUSDT"})) == "memory_fallback"


def test_trading_day_open_mark_close_lifecycle():
    position = {"symbol": "BTCUSDT", "quantity": 2, "entry_price": 100, "side": "LONG"}
    closed, trade = close_position(position, 110, "day-end")
    assert closed["status"] == "CLOSED" and trade["realized_pnl"] == 20
    result = lifecycle_agent(initial_state(portfolio_positions=[position], market_data=[{"symbol": "BTCUSDT", "price": 105}], close_positions=["BTCUSDT"]))
    assert result["realized_pnl"] == 10
    assert result["margin_used"] == 105
    assert result["portfolio_positions"][0]["status"] == "CLOSED"