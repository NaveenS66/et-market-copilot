"""
AlertGenerator Agent — LLM-powered alert generation with Gemini primary, GPT-4o fallback.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv

from backend.models import (
    AlertResponse,
    AuditStep,
    EvidenceItem,
    Holding,
    PipelineState,
    Signal,
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DISCLAIMER_TEXT = (
    "This alert is for informational purposes only and is not licensed financial advice."
)


def _get_holding(portfolio: list[Holding], ticker: str) -> Holding | None:
    for h in portfolio:
        if h.ticker == ticker:
            return h
    return None


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_bulk_deal_prompt(state: PipelineState) -> str:
    ticker = state["ticker"]
    bulk_deals = state.get("bulk_deals", [])
    enriched = state.get("enriched_context")
    price_data = state.get("price_data")

    deal = bulk_deals[0] if bulk_deals else None
    pct_equity = deal.pct_equity if deal else 0.0
    filing_url = deal.filing_url if deal else "N/A"
    market_price = price_data.close if price_data else 0.0
    deal_price = deal.price if deal else 0.0
    discount = ((market_price - deal_price) / market_price * 100) if market_price > 0 else 0.0
    eps_trend = enriched.eps_trend if enriched else None
    mgmt_commentary = enriched.mgmt_commentary if enriched else "Not available"

    return f"""You are a financial analyst assistant for Indian retail investors.

SIGNAL: Promoter bulk deal sell
Ticker: {ticker}
Deal size: {pct_equity:.2f}% of equity at {discount:.1f}% discount to market price
Filing: {filing_url}
EPS trend (last 4Q): {eps_trend}
Management commentary: {mgmt_commentary}

Generate a structured alert with:
1. SUMMARY (2 sentences)
2. DISTRESS vs ROUTINE assessment with reasoning
3. RECOMMENDED ACTION with confidence (Low/Medium/High) — not a binary buy/sell
4. EVIDENCE CHAIN: list each data point with source URL
5. DISCLAIMER: "This is not licensed financial advice."

Format as JSON with these exact keys:
{{
  "signal_type": "bulk_deal",
  "ticker": "{ticker}",
  "summary": "...",
  "recommended_action": "...",
  "confidence": "Low|Medium|High",
  "bull_case": null,
  "bear_case": "...",
  "what_to_watch": ["...", "..."],
  "evidence_chain": [
    {{"label": "...", "value": "...", "source_name": "...", "source_url": "...", "retrieved_at": "..."}}
  ],
  "disclaimer": "{DISCLAIMER_TEXT}"
}}"""


def build_breakout_conflicted_prompt(state: PipelineState) -> str:
    ticker = state["ticker"]
    price_data = state.get("price_data")
    enriched = state.get("enriched_context")
    conflict_report = state.get("conflict_report")

    close = price_data.close if price_data else 0.0
    week52_high = price_data.week52_high if price_data else 0.0
    volume = price_data.volume if price_data else 0
    avg_vol = price_data.avg_volume_20d if price_data else 0.0
    rsi14 = price_data.rsi14 if price_data else 0.0
    success_rate = enriched.breakout_success_rate if enriched else None
    backtest = enriched.backtest_result if enriched else None
    avg_gain = backtest.avg_gain_pct if backtest else None
    avg_loss = backtest.avg_loss_pct if backtest else None
    sample_size = backtest.sample_size if backtest else 0

    # FII change from flags
    fii_change = "N/A"
    if conflict_report:
        for flag in conflict_report.bear_indicators:
            if flag.name == "fii_reduction":
                fii_change = f"{flag.value:.1f}%"

    return f"""You are a financial analyst assistant for Indian retail investors.

SIGNAL: Breakout with conflicting indicators
Ticker: {ticker}
Price vs 52W High: {close} vs {week52_high} (BREAKOUT)
Volume: {volume} vs {avg_vol:.0f} avg (above average)
RSI(14): {rsi14:.1f} (OVERBOUGHT >70)
FII change QoQ: {fii_change} (REDUCTION)
Historical breakout success rate (2Y): {success_rate}% (sample_size={sample_size}, avg_gain={avg_gain}%, avg_loss={avg_loss}%)

Generate a structured alert with:
1. SUMMARY (2 sentences)
2. BULL CASE: evidence for continued upside
3. BEAR CASE: evidence for reversal
4. RECOMMENDATION: confidence level only (Low/Medium/High), NOT a binary buy/sell
5. WHAT TO WATCH: 2-3 specific future data points to monitor
6. EVIDENCE CHAIN: each indicator with exact value, date, and source
7. DISCLAIMER

