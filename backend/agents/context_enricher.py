"""
ContextEnricher Agent — enriches signals with portfolio context and historical data.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from backend.agents.backtest_engine import compute_breakout_success_rate
from backend.models import (
    AuditStep,
    BacktestResult,
    EnrichedContext,
    Holding,
    PipelineState,
    Signal,
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Sector sensitivity coefficients for impact estimation
# ---------------------------------------------------------------------------
SECTOR_SENSITIVITY: dict[str, dict[str, tuple[float, float]]] = {
    # signal_type → sector → (low_pct, high_pct) of holding value
    "bulk_deal_promoter_sell": {
        "default": (-0.15, -0.05),
    },
    "macro_rate_cut": {
        "banking": (0.05, 0.08),
        "NBFC": (0.04, 0.07),
        "IT": (-0.01, 0.01),
        "energy": (0.01, 0.03),
        "pharma": (0.00, 0.02),
        "auto": (0.02, 0.04),
        "default": (0.01, 0.03),
    },
    "macro_rate_hike": {
        "banking": (-0.05, -0.02),
        "NBFC": (-0.06, -0.03),
        "IT": (-0.02, 0.00),
        "energy": (-0.03, -0.01),
        "default": (-0.03, -0.01),
    },
    "macro_regulatory": {
        "default": (-0.10, -0.03),
    },
    "breakout": {
        "default": (0.05, 0.12),
    },
    "macro_event": {
        "banking": (-0.08, 0.08),
        "NBFC": (-0.07, 0.07),
        "IT": (-0.03, 0.03),
        "energy": (-0.05, 0.05),
        "default": (-0.05, 0.05),
    },
}

# Sector map (same as signal_detector for consistency)
SECTOR_MAP: dict[str, str] = {
    "HDFCBANK.NS": "banking", "HDFCBANK": "banking",
    "ICICIBANK.NS": "banking", "ICICIBANK": "banking",
    "SBIN.NS": "banking", "SBIN": "banking",
    "KOTAKBANK.NS": "banking", "KOTAKBANK": "banking",
    "AXISBANK.NS": "banking", "AXISBANK": "banking",
    "INFY.NS": "IT", "INFY": "IT",
    "TCS.NS": "IT", "TCS": "IT",
    "WIPRO.NS": "IT", "WIPRO": "IT",
    "HCLTECH.NS": "IT", "HCLTECH": "IT",
    "TECHM.NS": "IT", "TECHM": "IT",
    "RELIANCE.NS": "energy", "RELIANCE": "energy",
    "ONGC.NS": "energy", "ONGC": "energy",
    "BPCL.NS": "energy", "BPCL": "energy",
    "IOC.NS": "energy", "IOC": "energy",
    "SUNPHARMA.NS": "pharma", "SUNPHARMA": "pharma",
    "DRREDDY.NS": "pharma", "DRREDDY": "pharma",
    "CIPLA.NS": "pharma", "CIPLA": "pharma",
    "TATAMOTORS.NS": "auto", "TATAMOTORS": "auto",
    "MARUTI.NS": "auto", "MARUTI": "auto",
    "M&M.NS": "auto", "M&M": "auto",
    "BAJFINANCE.NS": "NBFC", "BAJFINANCE": "NBFC",
    "BAJAJFINSV.NS": "NBFC", "BAJAJFINSV": "NBFC",
}


def _get_holding(portfolio: list[Holding], ticker: str) -> Holding | None:
    for h in portfolio:
        if h.ticker == ticker:
            return h
    return None


# ---------------------------------------------------------------------------
# estimate_impact
# ---------------------------------------------------------------------------

def estimate_impact(
    signal: Signal, holding: Holding, current_price: float
) -> tuple[float, float]:
    """
    Returns (low, high) INR impact range.
    Uses sector sensitivity coefficients × holding value.
    """
    holding_value = holding.quantity * current_price
    sector = SECTOR_MAP.get(holding.ticker, "default")

    # Determine sensitivity table
    sensitivity_table = SECTOR_SENSITIVITY.get(signal.type, {})
    low_pct, high_pct = sensitivity_table.get(sector, sensitivity_table.get("default", (-0.05, 0.05)))

    impact_low = holding_value * low_pct
    impact_high = holding_value * high_pct

    # Ensure low <= high
    if impact_low > impact_high:
        impact_low, impact_high = impact_high, impact_low

    return impact_low, impact_high


# ---------------------------------------------------------------------------
# fetch_breakout_history
# ---------------------------------------------------------------------------

def fetch_breakout_history(ticker: str, years: int = 2) -> BacktestResult:
    """
    Compute historical breakout success rate from real yfinance data.
    A breakout is: close >= rolling 52W high AND volume > avg_vol_20d * 1.2.
    Success: price > 5% higher 30 calendar days later.
    """
    try:
        hist = yf.Ticker(ticker).history(period=f"{years}y")
    except Exception as e:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note=f"yfinance error: {e}",
        )

    if hist.empty:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="No historical data",
        )

    hist["rolling_52w_high"] = hist["Close"].rolling(252).max().shift(1)
    hist["avg_vol_20d"] = hist["Volume"].rolling(20).mean().shift(1)
    hist = hist.dropna(subset=["rolling_52w_high", "avg_vol_20d"])

    breakouts = hist[
        (hist["Close"] >= hist["rolling_52w_high"])
        & (hist["Volume"] > hist["avg_vol_20d"] * 1.2)
    ]

    if len(breakouts) == 0:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="No breakout events found",
        )

    gains: list[float] = []
    losses: list[float] = []

    for dt in breakouts.index:
        future_date = dt + pd.Timedelta(days=30)
        future_slice = hist[hist.index >= future_date]
        if future_slice.empty:
            continue
        future_price = float(future_slice.iloc[0]["Close"])
        entry_price = float(hist.loc[dt, "Close"])
        pct_change = (future_price - entry_price) / entry_price * 100
        if pct_change > 5:
            gains.append(pct_change)
        else:
            losses.append(pct_change)

    total = len(gains) + len(losses)
    if total == 0:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="Insufficient forward data",
        )

    return BacktestResult(
        ticker=ticker,
        success_rate_pct=round(len(gains) / total * 100, 1),
        sample_size=total,
        avg_gain_pct=round(sum(gains) / len(gains), 2) if gains else None,
        avg_loss_pct=round(sum(losses) / len(losses), 2) if losses else None,
        note=None,
    )


# ---------------------------------------------------------------------------
# fetch_eps_trend
# ---------------------------------------------------------------------------

def fetch_eps_trend(ticker: str, quarters: int = 4) -> list[float]:
    """Fetch last N quarters of EPS from yfinance."""
    try:
        t = yf.Ticker(ticker)
        # Try quarterly_income_stmt first (newer yfinance), fall back to quarterly_earnings
        earnings = None
        try:
            stmt = t.quarterly_income_stmt
            if stmt is not None and not stmt.empty:
                # Look for Basic EPS or Diluted EPS row
                for row_name in ["Basic EPS", "Diluted EPS", "EPS"]:
                    if row_name in stmt.index:
                        values = stmt.loc[row_name].dropna().tolist()
                        return [float(v) for v in values[:quarters]]
        except Exception:
            pass
        # Fallback: quarterly_earnings (older yfinance)
        try:
            earnings = t.quarterly_earnings
            if earnings is not None and not earnings.empty:
                eps_col = "EPS" if "EPS" in earnings.columns else earnings.columns[0]
                values = earnings[eps_col].dropna().tolist()
                return [float(v) for v in values[:quarters]]
        except Exception:
            pass
        return []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# context_enricher_node
# ---------------------------------------------------------------------------

def context_enricher_node(state: PipelineState) -> PipelineState:
    """Enrich signals with portfolio context, EPS trend, and impact estimates."""
    ticker = state["ticker"]
    portfolio = state.get("portfolio", [])
    signals: list[Signal] = state.get("signals", [])
    audit: list[AuditStep] = []

    portfolio_match = any(h.ticker == ticker for h in portfolio)
    holding = _get_holding(portfolio, ticker)
    current_price = state.get("price_data").close if state.get("price_data") else (
        holding.current_price if holding else 0.0
    )

    enriched = EnrichedContext(portfolio_match=portfolio_match)

    for sig in signals:
        # EPS trend for bulk deal promoter sell
        if sig.type == "bulk_deal_promoter_sell":
            eps_trend = fetch_eps_trend(ticker, quarters=4)
            enriched.eps_trend = eps_trend if eps_trend else None

            # Management commentary via Tavily
            try:
                from tavily import TavilyClient
                api_key = os.environ.get("TAVILY_API_KEY", "")
                client = TavilyClient(api_key=api_key)
                results = client.search(
                    query=f"{ticker} management commentary earnings call transcript",
                    max_results=3,
                    search_depth="basic",
                )
                snippets = [r.get("content", "") for r in results.get("results", [])]
                enriched.mgmt_commentary = " ".join(snippets)[:500] if snippets else None
                audit.append(
                    AuditStep(
                        agent="ContextEnricher",
                        action="fetch_mgmt_commentary",
                        source_urls=[r.get("url", "") for r in results.get("results", [])],
                        output_summary=f"EPS trend: {eps_trend}, commentary fetched",
                    )
                )
            except Exception as e:
                enriched.mgmt_commentary = None
                audit.append(
                    AuditStep(
                        agent="ContextEnricher",
                        action="fetch_mgmt_commentary_error",
                        output_summary=str(e),
                    )
                )

        # Impact estimation for portfolio holdings
        if portfolio_match and holding and current_price > 0:
            impact_low, impact_high = estimate_impact(sig, holding, current_price)
            enriched.impact_inr_low = impact_low
            enriched.impact_inr_high = impact_high
            audit.append(
                AuditStep(
                    agent="ContextEnricher",
                    action="estimate_impact",
                    output_summary=(
                        f"Impact range: ₹{impact_low:,.0f} to ₹{impact_high:,.0f}"
                    ),
                )
            )

    # Portfolio match audit
    audit.append(
        AuditStep(
            agent="ContextEnricher",
            action="portfolio_match_check",
            output_summary=f"portfolio_match={portfolio_match} for {ticker}",
        )
    )

    return {
        **state,
        "enriched_context": enriched,
        "portfolio_match": portfolio_match,
        "audit_trail": state.get("audit_trail", []) + audit,
    }


# ---------------------------------------------------------------------------
# extended_enricher_node
# ---------------------------------------------------------------------------

def extended_enricher_node(state: PipelineState) -> PipelineState:
    """Extended enrichment for conflicted signals: adds breakout history."""
    # First run standard enrichment
    base_state = context_enricher_node(state)
    ticker = state["ticker"]
    audit: list[AuditStep] = []

    # Fetch breakout history via BacktestEngine
    try:
        backtest = compute_breakout_success_rate(ticker, years=2)
        enriched = base_state.get("enriched_context")
        if enriched is not None:
            enriched.breakout_success_rate = backtest.success_rate_pct
            enriched.backtest_result = backtest
        audit.append(
            AuditStep(
                agent="ContextEnricher",
                action="fetch_breakout_history",
                output_summary=(
                    f"Backtest: success_rate={backtest.success_rate_pct}%, "
                    f"sample_size={backtest.sample_size}, "
                    f"avg_gain={backtest.avg_gain_pct}%, avg_loss={backtest.avg_loss_pct}%"
                ),
            )
        )
    except Exception as e:
        audit.append(
            AuditStep(
                agent="ContextEnricher",
                action="fetch_breakout_history_error",
                output_summary=str(e),
            )
        )

    return {
        **base_state,
        "audit_trail": base_state.get("audit_trail", []) + audit,
    }


# ---------------------------------------------------------------------------
# rank_macro_events — priority ranking by absolute impact
# ---------------------------------------------------------------------------

def rank_macro_events(enriched_contexts: list[EnrichedContext]) -> list[EnrichedContext]:
    """
    Sort enriched contexts by abs(impact_inr_high) descending and assign priority_rank.
    Rank 1 = highest priority (largest absolute impact).
    """
    sortable = [
        (abs(ctx.impact_inr_high or 0.0), ctx)
        for ctx in enriched_contexts
    ]
    sortable.sort(key=lambda x: x[0], reverse=True)
    for rank, (_, ctx) in enumerate(sortable, start=1):
        ctx.priority_rank = rank
    return [ctx for _, ctx in sortable]
