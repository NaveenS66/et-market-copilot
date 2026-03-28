"""
Pre-populated PipelineState fixtures for the three judging scenarios.
Data is realistic but hardcoded for demo reliability — no external API calls needed.
"""
from __future__ import annotations

from datetime import date, datetime

from backend.models import (
    BulkDeal,
    FilingScanResult,
    Holding,
    NewsResult,
    PipelineState,
    PriceData,
)

SCENARIO_BULK_DEAL: dict = {
    "ticker": "HDFCBANK.NS",
    "portfolio": [
        Holding(ticker="HDFCBANK.NS", quantity=100, avg_buy_price=1650.0, current_price=1720.0)
    ],
    "scenario_hint": "bulk_deal",
    "price_data": PriceData(
        ticker="HDFCBANK.NS", close=1720.0, volume=8500000,
        avg_volume_20d=6200000.0, week52_high=1850.0, week52_low=1420.0,
        rsi14=52.3, source_url="https://www.nseindia.com/companies-listing/corporate-filings/bulk-deals",
        retrieved_at=datetime.utcnow()
    ),
    "bulk_deals": [
        BulkDeal(
            ticker="HDFCBANK.NS", client_name="HDFC Promoter Group",
            deal_type="SELL", quantity=21000000, price=1618.0,
            pct_equity=4.2, is_promoter=True,
            filing_url="https://www.nseindia.com/companies-listing/corporate-filings/bulk-deals",
            deal_date=date.today()
        )
    ],
    "news_results": [],
    "filing_scan_result": FilingScanResult(
        ticker="HDFCBANK.NS", has_filing=True,
        filing_url="https://www.nseindia.com/companies-listing/corporate-filings/bulk-deals",
        is_unreported=True, news_count=0
    ),
    "signals": [],
    "conflict_report": None,
    "enriched_context": None,
    "portfolio_match": False,
    "alert": None,
    "audit_trail": [],
    "errors": [],
}

SCENARIO_BREAKOUT_CONFLICTED: dict = {
    "ticker": "INFY.NS",
    "portfolio": [
        Holding(ticker="INFY.NS", quantity=150, avg_buy_price=1450.0, current_price=1892.0)
    ],
    "scenario_hint": "breakout",
    "price_data": PriceData(
        ticker="INFY.NS", close=1892.0, volume=12400000,
        avg_volume_20d=8100000.0, week52_high=1890.0, week52_low=1320.0,
        rsi14=78.3, source_url="https://finance.yahoo.com/quote/INFY.NS",
        retrieved_at=datetime.utcnow()
    ),
    "bulk_deals": [],
    "news_results": [
        NewsResult(
            ticker="INFY.NS",
            title="FII selling in IT stocks as FII holding decreased in Infosys",
            url="https://economictimes.indiatimes.com/markets/stocks/news/fii-selling-it",
            snippet="Foreign institutional investors reduced stake in Infosys by 2.1% QoQ",
            retrieved_at=datetime.utcnow()
        )
    ],
    "filing_scan_result": None,
    "signals": [],
    "conflict_report": None,
    "enriched_context": None,
    "portfolio_match": False,
    "alert": None,
    "audit_trail": [],
    "errors": [],
}

SCENARIO_MACRO_DUAL: dict = {
    "ticker": "HDFCBANK.NS",
    "portfolio": [
        Holding(ticker="HDFCBANK.NS", quantity=100, avg_buy_price=1650.0, current_price=1720.0),
        Holding(ticker="INFY.NS", quantity=150, avg_buy_price=1450.0, current_price=1892.0),
        Holding(ticker="RELIANCE.NS", quantity=50, avg_buy_price=2800.0, current_price=2950.0),
        Holding(ticker="TCS.NS", quantity=30, avg_buy_price=3800.0, current_price=4100.0),
        Holding(ticker="SBIN.NS", quantity=200, avg_buy_price=780.0, current_price=820.0),
        Holding(ticker="SUNPHARMA.NS", quantity=80, avg_buy_price=1200.0, current_price=1350.0),
        Holding(ticker="TATAMOTORS.NS", quantity=120, avg_buy_price=950.0, current_price=1020.0),
        Holding(ticker="BAJFINANCE.NS", quantity=25, avg_buy_price=6800.0, current_price=7200.0),
    ],
    "scenario_hint": "macro",
    "price_data": PriceData(
        ticker="HDFCBANK.NS", close=1720.0, volume=5000000,
        avg_volume_20d=6200000.0, week52_high=1850.0, week52_low=1420.0,
        rsi14=48.0, source_url="https://finance.yahoo.com/quote/HDFCBANK.NS",
        retrieved_at=datetime.utcnow()
    ),
    "bulk_deals": [],
    "news_results": [
        NewsResult(
            ticker="HDFCBANK.NS",
            title="RBI cuts repo rate by 25bps to 6.25% — banking sector to benefit",
            url="https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
            snippet="Reserve Bank of India reduces repo rate by 25 basis points in monetary policy review",
            retrieved_at=datetime.utcnow()
        ),
        NewsResult(
            ticker="INFY.NS",
            title="SEBI tightens F&O regulations — IT sector faces compliance burden",
            url="https://sebi.gov.in/legal/circulars/mar-2026/circular",
            snippet="SEBI introduces new regulations affecting derivatives trading in IT sector stocks",
            retrieved_at=datetime.utcnow()
        ),
    ],
    "filing_scan_result": None,
    "signals": [],
    "conflict_report": None,
    "enriched_context": None,
    "portfolio_match": False,
    "alert": None,
    "audit_trail": [],
    "errors": [],
}

SCENARIOS = {
    "bulk_deal": SCENARIO_BULK_DEAL,
    "breakout": SCENARIO_BREAKOUT_CONFLICTED,
    "macro": SCENARIO_MACRO_DUAL,
}
