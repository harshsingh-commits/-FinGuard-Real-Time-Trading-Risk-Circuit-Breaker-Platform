import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from fin_guard.backend.simulation import POSITIONS, generate_market, generate_orderbook, scenario_news
from fin_guard.graph.state import initial_state
from fin_guard.graph.workflow import workflow


def test_normal_workflow_audits_transition():
    state = initial_state(market_data=generate_market(), orderbook_data=generate_orderbook(), news_data=scenario_news(), portfolio_positions=POSITIONS)
    result = workflow.invoke(state, config={"configurable": {"thread_id": "test-normal"}})
    assert result["risk_level"] in {"Safe", "Monitor", "Warning"}
    assert result["audit_log"]
