import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fin_guard.agents.news_agent import news_agent
from fin_guard.agents.orderbook_agent import orderbook_agent
from fin_guard.agents.price_agent import price_agent
from fin_guard.backend.simulation import generate_market, generate_orderbook, scenario_news
from fin_guard.graph.state import initial_state


def test_agents_detect_flash_crash_signals():
    state = initial_state(market_data=generate_market("flash_crash"), orderbook_data=generate_orderbook("flash_crash"), news_data=scenario_news("flash_crash"))
    assert price_agent(state)["price_anomaly_score"] > 20
    assert orderbook_agent(state)["liquidity_score"] > 20
    assert news_agent(state)["sentiment_score"] > 50
