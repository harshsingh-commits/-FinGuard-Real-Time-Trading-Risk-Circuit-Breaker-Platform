"""FastAPI control plane for FinGuard."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response
from langgraph.types import Command

from fin_guard.backend.config import settings
from fin_guard.backend.simulation import POSITIONS, generate_market, generate_orderbook, scenario_news
from fin_guard.backend.market_feed import get_live_ticks
from fin_guard.backend.event_stream import KafkaEventBus, publish_market_event
from fin_guard.audit.report import export_audit_pdf
from fin_guard.database.models import ApprovalRequest, SimulationRequest, TradingDayRequest
from fin_guard.database.storage import Storage
from fin_guard.graph.state import initial_state
from fin_guard.graph.workflow import workflow
from fin_guard.graph.replay import ReplayEngine


app = FastAPI(title="FinGuard", version="1.0.0", description="Real-time algorithmic trading risk governance engine")
storage = Storage(settings.database_path)
replay_engine = ReplayEngine(storage)
event_bus = KafkaEventBus(settings.kafka_bootstrap_servers, settings.kafka_topic)
LATEST: dict = initial_state(portfolio_positions=POSITIONS)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "finguard"}


@app.get("/risk")
async def risk():
    return LATEST


@app.get("/positions")
async def positions():
    return {"positions": LATEST.get("portfolio_positions", POSITIONS)}


@app.get("/audit")
async def audit():
    return {"audit_logs": storage.list_rows("audit_logs"), "incidents": storage.list_rows("incidents")}


@app.get("/checkpoints")
async def checkpoints():
    return {"checkpoints": storage.list_rows("checkpoints")}


async def _run_scenario(scenario: str, thread_id: str = "default", close_positions: list[str] | None = None):
    global LATEST
    state = initial_state(scenario=scenario, market_data=generate_market(scenario), orderbook_data=generate_orderbook(scenario), news_data=scenario_news(scenario), portfolio_positions=POSITIONS, daily_drawdown=12.0 if scenario == "flash_crash" else 0.0, close_positions=close_positions or [])
    try:
        LATEST = workflow.invoke(state, config={"configurable": {"thread_id": thread_id}})
    except Exception as exc:
        if "interrupt" not in exc.__class__.__name__.lower():
            raise
        LATEST = workflow.get_state({"configurable": {"thread_id": thread_id}}).values
    storage.save_state(LATEST, thread_id)
    history = [{"state": snapshot.values, "node": f"checkpoint_{index}"} for index, snapshot in enumerate(workflow.get_state_history({"configurable": {"thread_id": thread_id}}))]
    storage.save_history(history, thread_id)
    return LATEST


@app.post("/simulate-market")
async def simulate_market(request: SimulationRequest):
    return await _run_scenario(request.scenario)


@app.post("/simulate-crash")
async def simulate_crash():
    return await _run_scenario("flash_crash")


@app.post("/simulate-trading-day")
async def simulate_trading_day(request: TradingDayRequest):
    return await _run_scenario(request.scenario, thread_id="trading-day", close_positions=request.close_positions)


@app.get("/feed")
async def live_feed():
    ticks = await get_live_ticks(1)
    sources = [await publish_market_event(tick, event_bus) for tick in ticks]
    return {"ticks": ticks, "event_bus": sources}


@app.get("/replay/{thread_id}")
async def replay(thread_id: str):
    return {"thread_id": thread_id, "steps": replay_engine.replay(thread_id)}


@app.get("/audit/report/{incident_id}")
async def audit_report(incident_id: int):
    incident = storage.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    timeline = storage.list_rows("audit_logs", 1000)
    return Response(content=export_audit_pdf(incident, timeline), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=finguard-incident-{incident_id}.pdf"})


async def _approve(request: ApprovalRequest):
    storage.record_approval(request.decision, request.thread_id)
    try:
        global LATEST
        LATEST = workflow.invoke(Command(resume=request.decision), config={"configurable": {"thread_id": request.thread_id}})
        storage.save_state(LATEST, request.thread_id)
        storage.save_history([{"state": snapshot.values, "node": "approval_resume"} for snapshot in workflow.get_state_history({"configurable": {"thread_id": request.thread_id}})], request.thread_id)
        return LATEST
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"No suspended approval for thread: {exc}") from exc


@app.post("/approve")
async def approve(request: ApprovalRequest):
    request.decision = "APPROVE"
    return await _approve(request)


@app.post("/reject")
async def reject(request: ApprovalRequest):
    request.decision = "REJECT"
    return await _approve(request)


@app.post("/force-close")
async def force_close(request: ApprovalRequest):
    request.decision = "FORCE CLOSE POSITIONS"
    return await _approve(request)
