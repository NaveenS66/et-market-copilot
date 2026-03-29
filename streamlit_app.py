"""
ET Investor Copilot — Streamlit Demo UI
Wraps the existing backend pipeline directly (no FastAPI needed).
"""
import copy
import os
import sys

import streamlit as st
from dotenv import load_dotenv

# Load env from backend/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "backend", ".env"))

# Make backend importable
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="ET Investor Copilot",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📈 ET Investor Copilot")
st.caption("Portfolio-aware signal intelligence for Indian retail investors · ET AI Hackathon 2026")
st.divider()

# ---------------------------------------------------------------------------
# Scenario selector
# ---------------------------------------------------------------------------
SCENARIOS = {
    "🏦 Bulk Deal — HDFC Bank (Unreported Signal)": "bulk_deal",
    "💻 Conflicted Breakout — Infosys (RSI Overbought + FII Selling)": "breakout",
    "🌐 Dual Macro Events — RBI Rate Cut + SEBI Regulation": "macro",
}

st.subheader("Judge Scenario Pack")
st.caption("Pre-loaded with realistic NSE data. Each runs the full agent pipeline.")

selected_label = st.selectbox("Select a scenario", list(SCENARIOS.keys()))
scenario_id = SCENARIOS[selected_label]

run = st.button("▶ Run Analysis", type="primary", use_container_width=False)

# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------
if run:
    with st.spinner("Running agent pipeline…"):
        try:
            import datetime
            from backend.agents.alert_generator import alert_generator_node
            from backend.agents.context_enricher import context_enricher_node, extended_enricher_node
            from backend.agents.signal_detector import signal_detector_node
            from backend.demo.scenarios import SCENARIOS as SCENARIO_DATA
            from backend.models import PriceData
            from backend.orchestrator import safe_agent_node

            def _run_single(state: dict) -> dict | None:
                state = safe_agent_node(signal_detector_node, state)
                signals = state.get("signals", [])
                if any(s.is_conflicted for s in signals):
                    state = safe_agent_node(extended_enricher_node, state)
                else:
                    state = safe_agent_node(context_enricher_node, state)
                state = safe_agent_node(alert_generator_node, state)
                return state

            alerts = []

            if scenario_id == "macro":
                from backend.demo.scenarios import SCENARIO_MACRO_DUAL

                state1 = copy.deepcopy(SCENARIO_MACRO_DUAL)
                state1["ticker"] = "HDFCBANK.NS"
                state1["news_results"] = [SCENARIO_MACRO_DUAL["news_results"][0]]

                state2 = copy.deepcopy(SCENARIO_MACRO_DUAL)
                state2["ticker"] = "INFY.NS"
                state2["price_data"] = PriceData(
                    ticker="INFY.NS", close=1892.0, volume=5000000,
                    avg_volume_20d=6000000.0, week52_high=1950.0, week52_low=1320.0,
                    rsi14=52.0, source_url="https://finance.yahoo.com/quote/INFY.NS",
                    retrieved_at=datetime.datetime.utcnow()
                )
                state2["news_results"] = [SCENARIO_MACRO_DUAL["news_results"][1]]

                for state in [state1, state2]:
                    final = _run_single(state)
                    if final.get("alert"):
                        alerts.append((final["alert"], final.get("audit_trail", [])))
            else:
                state = copy.deepcopy(SCENARIO_DATA[scenario_id])
                final = _run_single(state)
                if final.get("alert"):
                    alerts.append((final["alert"], final.get("audit_trail", [])))

            st.session_state["alerts"] = alerts
            st.session_state["errors"] = []

        except Exception as e:
            st.session_state["alerts"] = []
            st.session_state["errors"] = [str(e)]

# ---------------------------------------------------------------------------
# Display alerts
# ---------------------------------------------------------------------------
if "errors" in st.session_state and st.session_state["errors"]:
    for err in st.session_state["errors"]:
        st.error(f"Pipeline error: {err}")

if "alerts" in st.session_state and st.session_state["alerts"]:
    st.divider()
    st.subheader("Signal Alerts")

    for alert, audit_trail in st.session_state["alerts"]:
        signal_type = alert.get("signal_type", "")
        ticker = alert.get("ticker", "")
        confidence = alert.get("confidence", "")
        unreported = alert.get("unreported_signal", False)
        priority = alert.get("priority_rank")

        # Badge colors
        badge_map = {
            "bulk_deal": "🔴 BULK DEAL",
            "breakout_conflicted": "🟡 CONFLICTED",
            "macro_event": "🔵 MACRO",
            "breakout": "🟢 BREAKOUT",
        }
        badge = badge_map.get(signal_type, signal_type.upper())

        header = f"{badge} · **{ticker}** · {confidence} confidence"
        if unreported:
            header += " · 🔍 **Unreported Signal**"
        if priority:
            header += f" · #{priority} Priority"

        with st.expander(header, expanded=True):
            # Personalized opening
            if alert.get("personalized_opening"):
                st.info(alert["personalized_opening"])

            st.markdown(f"**Summary:** {alert.get('summary', '')}")
            st.markdown(f"**Recommended Action:** {alert.get('recommended_action', '')}")

            # Impact
            low = alert.get("estimated_impact_inr_low")
            high = alert.get("estimated_impact_inr_high")
            if low is not None and high is not None:
                color = "red" if high < 0 else "green"
                st.markdown(
                    f"**Estimated Impact:** :{color}[₹{low:,.0f} to ₹{high:,.0f}]"
                )

            # Bull / Bear
            col1, col2 = st.columns(2)
            if alert.get("bull_case"):
                with col1:
                    st.success(f"**Bull Case:** {alert['bull_case']}")
            if alert.get("bear_case"):
                with col2:
                    st.error(f"**Bear Case:** {alert['bear_case']}")

            # What to watch
            if alert.get("what_to_watch"):
                st.markdown("**What to Watch:**")
                for item in alert["what_to_watch"]:
                    st.markdown(f"- {item}")

            # Evidence chain
            if alert.get("evidence_chain"):
                with st.expander(f"📎 Evidence Chain ({len(alert['evidence_chain'])} sources)"):
                    for ev in alert["evidence_chain"]:
                        st.markdown(
                            f"- **{ev.get('label')}:** {ev.get('value')} — "
                            f"[{ev.get('source_name')}]({ev.get('source_url')})"
                        )

            # Audit trail
            if audit_trail:
                with st.expander("🔍 Agent Reasoning Trail"):
                    router_steps = [s for s in audit_trail if s.agent == "ModelRouter"]
                    other_steps = [s for s in audit_trail if s.agent != "ModelRouter"]

                    for step in other_steps:
                        st.markdown(
                            f"`{step.agent}` → **{step.action}**"
                            + (f" · _{step.output_summary}_" if step.output_summary else "")
                        )

                    if router_steps:
                        st.divider()
                        st.markdown("**Model Routing:**")
                        total_saved = 0.0
                        for s in router_steps:
                            st.markdown(f"- {s.output_summary}")
                            total_saved += s.estimated_cost_saved or 0
                        if total_saved > 0:
                            st.success(f"Total saved vs all-GPT-4o: ~${total_saved:.4f}")

            st.caption(alert.get("disclaimer", ""))
