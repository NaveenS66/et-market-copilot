"""
FastAPI application entry point for ET Investor Copilot.
"""
from __future__ import annotations

import copy
import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import alerts, analysis, portfolio

app = FastAPI(title="ET Investor Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(portfolio.router)
app.include_router(analysis.router)
app.include_router(alerts.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/demo/{scenario_name}")
def run_demo_scenario(scenario_name: str):
    """
    Run a pre-populated demo scenario through the agent pipeline.
    Skips DataFetcher (data is pre-populated) and runs:
    signal_detector → context_enricher/extended_enricher → alert_generator

    For the macro scenario, runs the pipeline for each affected ticker
    and returns alerts ranked by absolute estimated impact.
    """
    from backend.agents.alert_generator import alert_generator_node
    from backend.agents.context_enricher import context_enricher_node, extended_enricher_node
    from backend.agents.signal_detector import signal_detector_node
    from backend.demo.scenarios import SCENARIOS
    from backend.orchestrator import safe_agent_node

    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{scenario_name}'. Valid: {list(SCENARIOS.keys())}",
        )

    def _run_single(state: dict) -> dict | None:
        """Run signal_detect → enrich → alert_generate on a state dict."""
        state = safe_agent_node(signal_detector_node, state)
        signals = state.get("signals", [])
        if any(s.is_conflicted for s in signals):
            state = safe_agent_node(extended_enricher_node, state)
        else:
            state = safe_agent_node(context_enricher_node, state)
        state = safe_agent_node(alert_generator_node, state)
        alert = state.get("alert")
        if alert:
            # Attach audit trail directly so UI can show it without Supabase
            alert["_audit_trail"] = [
                {
                    "id": str(i),
                    "alert_id": alert.get("alert_id", ""),
                    "agent_name": step.agent,
                    "action": step.action,
                    "source_urls": step.source_urls or [],
                    "model_used": step.model_used,
                    "fallback_occurred": step.fallback_occurred,
                    "fallback_reason": step.fallback_reason,
                    "output_summary": step.output_summary,
                    "task_type": step.task_type,
                    "estimated_cost_saved": step.estimated_cost_saved,
                    "timestamp": step.timestamp.isoformat(),
                }
                for i, step in enumerate(state.get("audit_trail", []))
            ]
        return alert

    if scenario_name == "macro":
        from backend.demo.scenarios import SCENARIO_MACRO_DUAL
        from backend.models import PriceData

        # Ticker 1: HDFCBANK.NS — RBI rate cut (banking sector)
        state1 = copy.deepcopy(SCENARIO_MACRO_DUAL)
        state1["ticker"] = "HDFCBANK.NS"
        state1["news_results"] = [SCENARIO_MACRO_DUAL["news_results"][0]]

        # Ticker 2: INFY.NS — SEBI regulation (IT sector)
        state2 = copy.deepcopy(SCENARIO_MACRO_DUAL)
        state2["ticker"] = "INFY.NS"
        state2["price_data"] = PriceData(
            ticker="INFY.NS", close=1892.0, volume=5000000,
            avg_volume_20d=6000000.0, week52_high=1950.0, week52_low=1320.0,
            rsi14=52.0, source_url="https://finance.yahoo.com/quote/INFY.NS",
            retrieved_at=datetime.datetime.utcnow()
        )
        state2["news_results"] = [SCENARIO_MACRO_DUAL["news_results"][1]]

        alerts = []
        for state in [state1, state2]:
            alert = _run_single(state)
            if alert:
                alerts.append(alert)

        # Rank by absolute estimated impact (highest first)
        def _abs_impact(a):
            v = a.get("estimated_impact_inr_high")
            return abs(v) if v is not None else 0

        alerts.sort(key=_abs_impact, reverse=True)
        for rank, alert in enumerate(alerts, start=1):
            alert["priority_rank"] = rank

        return alerts

    # Single-ticker scenarios (bulk_deal, breakout)
    state = copy.deepcopy(SCENARIOS[scenario_name])
    alert = _run_single(state)
    if alert is None:
        raise HTTPException(status_code=500, detail="Pipeline produced no alert")
    return alert
