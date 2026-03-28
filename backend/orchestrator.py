"""
LangGraph Orchestrator — coordinates the full agent pipeline.
"""
from __future__ import annotations

import os
from typing import Callable

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from backend.agents.alert_generator import alert_generator_node
from backend.agents.context_enricher import context_enricher_node, extended_enricher_node
from backend.agents.data_fetcher import data_fetcher_node
from backend.agents.signal_detector import signal_detector_node
from backend.models import AuditStep, Holding, PipelineState

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


# ---------------------------------------------------------------------------
# safe_agent_node — wraps any node in try/except
# ---------------------------------------------------------------------------

def safe_agent_node(
    node_fn: Callable[[PipelineState], PipelineState],
    state: PipelineState,
) -> PipelineState:
    """Wrap a node function in try/except; append error to state on failure."""
    try:
        return node_fn(state)
    except Exception as e:
        error_msg = f"{node_fn.__name__}: {str(e)}"
        return {
            **state,
            "errors": state.get("errors", []) + [error_msg],
            "audit_trail": state.get("audit_trail", []) + [
                AuditStep(
                    agent=node_fn.__name__,
                    action="error",
                    output_summary=error_msg,
                )
            ],
        }


# ---------------------------------------------------------------------------
# Wrapped node functions
# ---------------------------------------------------------------------------

def safe_data_fetcher_node(state: PipelineState) -> PipelineState:
    return safe_agent_node(data_fetcher_node, state)


def safe_signal_detector_node(state: PipelineState) -> PipelineState:
    return safe_agent_node(signal_detector_node, state)


def safe_context_enricher_node(state: PipelineState) -> PipelineState:
    return safe_agent_node(context_enricher_node, state)


def safe_extended_enricher_node(state: PipelineState) -> PipelineState:
    return safe_agent_node(extended_enricher_node, state)


def safe_alert_generator_node(state: PipelineState) -> PipelineState:
    return safe_agent_node(alert_generator_node, state)


# ---------------------------------------------------------------------------
# route_on_conflict — conditional edge
# ---------------------------------------------------------------------------

def route_on_conflict(state: PipelineState) -> str:
    """Return 'conflicted' if any signal is conflicted, else 'normal'."""
    signals = state.get("signals", [])
    if any(s.is_conflicted for s in signals):
        return "conflicted"
    return "normal"


# ---------------------------------------------------------------------------
# audit_log_node — writes to Supabase
# ---------------------------------------------------------------------------

def audit_log_node(state: PipelineState) -> PipelineState:
    """Write final alert and audit trail to Supabase."""
    audit: list[AuditStep] = []

    try:
        from supabase import create_client

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not configured")

        client = create_client(supabase_url, supabase_key)
        alert = state.get("alert")

        if alert:
            # Use the Python-generated alert_id as the Supabase ID
            alert_id = alert.get("alert_id", str(__import__("uuid").uuid4()))
            # Insert alert
            alert_row = {
                "id": alert_id,
                "ticker": alert.get("ticker", ""),
                "signal_type": alert.get("signal_type", ""),
                "summary": alert.get("summary", ""),
                "recommended_action": alert.get("recommended_action"),
                "confidence": alert.get("confidence"),
                "estimated_impact_inr_low": alert.get("estimated_impact_inr_low"),
                "estimated_impact_inr_high": alert.get("estimated_impact_inr_high"),
                "evidence_chain": alert.get("evidence_chain", []),
                "bull_case": alert.get("bull_case"),
                "bear_case": alert.get("bear_case"),
                "what_to_watch": alert.get("what_to_watch"),
                "disclaimer": alert.get("disclaimer", ""),
                "personalized_opening": alert.get("personalized_opening"),
                "holding_duration_days": alert.get("holding_duration_days"),
                "unrealised_pnl_inr": alert.get("unrealised_pnl_inr"),
                "impact_pct_of_portfolio": alert.get("impact_pct_of_portfolio"),
                "unreported_signal": alert.get("unreported_signal", False),
            }
            result = client.table("alerts").insert(alert_row).execute()
            # Use the original alert_id (we inserted it explicitly)
            db_alert_id = result.data[0]["id"] if result.data else alert_id

            # Insert audit trail entries
            for step in state.get("audit_trail", []):
                audit_row = {
                    "alert_id": db_alert_id,
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
                try:
                    client.table("audit_trail").insert(audit_row).execute()
                except Exception as audit_err:
                    # Log but don't fail the whole pipeline
                    print(f"Audit trail insert failed: {audit_err}")

            audit.append(
                AuditStep(
                    agent="AuditLog",
                    action="persist_to_supabase",
                    output_summary=f"Alert {db_alert_id} and audit trail written to Supabase",
                )
            )

    except Exception as e:
        audit.append(
            AuditStep(
                agent="AuditLog",
                action="persist_error",
                output_summary=f"Supabase write failed: {e}",
            )
        )

    # Compute cost efficiency summary from ModelRouter entries
    model_router_entries = [
        step for step in state.get("audit_trail", [])
        if step.agent == "ModelRouter" and step.estimated_cost_saved is not None
    ]
    if model_router_entries:
        total_saved = sum(s.estimated_cost_saved for s in model_router_entries if s.estimated_cost_saved)
        audit.append(
            AuditStep(
                agent="ModelRouter",
                action="cost_summary",
                output_summary=f"Total estimated savings: ${total_saved:.4f} vs all-GPT-4o baseline",
                estimated_cost_saved=total_saved,
            )
        )

    return {
        **state,
        "audit_trail": state.get("audit_trail", []) + audit,
    }


# ---------------------------------------------------------------------------
# Build the LangGraph StateGraph
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("data_fetch", safe_data_fetcher_node)
    graph.add_node("signal_detect", safe_signal_detector_node)
    graph.add_node("context_enrich", safe_context_enricher_node)
    graph.add_node("extended_enrich", safe_extended_enricher_node)
    graph.add_node("alert_generate", safe_alert_generator_node)
    graph.add_node("audit_log", audit_log_node)

    graph.set_entry_point("data_fetch")
    graph.add_edge("data_fetch", "signal_detect")
    graph.add_conditional_edges(
        "signal_detect",
        route_on_conflict,
        {"conflicted": "extended_enrich", "normal": "context_enrich"},
    )
    graph.add_edge("extended_enrich", "alert_generate")
    graph.add_edge("context_enrich", "alert_generate")
    graph.add_edge("alert_generate", "audit_log")
    graph.add_edge("audit_log", END)

    return graph


_compiled_graph = None


def _get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph().compile()
    return _compiled_graph


# ---------------------------------------------------------------------------
# run_pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    ticker: str,
    portfolio: list[Holding],
    scenario_hint: str | None = None,
) -> PipelineState:
    """Invoke the compiled LangGraph pipeline and return final state."""
    initial_state: PipelineState = {
        "ticker": ticker,
        "portfolio": portfolio,
        "scenario_hint": scenario_hint,
        "price_data": None,
        "bulk_deals": [],
        "news_results": [],
        "filing_scan_result": None,
        "signals": [],
        "conflict_report": None,
        "enriched_context": None,
        "portfolio_match": False,
        "alert": None,
        "audit_trail": [],
        "errors": [],
    }

    graph = _get_compiled_graph()
    result = graph.invoke(initial_state)
    return result
