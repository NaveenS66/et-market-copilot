"""
FilingScanner — detects unreported signals from NSE/BSE filings.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

from backend.models import AuditStep, FilingScanResult, PipelineState

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


async def scan_for_unreported_signals(ticker: str) -> FilingScanResult:
    """
    Step 1: Search NSE bulk deal filings directly via Tavily.
    Step 2: Cross-reference against news in last 24 hours.
    Returns FilingScanResult with is_unreported flag.
    """
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY", "")
    client = TavilyClient(api_key=api_key)

    # Step 1: NSE filing search
    try:
        filing_results = client.search(
            query=f"site:nseindia.com/companies-listing/corporate-filings/bulk-deals {ticker}",
            max_results=5,
            search_depth="basic",
            days=1,
        )
        filing_items = filing_results.get("results", [])
    except Exception:
        filing_items = []

    if not filing_items:
        return FilingScanResult(ticker=ticker, has_filing=False, is_unreported=False)

    filing_url = filing_items[0].get("url", "")

    # Step 2: Cross-reference news (exclude NSE/BSE domains)
    try:
        news_results = client.search(
            query=f"{ticker} bulk deal insider trade",
            max_results=5,
            search_depth="basic",
            days=1,
            exclude_domains=["nseindia.com", "bseindia.com"],
        )
        news_items = news_results.get("results", [])
    except Exception:
        news_items = []

    is_unreported = len(filing_items) > 0 and len(news_items) == 0

    return FilingScanResult(
        ticker=ticker,
        has_filing=True,
        filing_url=filing_url,
        is_unreported=is_unreported,
        news_count=len(news_items),
    )


def scan_for_unreported_signals_sync(ticker: str) -> FilingScanResult:
    """Synchronous wrapper for scan_for_unreported_signals."""
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY", "")
    client = TavilyClient(api_key=api_key)

    # Step 1: NSE filing search
    try:
        filing_results = client.search(
            query=f"site:nseindia.com/companies-listing/corporate-filings/bulk-deals {ticker}",
            max_results=5,
            search_depth="basic",
        )
        filing_items = filing_results.get("results", [])
    except Exception:
        filing_items = []

    if not filing_items:
        return FilingScanResult(ticker=ticker, has_filing=False, is_unreported=False)

    filing_url = filing_items[0].get("url", "")

    # Step 2: Cross-reference news
    try:
        news_results = client.search(
            query=f"{ticker} bulk deal insider trade",
            max_results=5,
            search_depth="basic",
        )
        news_items = [
            r for r in news_results.get("results", [])
            if "nseindia.com" not in r.get("url", "")
            and "bseindia.com" not in r.get("url", "")
        ]
    except Exception:
        news_items = []

    is_unreported = len(filing_items) > 0 and len(news_items) == 0

    return FilingScanResult(
        ticker=ticker,
        has_filing=True,
        filing_url=filing_url,
        is_unreported=is_unreported,
        news_count=len(news_items),
    )
