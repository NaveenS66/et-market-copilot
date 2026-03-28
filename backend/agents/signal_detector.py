"""
SignalDetector Agent — pure deterministic signal classification, no LLM calls.
"""
from __future__ import annotations

from backend.models import (
    AuditStep,
    BulkDeal,
    ConflictReport,
    Flag,
    NewsResult,
    PipelineState,
    PriceData,
    Signal,
)

# ---------------------------------------------------------------------------
# Sector map: NSE ticker → sector
# ---------------------------------------------------------------------------
SECTOR_MAP: dict[str, str] = {
    "HDFCBANK.NS": "banking",
    "HDFCBANK": "banking",
    "ICICIBANK.NS": "banking",
    "ICICIBANK": "banking",
    "SBIN.NS": "banking",
    "SBIN": "banking",
    "KOTAKBANK.NS": "banking",
    "KOTAKBANK": "banking",
    "AXISBANK.NS": "banking",
    "AXISBANK": "banking",
    "INFY.NS": "IT",
    "INFY": "IT",
    "TCS.NS": "IT",
    "TCS": "IT",
    "WIPRO.NS": "IT",
    "WIPRO": "IT",
    "HCLTECH.NS": "IT",
    "HCLTECH": "IT",
    "TECHM.NS": "IT",
    "TECHM": "IT",
    "RELIANCE.NS": "energy",
    "RELIANCE": "energy",
    "ONGC.NS": "energy",
    "ONGC": "energy",
    "BPCL.NS": "energy",
    "BPCL": "energy",
    "IOC.NS": "energy",
    "IOC": "energy",
    "SUNPHARMA.NS": "pharma",
    "SUNPHARMA": "pharma",
    "DRREDDY.NS": "pharma",
    "DRREDDY": "pharma",
    "CIPLA.NS": "pharma",
    "CIPLA": "pharma",
    "TATAMOTORS.NS": "auto",
    "TATAMOTORS": "auto",
    "MARUTI.NS": "auto",
    "MARUTI": "auto",
    "M&M.NS": "auto",
    "M&M": "auto",
    "BAJFINANCE.NS": "NBFC",
    "BAJFINANCE": "NBFC",
    "BAJAJFINSV.NS": "NBFC",
    "BAJAJFINSV": "NBFC",
}

# Macro keywords → affected sectors
MACRO_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "RBI": ["banking", "NBFC"],
    "rate": ["banking", "NBFC", "IT"],
    "SEBI": ["banking", "NBFC", "IT", "energy", "pharma", "auto"],
    "inflation": ["banking", "NBFC", "energy"],
    "repo": ["banking", "NBFC"],
    "CRR": ["banking"],
    "SLR": ["banking"],
    "FII": ["banking", "IT", "energy"],
    "FDI": ["energy", "IT"],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _fii_reduction_detected(state: PipelineState) -> bool:
    """Check if news mentions FII reduction."""
    keywords = ["fii reduction", "fii selling", "fii outflow", "foreign institutional",
                "fii holding decreased", "fii stake reduced", "fii cut"]
    for news in state.get("news_results", []):
        text = f"{news.title} {news.snippet}".lower()
        if any(kw in text for kw in keywords):
            return True
    return False


def _detect_macro_keywords(state: PipelineState) -> list[str]:
    """Return list of macro keywords found in news."""
    found: list[str] = []
    for news in state.get("news_results", []):
        text = f"{news.title} {news.snippet}"
        for kw in MACRO_SECTOR_KEYWORDS:
            if kw.lower() in text.lower() and kw not in found:
                found.append(kw)
    return found


def _get_affected_sectors(macro_keywords: list[str]) -> set[str]:
    """Get set of affected sectors from macro keywords."""
    sectors: set[str] = set()
    for kw in macro_keywords:
        sectors.update(MACRO_SECTOR_KEYWORDS.get(kw, []))
    return sectors


def _get_portfolio_tickers_in_sectors(
    portfolio: list, affected_sectors: set[str]
) -> list[str]:
    """Return portfolio tickers whose sector is in affected_sectors."""
    tickers: list[str] = []
    for holding in portfolio:
        sector = SECTOR_MAP.get(holding.ticker)
        if sector and sector in affected_sectors:
            tickers.append(holding.ticker)
    return tickers


