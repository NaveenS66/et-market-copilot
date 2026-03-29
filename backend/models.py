"""
Core data models for ET Investor Copilot.
All dataclasses and TypedDicts as specified in the design document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TypedDict


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Holding:
    ticker: str
    quantity: float
    avg_buy_price: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    current_price: float = 0.0  # populated at portfolio view time


@dataclass
class PriceData:
    ticker: str
    close: float
    volume: int
    avg_volume_20d: float
    week52_high: float
    week52_low: float
    rsi14: float
    source_url: str
    retrieved_at: datetime


@dataclass
class BulkDeal:
    ticker: str
    client_name: str
    deal_type: str          # "BUY" | "SELL"
    quantity: int
    price: float
    pct_equity: float
    is_promoter: bool
    filing_url: str
    deal_date: date


@dataclass
class Flag:
    name: str               # e.g. "overbought", "fii_reduction"
    value: float
    direction: str          # "bullish" | "bearish"


@dataclass
class Signal:
    type: str               # "breakout" | "bulk_deal_promoter_sell" | "macro_event"
    ticker: str
    flags: list[Flag] = field(default_factory=list)
    is_conflicted: bool = False
    is_unreported: bool = False  # set by FilingScanner (Requirement 16)


@dataclass
class ConflictReport:
    ticker: str
    bull_indicators: list[Flag] = field(default_factory=list)
    bear_indicators: list[Flag] = field(default_factory=list)


@dataclass
class EnrichedContext:
    portfolio_match: bool
    eps_trend: list[float] | None = None
    mgmt_commentary: str | None = None
    breakout_success_rate: float | None = None
    impact_inr_low: float | None = None
    impact_inr_high: float | None = None
    backtest_result: BacktestResult | None = None  # full backtest (Requirement 14)
    impact_pct_of_portfolio: float | None = None   # Requirement 15
    priority_rank: int | None = None               # for macro event ranking


@dataclass
class BacktestResult:
    ticker: str
    success_rate_pct: float | None   # null if sample_size < 1
    sample_size: int
    avg_gain_pct: float | None
    avg_loss_pct: float | None
    note: str | None = None


@dataclass
class FilingScanResult:
    ticker: str
    has_filing: bool
    filing_url: str | None = None
    is_unreported: bool = False
    news_count: int = 0


@dataclass
class AuditStep:
    agent: str
    action: str
    source_urls: list[str] = field(default_factory=list)
    model_used: str | None = None
    fallback_occurred: bool = False
    fallback_reason: str | None = None
    output_summary: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    # Model routing fields (Requirement 13)
    task_type: str | None = None
    estimated_cost_saved: float | None = None


@dataclass
class NewsResult:
    ticker: str
    title: str
    url: str
    snippet: str
    retrieved_at: datetime


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class EvidenceItem(TypedDict):
    label: str          # e.g. "RSI(14) value"
    value: str          # e.g. "78.3 as of 2026-01-15"
    source_name: str    # e.g. "NSE Bulk Deal Disclosure"
    source_url: str
    retrieved_at: str


class AlertResponse(TypedDict):
    alert_id: str
    ticker: str
    signal_type: str            # "bulk_deal" | "breakout_conflicted" | "macro_event"
    summary: str
    recommended_action: str
    confidence: str             # "Low" | "Medium" | "High"
    estimated_impact_inr_low: float | None
    estimated_impact_inr_high: float | None
    evidence_chain: list[EvidenceItem]
    bull_case: str | None
    bear_case: str | None
    what_to_watch: list[str] | None
    disclaimer: str
    # Personalization fields (Requirement 15)
    personalized_opening: str | None
    holding_duration_days: int | None
    unrealised_pnl_inr: float | None
    impact_pct_of_portfolio: float | None
    # Unreported signal flag (Requirement 16)
    unreported_signal: bool
    created_at: str
    priority_rank: int | None


class RunAnalysisRequest(TypedDict):
    portfolio_id: str
    tickers: list[str]      # optional override; defaults to all holdings
    scenario: str | None    # "bulk_deal" | "breakout" | "macro" | None


class PipelineState(TypedDict):
    # Input
    ticker: str
    portfolio: list[Holding]
    scenario_hint: str | None

    # DataFetcher output
    price_data: PriceData | None
    bulk_deals: list[BulkDeal]
    news_results: list[NewsResult]

    # FilingScanner output (Requirement 16)
    filing_scan_result: FilingScanResult | None

    # SignalDetector output
    signals: list[Signal]
    conflict_report: ConflictReport | None

    # ContextEnricher output
    enriched_context: EnrichedContext | None
    portfolio_match: bool

    # AlertGenerator output
    alert: AlertResponse | None

    # Audit
    audit_trail: list[AuditStep]
    errors: list[str]
