"""FinGuard operator dashboard."""

import asyncio
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fin_guard.backend.simulation import POSITIONS, generate_market, generate_orderbook, scenario_news
from fin_guard.backend.market_feed import get_live_ticks
from fin_guard.database.storage import Storage
from fin_guard.graph.replay import ReplayEngine
from fin_guard.audit.report import export_audit_pdf
from fin_guard.graph.state import initial_state
from fin_guard.graph.workflow import workflow


st.set_page_config(page_title="FinGuard | Risk Control", page_icon=":material/shield:", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    :root { --ink: #10243e; --muted: #64748b; --line: #dbe5ee; --mint: #0f766e; --amber: #b45309; --danger: #b42318; }
    .stApp { background: #f4f7f9; color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(244,247,249,.88); }
    [data-testid="stSidebar"] { background: #10243e; }
    [data-testid="stSidebar"] * { color: #e8f0f6 !important; }
    [data-testid="stSidebar"] [role="combobox"] { color: #10243e !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] * { color: #10243e !important; }
    [role="listbox"] [role="option"] { color: #10243e !important; background: #ffffff !important; }
    [data-testid="stSidebar"] .stButton button { border-color: #4f6d86; background: #173451; }
    .brand { padding: 0.3rem 0 1.2rem; border-bottom: 1px solid #284763; margin-bottom: 1rem; }
    .brand-mark { color: #62d6c7; font: 700 1.35rem Georgia, serif; letter-spacing: .02em; }
    .brand-sub { color: #9db3c7; font-size: .75rem; margin-top: .2rem; }
    .eyebrow { color: #0f766e; font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .page-title { color: #10243e; font: 700 2.05rem Georgia, serif; margin: .15rem 0 .1rem; }
    .page-copy { color: #64748b; margin-bottom: 1.2rem; }
    .status-card { border: 1px solid var(--line); border-radius: 8px; padding: 1rem 1.1rem; background: #fff; min-height: 116px; }
    .status-label { color: var(--muted); font-size: .76rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
    .status-value { color: var(--ink); font-size: 1.65rem; font-weight: 750; margin-top: .45rem; }
    .status-note { color: var(--muted); font-size: .78rem; margin-top: .18rem; }
    .status-safe { color: var(--mint); }
    .status-alert { color: var(--danger); }
    .breaker { border-radius: 8px; padding: 1.35rem; color: #fff; min-height: 190px; }
    .breaker-off { background: #0f766e; }
    .breaker-on { background: #b42318; }
    .breaker-title { font-size: .78rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; opacity: .82; }
    .breaker-value { font: 700 2.4rem Georgia, serif; margin: 1rem 0 .45rem; }
    .breaker-copy { font-size: .86rem; opacity: .9; }
    .context-strip { display: flex; gap: .55rem; flex-wrap: wrap; margin: -.45rem 0 1.35rem; }
    .context-pill { background: #e8eff4; border: 1px solid #d5e1e9; border-radius: 999px; color: #496176; font-size: .75rem; padding: .34rem .65rem; }
    .context-pill strong { color: #10243e; }
    .feed-status { border-radius: 7px; font-size: .78rem; font-weight: 700; letter-spacing: .04em; margin: .35rem 0 .75rem; padding: .65rem .8rem; }
    .feed-live { background: #d9f3ee; border: 1px solid #a8ded4; color: #0f766e; }
    .feed-fallback { background: #fff4d6; border: 1px solid #f2d58a; color: #925d08; }
    .feed-waiting { background: #e8eff4; border: 1px solid #d5e1e9; color: #496176; }
    .section-note { color: #64748b; font-size: .82rem; margin: -.55rem 0 .75rem; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #fff; }
    .stButton button { border-radius: 6px; font-weight: 650; transition: transform .15s ease, box-shadow .15s ease; }
    .stButton button:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(16,36,62,.12); }
    div[data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: .85rem 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"Rs {value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def page_header(kicker: str, title: str, copy: str) -> None:
    st.markdown(f'<div class="eyebrow">{kicker}</div><div class="page-title">{title}</div><div class="page-copy">{copy}</div>', unsafe_allow_html=True)


def status_card(label: str, value: str, note: str = "", class_name: str = "") -> None:
    st.markdown(
        f'<div class="status-card"><div class="status-label">{label}</div><div class="status-value {class_name}">{value}</div><div class="status-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def context_strip(state: dict) -> None:
    breaker = "TRIGGERED" if state.get("circuit_breaker_triggered") else "OFF"
    breaker_class = "status-alert" if state.get("circuit_breaker_triggered") else "status-safe"
    st.markdown(
        f'<div class="context-strip"><span class="context-pill">Scenario <strong>{str(state.get("scenario", "normal")).replace("_", " ").title()}</strong></span><span class="context-pill">Regime <strong>{state.get("market_regime", "Sideways Market")}</strong></span><span class="context-pill">Breaker <strong class="{breaker_class}">{breaker}</strong></span><span class="context-pill">Source <strong>{str(state.get("event_source", "simulation")).title()}</strong></span></div>',
        unsafe_allow_html=True,
    )


def section_note(text: str) -> None:
    st.markdown(f'<div class="section-note">{text}</div>', unsafe_allow_html=True)


def feed_status(source: str, count: int) -> None:
    source_name = source.lower()
    if source_name == "binance":
        label, class_name, detail = "LIVE · BINANCE", "feed-live", "Exchange websocket connected"
    elif source_name == "yfinance":
        label, class_name, detail = "FALLBACK · YFINANCE", "feed-fallback", "Binance unavailable; fallback prices are active"
    else:
        label, class_name, detail = "WAITING", "feed-waiting", "Waiting for market observations"
    st.markdown(f'<div class="feed-status {class_name}">{label} <span style="font-weight:400">· {detail} · {count} observations</span></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">FIN / GUARD</div><div class="brand-sub">Portfolio risk command center</div></div>', unsafe_allow_html=True)
    scenario = st.selectbox("Market scenario", ["normal", "bull", "bear", "high_volatility", "flash_crash"])
    page = st.radio("Workspace", ["Executive Dashboard", "Risk Analytics", "Audit & Replay", "Operations Center", "Developer Diagnostics"], label_visibility="collapsed")
    run = st.button("Run selected scenario", icon=":material/play_arrow:", type="primary", width="stretch")
    crash_demo = st.button("Simulate flash crash", icon=":material/bolt:", width="stretch")
    st.caption("Simulation mode · data is non-execution")


@st.cache_data(ttl=15)
def run_analysis(selected: str):
    state = initial_state(scenario=selected, market_data=generate_market(selected), orderbook_data=generate_orderbook(selected), news_data=scenario_news(selected), portfolio_positions=POSITIONS, daily_drawdown=12.0 if selected == "flash_crash" else 0.0)
    try:
        return workflow.invoke(state, config={"configurable": {"thread_id": "dashboard"}})
    except Exception as exc:
        if "interrupt" not in exc.__class__.__name__.lower():
            raise
        return workflow.get_state({"configurable": {"thread_id": "dashboard"}}).values


state = run_analysis(scenario) if run or "dashboard_state" not in st.session_state else st.session_state["dashboard_state"]
if crash_demo:
    state = run_analysis("flash_crash")
st.session_state["dashboard_state"] = state

if page == "Executive Dashboard":
    page_header("Executive view", "Portfolio risk at a glance", "One screen for the decisions that matter before capital moves.")
    context_strip(state)
    risk_level = state.get("risk_level", "Safe").upper()
    risk_class = "status-alert" if risk_level != "SAFE" else "status-safe"
    columns = st.columns(4)
    with columns[0]:
        status_card("Risk status", risk_level, "Composite governance signal", risk_class)
    with columns[1]:
        status_card("Risk score", f"{state.get('risk_score', 0):.2f}", "0 to 100 scale")
    with columns[2]:
        status_card("Current exposure", pct(state.get("exposure_score", 0)), "Portfolio notional at risk")
    with columns[3]:
        status_card("Drawdown", pct(state.get("daily_drawdown", 0)), "Session-to-date")

    st.write("")
    left, right = st.columns([1.25, .75])
    with left:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=state.get("risk_score", 0),
            number={"font": {"size": 42, "color": "#10243e"}, "valueformat": ".2f"},
            title={"text": "Composite risk score", "font": {"size": 16, "color": "#64748b"}},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#0f766e"}, "steps": [{"range": [0, 40], "color": "#d9f3ee"}, {"range": [40, 70], "color": "#fef3c7"}, {"range": [70, 100], "color": "#fee2e2"}], "threshold": {"line": {"color": "#b42318", "width": 4}, "thickness": .8, "value": 80}},
        ))
        gauge.update_layout(height=285, margin={"t": 60, "b": 20, "l": 30, "r": 30}, paper_bgcolor="#ffffff", font={"family": "Georgia"})
        st.plotly_chart(gauge, width="stretch", config={"displayModeBar": False})
    with right:
        breaker_on = state.get("circuit_breaker_triggered", False)
        breaker_class = "breaker-on" if breaker_on else "breaker-off"
        breaker_status = "TRIGGERED" if breaker_on else "OFF"
        breaker_copy = state.get("circuit_breaker_reason", "Execution within governance limits") if breaker_on else "Trading permissions are clear"
        st.markdown(f'<div class="breaker {breaker_class}"><div class="breaker-title">Circuit breaker</div><div class="breaker-value">{breaker_status}</div><div class="breaker-copy">{breaker_copy}</div></div>', unsafe_allow_html=True)
        st.write("")
        mini_left, mini_right = st.columns(2)
        with mini_left:
            status_card("Portfolio value", money(state.get("session_equity", 100000)), "Current session equity")
        with mini_right:
            status_card("Session PnL", money(state.get("realized_pnl", 0)), "Realized result")

    frame = pd.DataFrame(state.get("market_data", []))
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Risk factors")
        timeline = pd.DataFrame({"factor": ["Volatility", "Liquidity", "Sentiment", "Drawdown", "Exposure"], "score": [state.get("volatility_score", 0), state.get("liquidity_score", 0), state.get("sentiment_score", 0), state.get("daily_drawdown", 0) * 5, state.get("exposure_score", 0)]})
        fig = px.bar(timeline, x="factor", y="score", color="score", color_continuous_scale=[[0, "#9bd8cf"], [1, "#b42318"]])
        fig.update_layout(height=300, showlegend=False, coloraxis_showscale=False, margin={"t": 15, "b": 15, "l": 0, "r": 0})
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with chart_right:
        st.subheader(f"Market pulse · {state.get('market_regime', 'Sideways Market')}")
        if not frame.empty:
            fig = px.line(frame, x="timestamp", y="price", color="symbol" if "symbol" in frame else None)
            fig.update_layout(height=300, margin={"t": 15, "b": 15, "l": 0, "r": 0}, showlegend=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No market observations available.")
elif page == "Risk Analytics":
    page_header("Risk analytics", "Understand what is moving the score", "Inspect factor contribution, tail risk, and portfolio quality without raw state noise.")
    context_strip(state)
    analytics = [("Volatility", state.get("volatility_score", 0)), ("Liquidity", state.get("liquidity_score", 0)), ("Sentiment", state.get("sentiment_score", 0)), ("Concentration", state.get("concentration_risk", 0)), ("Position sizing", state.get("position_sizing_risk", 0)), ("Correlation", state.get("correlation_risk", 0))]
    fig = px.bar(pd.DataFrame(analytics, columns=["factor", "score"]), x="score", y="factor", orientation="h", color="score", color_continuous_scale=[[0, "#9bd8cf"], [1, "#b42318"]])
    fig.update_layout(height=320, coloraxis_showscale=False, margin={"t": 10, "b": 10, "l": 0, "r": 0})
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    cols = st.columns(5)
    for column, (label, value) in zip(cols, [("VaR 95%", state.get("var_95", 0)), ("Expected shortfall", state.get("expected_shortfall", 0)), ("Sharpe ratio", state.get("sharpe_ratio", 0)), ("Sortino ratio", state.get("sortino_ratio", 0)), ("Regime confidence", state.get("regime_confidence", 0))]):
        with column:
            status_card(label, f"{value:.2f}", "Model output")
    st.subheader("Portfolio positions")
    section_note("Notional and sizing are calculated from the current simulation snapshot.")
    positions = pd.DataFrame(state.get("portfolio_positions", []))
    if not positions.empty:
        positions["notional"] = positions["quantity"] * positions["entry_price"]
        st.dataframe(positions, width="stretch", hide_index=True)
    else:
        st.info("No open positions.")
elif page == "Operations Center":
    page_header("Operations center", "Control the response", "Simulate incidents, monitor the live feed, and resolve human approval requests.")
    context_strip(state)
    if state.get("circuit_breaker_triggered"):
        st.error(f"Execution paused: {state.get('circuit_breaker_reason', 'threshold breach')}", icon=":material/pause_circle:")
        st.subheader("Human approval queue")
        st.warning(f"Approval required for risk score {state.get('risk_score', 0):.2f}")
        approve, reject, close = st.columns(3)
        with approve:
            approve_clicked = st.button("Approve trading", icon=":material/check:", width="stretch")
        with reject:
            reject_clicked = st.button("Reject trading", icon=":material/block:", width="stretch")
        with close:
            close_clicked = st.button("Force close positions", icon=":material/power_settings_new:", width="stretch")
        action = "APPROVE" if approve_clicked else "REJECT" if reject_clicked else "FORCE CLOSE POSITIONS" if close_clicked else None
        if action:
            st.session_state["dashboard_state"] = workflow.invoke(Command(resume=action), config={"configurable": {"thread_id": "dashboard"}})
            st.success(f"Decision applied: {action}")
            st.rerun()
    else:
        st.success("Execution is within governance limits", icon=":material/check_circle:")
        st.info("No approval is pending. Use ‘Simulate flash crash’ in the sidebar to demonstrate the control loop.")
    st.subheader("Live market feed")
    section_note("The panel refreshes every second. Binance is preferred; YFinance appears automatically when the exchange stream is unavailable.")
    @st.fragment(run_every="1s")
    def live_market_panel():
        try:
            ticks = asyncio.run(get_live_ticks(1))
            if ticks:
                feed_status(str(ticks[0].get("source", "waiting")), len(ticks))
                tick_frame = pd.DataFrame(ticks)
                visible_columns = [column for column in ["timestamp", "symbol", "price", "source"] if column in tick_frame]
                st.dataframe(tick_frame[visible_columns], width="stretch", hide_index=True)
            else:
                feed_status("waiting", 0)
                st.info("Waiting for market observations...")
        except Exception as exc:
            feed_status("waiting", 0)
            st.warning(f"Live feed unavailable: {exc.__class__.__name__}. Simulation data remains active.")
    live_market_panel()
elif page == "Audit & Replay":
    page_header("Audit & replay", "Review every decision", "Trace risk transitions and replay persisted incidents for a defensible audit trail.")
    context_strip(state)
    timeline = pd.DataFrame(state.get("audit_log", []))
    if not timeline.empty:
        timeline["step"] = range(1, len(timeline) + 1)
        color_column = "risk_level" if "risk_level" in timeline.columns else None
        hover_columns = [column for column in ["risk_score", "node", "event"] if column in timeline.columns]
        st.plotly_chart(px.scatter(timeline, x="timestamp", y="step", color=color_column, hover_data=hover_columns), width="stretch", config={"displayModeBar": False})
        st.dataframe(timeline, width="stretch", hide_index=True)
    else:
        st.info("No audit transitions recorded yet.")
    incident = Storage(Path(__file__).resolve().parents[1] / "data" / "fin_guard.db").list_rows("incidents", 1)
    if incident:
        st.download_button("Export audit report", export_audit_pdf(incident[0], state.get("audit_log", [])), "finguard-audit.pdf", "application/pdf", icon=":material/download:")
    st.subheader("Checkpoint replay")
    rows = Storage(Path(__file__).resolve().parents[1] / "data" / "fin_guard.db").list_rows("checkpoints")
    replay = ReplayEngine(Storage(Path(__file__).resolve().parents[1] / "data" / "fin_guard.db"))
    thread_ids = sorted({row["thread_id"] for row in rows})
    selected_thread = st.selectbox("Incident thread", thread_ids) if thread_ids else None
    if selected_thread:
        steps = replay.replay(selected_thread)
        st.caption(f"{len(steps)} persisted transitions in thread `{selected_thread}`")
        selected_step = st.number_input("Replay step", min_value=1, max_value=max(1, len(steps)), value=1)
        current = steps[selected_step - 1]
        st.json({"node": current.get("node"), "timestamp": current.get("timestamp"), "diff": current.get("diff", {})})
    else:
        st.caption("No persisted checkpoints yet")
else:
    page_header("Developer diagnostics", "Inspect the engine clearly", "Charts and structured tables first. Raw LangGraph state stays available for deeper debugging.")
    context_strip(state)
    diagnostic_metrics = st.columns(4)
    with diagnostic_metrics[0]:
        status_card("Graph scenario", str(state.get("scenario", "normal")).replace("_", " ").title(), "Current run")
    with diagnostic_metrics[1]:
        status_card("Market observations", str(len(state.get("market_data", []))), "Input candles")
    with diagnostic_metrics[2]:
        status_card("Audit transitions", str(len(state.get("audit_log", []))), "Persisted events")
    with diagnostic_metrics[3]:
        status_card("Event source", str(state.get("event_source", "simulation")).title(), "Data pipeline")

    curve_frame = pd.DataFrame({
        "step": range(1, max(len(state.get("daily_pnl", [])), len(state.get("equity_curve", [])), len(state.get("drawdown_curve", []))) + 1),
        "daily_pnl": pd.Series(state.get("daily_pnl", [])),
        "equity": pd.Series(state.get("equity_curve", [])),
        "drawdown": pd.Series(state.get("drawdown_curve", [])),
    })
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.subheader("Daily PnL trend")
        if not curve_frame.empty and curve_frame["daily_pnl"].notna().any():
            pnl_chart = px.line(curve_frame, x="step", y="daily_pnl", markers=True)
            pnl_chart.update_layout(height=280, margin={"t": 15, "b": 15, "l": 0, "r": 0}, xaxis_title="Observation", yaxis_title="PnL")
            st.plotly_chart(pnl_chart, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No daily PnL observations available.")
    with chart_right:
        st.subheader("Equity and drawdown")
        equity_columns = [column for column in ["equity", "drawdown"] if curve_frame[column].notna().any()]
        if equity_columns:
            equity_chart = px.line(curve_frame, x="step", y=equity_columns)
            equity_chart.update_layout(height=280, margin={"t": 15, "b": 15, "l": 0, "r": 0}, xaxis_title="Observation", yaxis_title="Value")
            st.plotly_chart(equity_chart, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No equity curve observations available.")

    st.subheader("Portfolio positions")
    positions = pd.DataFrame(state.get("portfolio_positions", []))
    if not positions.empty:
        positions["notional"] = positions["quantity"] * positions["entry_price"]
        position_columns = [column for column in ["symbol", "quantity", "entry_price", "current_price", "notional", "unrealized_pnl", "side", "status"] if column in positions]
        st.dataframe(positions[position_columns], width="stretch", hide_index=True)
    else:
        st.info("No portfolio positions in this run.")

    audit_frame = pd.DataFrame(state.get("audit_log", []))
    if not audit_frame.empty:
        st.subheader("Audit timeline")
        audit_columns = [column for column in ["timestamp", "event", "node", "risk_score", "risk_level", "message"] if column in audit_frame]
        st.dataframe(audit_frame[audit_columns], width="stretch", hide_index=True)

    event_left, event_right = st.columns(2)
    with event_left:
        st.subheader("News events")
        news_events = pd.DataFrame(state.get("news_events", []))
        if not news_events.empty:
            st.dataframe(news_events, width="stretch", hide_index=True)
        else:
            st.caption("No news events.")
    with event_right:
        st.subheader("Lifecycle events")
        lifecycle_events = pd.DataFrame(state.get("lifecycle_events", []))
        if not lifecycle_events.empty:
            st.dataframe(lifecycle_events, width="stretch", hide_index=True)
        else:
            st.caption("No lifecycle events.")

    with st.expander("Advanced: show raw graph state", expanded=False):
        st.json(state)