def _build_conflict_report(sig: Signal) -> ConflictReport:
    bull = [f for f in sig.flags if f.direction == "bullish"]
    bear = [f for f in sig.flags if f.direction == "bearish"]
    return ConflictReport(
        ticker=sig.ticker,
        bull_indicators=bull,
        bear_indicators=bear,
    )


# ---------------------------------------------------------------------------
# signal_detector_node — LangGraph node
# ---------------------------------------------------------------------------

def signal_detector_node(state: PipelineState) -> PipelineState:
    """Deterministic signal classification — no LLM calls."""
    ticker = state["ticker"]
    price_data: PriceData | None = state.get("price_data")
    bulk_deals: list[BulkDeal] = state.get("bulk_deals", [])
    portfolio = state.get("portfolio", [])
    audit: list[AuditStep] = []

    signals: list[Signal] = []
    conflict_report: ConflictReport | None = None

    # ------------------------------------------------------------------
    # 1. Breakout detection
    # ------------------------------------------------------------------
    if (
        price_data is not None
        and price_data.close >= price_data.week52_high
        and price_data.volume > price_data.avg_volume_20d * 1.2
    ):
        sig = Signal(type="breakout", ticker=ticker, flags=[])

        # Overbought flag
        if price_data.rsi14 > 70:
            sig.flags.append(
                Flag(name="overbought", value=price_data.rsi14, direction="bearish")
            )

        # FII reduction flag (keyword check on news)
        if _fii_reduction_detected(state):
            sig.flags.append(
                Flag(name="fii_reduction", value=-1.0, direction="bearish")
            )

        # Bullish flag for the breakout itself
        sig.flags.append(
            Flag(name="breakout_volume", value=price_data.volume / price_data.avg_volume_20d, direction="bullish")
        )

        signals.append(sig)
        audit.append(
            AuditStep(
                agent="SignalDetector",
                action="detect_breakout",
                output_summary=(
                    f"Breakout: close={price_data.close} >= 52W_high={price_data.week52_high}, "
                    f"vol={price_data.volume} > avg*1.2={price_data.avg_volume_20d * 1.2:.0f}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # 2. Promoter sell bulk deal detection
    # ------------------------------------------------------------------
    for deal in bulk_deals:
        if deal.is_promoter and deal.pct_equity > 1.0:
            sig = Signal(
                type="bulk_deal_promoter_sell",
                ticker=ticker,
                flags=[Flag(name="promoter_sell", value=deal.pct_equity, direction="bearish")],
            )
            signals.append(sig)
            audit.append(
                AuditStep(
                    agent="SignalDetector",
                    action="detect_promoter_sell",
                    source_urls=[deal.filing_url],
                    output_summary=(
                        f"Promoter sell: {deal.client_name}, {deal.pct_equity:.2f}% equity"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 3. Conflict detection: ≥ 2 bearish flags → is_conflicted
    # ------------------------------------------------------------------
    for sig in signals:
        bearish_count = sum(1 for f in sig.flags if f.direction == "bearish")
        if bearish_count >= 2:
            sig.is_conflicted = True
            conflict_report = _build_conflict_report(sig)
            audit.append(
                AuditStep(
                    agent="SignalDetector",
                    action="detect_conflict",
                    output_summary=(
                        f"Conflict detected: {bearish_count} bearish flags on {sig.type}"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 4. Macro event detection
    # ------------------------------------------------------------------
    macro_keywords = _detect_macro_keywords(state)
    if macro_keywords:
        affected_sectors = _get_affected_sectors(macro_keywords)
        affected_tickers = _get_portfolio_tickers_in_sectors(portfolio, affected_sectors)

        for affected_ticker in affected_tickers:
            macro_sig = Signal(
                type="macro_event",
                ticker=affected_ticker,
                flags=[Flag(name="macro_keyword", value=0.0, direction="bearish")],
            )
            signals.append(macro_sig)

        audit.append(
            AuditStep(
                agent="SignalDetector",
                action="detect_macro_event",
                output_summary=(
                    f"Macro keywords: {macro_keywords}, "
                    f"affected tickers: {affected_tickers}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # 5. Wire unreported signal flag from FilingScanner
    # ------------------------------------------------------------------
    filing_scan = state.get("filing_scan_result")
    if filing_scan and filing_scan.is_unreported:
        for sig in signals:
            if sig.type in ("bulk_deal_promoter_sell", "breakout"):
                sig.is_unreported = True

    return {
        **state,
        "signals": signals,
        "conflict_report": conflict_report,
        "audit_trail": state.get("audit_trail", []) + audit,
    }
