"""LangGraph workflow for FinGuard's parallel risk analysis."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from fin_guard.agents.audit_agent import audit_agent
from fin_guard.agents.circuit_breaker_agent import circuit_breaker_agent
from fin_guard.agents.human_review_agent import human_review_agent
from fin_guard.agents.news_agent import news_agent
from fin_guard.agents.regime_agent import regime_agent
from fin_guard.agents.orderbook_agent import orderbook_agent
from fin_guard.agents.price_agent import price_agent
from fin_guard.agents.risk_agent import risk_agent
from fin_guard.backend.config import settings
from fin_guard.backend.portfolio_lifecycle import lifecycle_agent
from fin_guard.graph.checkpoint import durable_checkpoint
from fin_guard.graph.state import FinGuardState


def fan_out(state: FinGuardState) -> list[Send]:
    return [Send("price_agent", state), Send("orderbook_agent", state), Send("news_agent", state), Send("regime_agent", state), Send("lifecycle_agent", state)]


def route_review(state: FinGuardState) -> str:
    return "human_review" if state.get("circuit_breaker_triggered") and not state.get("human_approval") else "audit"


def build_graph(checkpointer=None):
    graph = StateGraph(FinGuardState)
    graph.add_node("price_agent", price_agent)
    graph.add_node("orderbook_agent", orderbook_agent)
    graph.add_node("news_agent", news_agent)
    graph.add_node("regime_agent", regime_agent)
    graph.add_node("lifecycle_agent", lifecycle_agent)
    graph.add_node("risk_agent", risk_agent)
    graph.add_node("circuit_breaker", circuit_breaker_agent)
    graph.add_node("human_review", human_review_agent)
    graph.add_node("audit", audit_agent)
    graph.add_conditional_edges(START, fan_out, ["price_agent", "orderbook_agent", "news_agent", "regime_agent", "lifecycle_agent"])
    for name in ("price_agent", "orderbook_agent", "news_agent", "regime_agent", "lifecycle_agent"):
        graph.add_edge(name, "risk_agent")
    graph.add_edge("risk_agent", "circuit_breaker")
    graph.add_conditional_edges("circuit_breaker", route_review, {"human_review": "human_review", "audit": "audit"})
    graph.add_edge("human_review", "audit")
    graph.add_edge("audit", END)
    return graph.compile(checkpointer=checkpointer or durable_checkpoint(settings.database_path.with_name("graph_checkpoints.db")))


workflow = build_graph()