Format as JSON with these exact keys:
{{
  "signal_type": "breakout_conflicted",
  "ticker": "{ticker}",
  "summary": "...",
  "recommended_action": "Monitor closely — conflicting signals present",
  "confidence": "Low|Medium|High",
  "bull_case": "...",
  "bear_case": "...",
  "what_to_watch": ["...", "...", "..."],
  "evidence_chain": [
    {{"label": "RSI(14) value", "value": "{rsi14:.1f} as of {datetime.utcnow().date()}", "source_name": "yfinance", "source_url": "https://finance.yahoo.com/quote/{ticker}", "retrieved_at": "{datetime.utcnow().isoformat()}"}}
  ],
  "disclaimer": "{DISCLAIMER_TEXT}"
}}"""


def build_macro_event_prompt(state: PipelineState) -> str:
    ticker = state["ticker"]
    enriched = state.get("enriched_context")
    news_results = state.get("news_results", [])

    impact_low = enriched.impact_inr_low if enriched else None
    impact_high = enriched.impact_inr_high if enriched else None
    priority_rank = enriched.priority_rank if enriched else 1
    news_summary = "; ".join(n.title for n in news_results[:3]) if news_results else "No news available"

    return f"""You are a financial analyst assistant for Indian retail investors.

SIGNAL: Macro event affecting portfolio
Ticker: {ticker}
News context: {news_summary}
Estimated P&L impact: ₹{impact_low:,.0f} to ₹{impact_high:,.0f} (priority rank: {priority_rank})

Generate a structured alert with:
1. SUMMARY (2 sentences)
2. ESTIMATED IMPACT on holding with methodology explanation
3. PRIORITY RANK relative to other simultaneous events
4. RECOMMENDED ACTION with confidence (Low/Medium/High)
5. EVIDENCE CHAIN with news sources
6. DISCLAIMER

Format as JSON with these exact keys:
{{
  "signal_type": "macro_event",
  "ticker": "{ticker}",
  "summary": "...",
  "recommended_action": "...",
  "confidence": "Low|Medium|High",
  "bull_case": null,
  "bear_case": null,
  "what_to_watch": ["...", "..."],
  "evidence_chain": [
    {{"label": "...", "value": "...", "source_name": "...", "source_url": "...", "retrieved_at": "..."}}
  ],
  "disclaimer": "{DISCLAIMER_TEXT}"
}}"""


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def gemini_generate(prompt: str) -> str:
    """Generate text using Gemini 1.5 Flash."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.environ.get("GEMINI_API_KEY", "")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=api_key)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def openai_generate(prompt: str) -> str:
    """Generate text using OpenAI GPT-4o."""
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "")
    llm = ChatOpenAI(model="gpt-4o", openai_api_key=api_key)
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


# ---------------------------------------------------------------------------
# Alert parsing
# ---------------------------------------------------------------------------

def _parse_alert_response(raw: str, state: PipelineState) -> AlertResponse:
    """Parse LLM JSON response into AlertResponse. Falls back to minimal alert on error."""
    import re

    ticker = state["ticker"]
    signals: list[Signal] = state.get("signals", [])
    signal_type = signals[0].type if signals else "unknown"
    enriched = state.get("enriched_context")

    # Extract JSON block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # Build evidence chain
    evidence_chain: list[EvidenceItem] = data.get("evidence_chain", [])
    if not evidence_chain:
        price_data = state.get("price_data")
        if price_data:
            evidence_chain = [
                EvidenceItem(
                    label="Price data",
                    value=f"close={price_data.close}, rsi14={price_data.rsi14:.1f}",
                    source_name="yfinance",
                    source_url=price_data.source_url,
                    retrieved_at=price_data.retrieved_at.isoformat(),
                )
            ]

    alert: AlertResponse = {
        "alert_id": str(uuid.uuid4()),
        "ticker": data.get("ticker", ticker),
        "signal_type": data.get("signal_type", signal_type),
        "summary": data.get("summary", f"Signal detected for {ticker}"),
        "recommended_action": data.get("recommended_action", "Review signal carefully"),
        "confidence": data.get("confidence", "Low"),
        "estimated_impact_inr_low": enriched.impact_inr_low if enriched else None,
        "estimated_impact_inr_high": enriched.impact_inr_high if enriched else None,
        "evidence_chain": evidence_chain,
        "bull_case": data.get("bull_case"),
        "bear_case": data.get("bear_case"),
        "what_to_watch": data.get("what_to_watch"),
        "disclaimer": DISCLAIMER_TEXT,
        "personalized_opening": None,
        "holding_duration_days": None,
        "unrealised_pnl_inr": None,
        "impact_pct_of_portfolio": None,
        "unreported_signal": signals[0].is_unreported if signals else False,
        "created_at": datetime.utcnow().isoformat(),
    }
    return alert


