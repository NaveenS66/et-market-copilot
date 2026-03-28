"""
FastAPI application entry point for ET Investor Copilot.
"""
from __future__ import annotations

import copy

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import alerts, analysis, portfolio

app = FastAPI(title="ET Investor Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
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
    signal_detector → context_enricher → alert_generator
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

    # Deep copy so the fixture is not mutated between calls
    state = copy.deepcopy(SCENARIOS[scenario_name])

    # Run signal detection
    state = safe_agent_node(signal_detector_node, state)

    # Route to extended enricher if conflicted, else standard
    signals = state.get("signals", [])
    if any(s.is_conflicted for s in signals):
        state = safe_agent_node(extended_enricher_node, state)
    else:
        state = safe_agent_node(context_enricher_node, state)

    # Generate alert
    state = safe_agent_node(alert_generator_node, state)

    alert = state.get("alert")
    if alert is None:
        raise HTTPException(status_code=500, detail="Pipeline produced no alert")

    return alert