# ---------------------------------------------------------------------------
# alert_generator_node — LangGraph node
# ---------------------------------------------------------------------------

def alert_generator_node(state: PipelineState) -> PipelineState:
    """Select prompt, call LLM with fallback, parse response, add personalization."""
    signals: list[Signal] = state.get("signals", [])
    audit: list[AuditStep] = []

    if not signals:
        # No signals — return minimal state
        return {**state, "alert": None}

    sig = signals[0]

    # Select prompt builder
    if sig.type == "bulk_deal_promoter_sell":
        prompt = build_bulk_deal_prompt(state)
    elif sig.type == "breakout_conflicted" or sig.is_conflicted:
        prompt = build_breakout_conflicted_prompt(state)
    elif sig.type == "macro_event":
        prompt = build_macro_event_prompt(state)
    else:
        prompt = build_breakout_conflicted_prompt(state)

    # LLM call with fallback
    model_used = "gemini-1.5-flash"
    fallback_occurred = False
    fallback_reason: str | None = None
    raw = ""

    try:
        raw = gemini_generate(prompt)
        if not raw or len(raw.strip()) < 50:
            raise ValueError("Empty or too-short Gemini response")
    except Exception as e:
        fallback_reason = str(e)
        try:
            raw = openai_generate(prompt)
            model_used = "gpt-4o"
            fallback_occurred = True
        except Exception as e2:
            # Both failed — build minimal alert
            raw = ""
            fallback_reason = f"Gemini: {e}; GPT-4o: {e2}"
            fallback_occurred = True

    audit.append(
        AuditStep(
            agent="AlertGenerator",
            action="llm_generate",
            model_used=model_used,
            fallback_occurred=fallback_occurred,
            fallback_reason=fallback_reason,
            output_summary=f"Generated alert using {model_used}",
        )
    )

    # Parse response
    alert = _parse_alert_response(raw, state)
    alert["disclaimer"] = DISCLAIMER_TEXT

    # Personalized opening (Requirement 15)
    portfolio = state.get("portfolio", [])
    portfolio_match = state.get("portfolio_match", False)
    if portfolio_match:
        holding = _get_holding(portfolio, state["ticker"])
        if holding:
            total_portfolio_value = sum(
                h.quantity * (h.current_price or h.avg_buy_price) for h in portfolio
            )
            holding_duration_days = (datetime.utcnow() - holding.created_at).days
            current_price = (
                state["price_data"].close if state.get("price_data") else holding.current_price
            )
            unrealised_pnl = (current_price - holding.avg_buy_price) * holding.quantity
            position_value = holding.quantity * current_price
            enriched = state.get("enriched_context")
            impact_high = enriched.impact_inr_high if enriched else None
            impact_pct = (
                abs(impact_high or 0) / total_portfolio_value * 100
                if total_portfolio_value > 0
                else 0.0
            )
            alert["personalized_opening"] = (
                f"You've held {holding.ticker} for {holding_duration_days} days "
                f"at ₹{holding.avg_buy_price:,.0f} avg. "
                f"Today's {sig.type} signal directly affects "
                f"your ₹{position_value / 100000:.1f}L position."
            )
            alert["holding_duration_days"] = holding_duration_days
            alert["unrealised_pnl_inr"] = round(unrealised_pnl, 2)
            alert["impact_pct_of_portfolio"] = round(impact_pct, 2)

    # Non-portfolio: clear impact fields
    if not portfolio_match:
        alert["estimated_impact_inr_low"] = None
        alert["estimated_impact_inr_high"] = None

    audit.append(
        AuditStep(
            agent="AlertGenerator",
            action="finalize_alert",
            output_summary=f"Alert: {alert['summary'][:100]}",
        )
    )

    return {
        **state,
        "alert": alert,
        "audit_trail": state.get("audit_trail", []) + audit,
    }
