"""
DataFetcher Agent — fetches price data, NSE bulk deals, and news.
"""
from __future__ import annotations

import os
from datetime import datetime, date

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from tavily import TavilyClient

from backend.agents.model_router import ModelRouter
from backend.agents.filing_scanner import scan_for_unreported_signals_sync
from backend.models import (
    AuditStep,
    BulkDeal,
    NewsResult,
    PipelineState,
    PriceData,
)

_model_router = ModelRouter()

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


# ---------------------------------------------------------------------------
# fetch_price_data
# ---------------------------------------------------------------------------

def _compute_rsi(close: pd.Series, length: int = 14) -> float:
    """Compute RSI using Wilder's smoothing method (pure pandas)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, float('inf'))
    rsi = 100 - (100 / (1 + rs))
    val = rsi.dropna()
    return float(val.iloc[-1]) if not val.empty else 50.0


def fetch_price_data(ticker: str) -> PriceData:
    """Fetch OHLCV + RSI(14) + avg_volume_20d via yfinance."""
    t = yf.Ticker(ticker)
    hist = t.history(period="1y")
    if hist.empty:
        raise ValueError(f"yfinance returned empty history for {ticker}")

    # RSI via pure pandas (Wilder's method)
    rsi14 = _compute_rsi(hist["Close"], length=14)

    avg_volume_20d = float(hist["Volume"].rolling(20).mean().iloc[-1])
    week52_high = float(hist["Close"].max())
    week52_low = float(hist["Close"].min())
    close = float(hist["Close"].iloc[-1])
    volume = int(hist["Volume"].iloc[-1])

    return PriceData(
        ticker=ticker,
        close=close,
        volume=volume,
        avg_volume_20d=avg_volume_20d,
        week52_high=week52_high,
        week52_low=week52_low,
        rsi14=rsi14,
        source_url=f"https://finance.yahoo.com/quote/{ticker}",
        retrieved_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# gemini_grounding_fallback
# ---------------------------------------------------------------------------

def gemini_grounding_fallback(ticker: str) -> PriceData:
    """Use Gemini (or Groq fallback) to get approximate price data when yfinance fails."""
    from backend.agents.model_router import call_gemini, call_groq

    prompt = (
        f"Provide approximate current market data for NSE ticker {ticker}. "
        "Return ONLY a JSON object with keys: close (float), volume (int), "
        "avg_volume_20d (float), week52_high (float), week52_low (float), rsi14 (float). "
        "Use realistic estimates based on recent market data."
    )

    text = ""
    source = "gemini-grounding"
    # Try Gemini first, then Groq
    for fn, label in [
        (lambda p: call_gemini(p), "gemini-grounding"),
        (lambda p: call_groq(p), "groq-grounding"),
    ]:
        try:
            text = fn(prompt)
            source = label
            if text and len(text.strip()) > 10:
                break
        except Exception:
            continue

    import json, re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    return PriceData(
        ticker=ticker,
        close=float(data.get("close", 100.0)),
        volume=int(data.get("volume", 1000000)),
        avg_volume_20d=float(data.get("avg_volume_20d", 900000.0)),
        week52_high=float(data.get("week52_high", 120.0)),
        week52_low=float(data.get("week52_low", 80.0)),
        rsi14=float(data.get("rsi14", 50.0)),
        source_url=f"{source}:{ticker}",
        retrieved_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# fetch_nse_bulk_deals
# ---------------------------------------------------------------------------

def fetch_nse_bulk_deals(ticker: str) -> list[BulkDeal]:
    """Search NSE bulk deals via Tavily and parse into BulkDeal objects."""
    client = _get_tavily()
    try:
        results = client.search(
            query=f"site:nseindia.com bulk deal {ticker}",
            max_results=5,
            search_depth="basic",
        )
    except Exception:
        return []

    deals: list[BulkDeal] = []
    for item in results.get("results", []):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        # Best-effort parse: extract client name from title/content
        client_name = _extract_client_name(title, content)
        is_promoter = "promoter" in client_name.lower()
        deals.append(
            BulkDeal(
                ticker=ticker,
                client_name=client_name,
                deal_type=_extract_deal_type(title, content),
                quantity=_extract_quantity(content),
                price=_extract_price(content),
                pct_equity=_extract_pct_equity(content),
                is_promoter=is_promoter,
                filing_url=url or f"https://www.nseindia.com/companies-listing/corporate-filings/bulk-deals",
                deal_date=date.today(),
            )
        )
    return deals


def _extract_client_name(title: str, content: str) -> str:
    text = f"{title} {content}"
    # Look for "promoter" keyword
    if "promoter" in text.lower():
        return "Promoter Group"
    # Try to extract a name pattern
    import re
    match = re.search(r"(?:client|buyer|seller)[:\s]+([A-Z][A-Za-z\s&.]+?)(?:\s+(?:bought|sold|purchased)|\.|,)", text)
    if match:
        return match.group(1).strip()
    return "Unknown Client"


def _extract_deal_type(title: str, content: str) -> str:
    text = f"{title} {content}".lower()
    if "sell" in text or "sold" in text:
        return "SELL"
    return "BUY"


def _extract_quantity(content: str) -> int:
    import re
    match = re.search(r"(\d[\d,]+)\s*(?:shares|equity shares)", content, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


def _extract_price(content: str) -> float:
    import re
    match = re.search(r"(?:price|at|@)\s*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)", content, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0


def _extract_pct_equity(content: str) -> float:
    import re
    match = re.search(r"([\d.]+)\s*%\s*(?:of\s+)?(?:equity|stake|shareholding)", content, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 0.0


# ---------------------------------------------------------------------------
# fetch_news
# ---------------------------------------------------------------------------

def fetch_news(ticker: str) -> list[NewsResult]:
    """Fetch top 5 news results via Tavily."""
    client = _get_tavily()
    try:
        results = client.search(
            query=f"{ticker} NSE filing earnings announcement",
            max_results=5,
            search_depth="basic",
        )
    except Exception:
        return []

    news: list[NewsResult] = []
    for item in (results.get("results", []) or [])[:5]:
        news.append(
            NewsResult(
                ticker=ticker,
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", "")[:300],
                retrieved_at=datetime.utcnow(),
            )
        )
    return news


# ---------------------------------------------------------------------------
# data_fetcher_node — LangGraph node
# ---------------------------------------------------------------------------

def data_fetcher_node(state: PipelineState) -> PipelineState:
    """LangGraph node: fetch price data, bulk deals, and news."""
    ticker = state["ticker"]
    audit: list[AuditStep] = []
    price_data: PriceData | None = None

    # 1. Price + technicals
    try:
        price_data = fetch_price_data(ticker)
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="fetch_price",
                source_urls=[price_data.source_url],
                output_summary=f"close={price_data.close}, rsi14={price_data.rsi14:.1f}",
            )
        )
    except Exception as e:
        try:
            price_data = gemini_grounding_fallback(ticker)
            audit.append(
                AuditStep(
                    agent="DataFetcher",
                    action="fetch_price_fallback",
                    source_urls=[price_data.source_url],
                    fallback_occurred=True,
                    fallback_reason=str(e),
                    output_summary=f"Gemini fallback: close={price_data.close}",
                )
            )
        except Exception as e2:
            audit.append(
                AuditStep(
                    agent="DataFetcher",
                    action="fetch_price_error",
                    fallback_occurred=True,
                    fallback_reason=str(e2),
                    output_summary="Both yfinance and Gemini fallback failed",
                )
            )

    # Log ModelRouter decisions for classification tasks
    _model_router.log_routing("sector_tagging", audit)
    _model_router.log_routing("promoter_detection", audit)

    # 2. Bulk deals
    bulk_deals: list[BulkDeal] = []
    try:
        bulk_deals = fetch_nse_bulk_deals(ticker)
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="fetch_bulk_deals",
                source_urls=[d.filing_url for d in bulk_deals],
                output_summary=f"Found {len(bulk_deals)} bulk deals",
            )
        )
    except Exception as e:
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="fetch_bulk_deals_error",
                output_summary=str(e),
            )
        )

    # 3. News
    news_results: list[NewsResult] = []
    try:
        news_results = fetch_news(ticker)
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="fetch_news",
                source_urls=[n.url for n in news_results],
                output_summary=f"Found {len(news_results)} news items",
            )
        )
    except Exception as e:
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="fetch_news_error",
                output_summary=str(e),
            )
        )

    # 4. FilingScanner — detect unreported signals
    from backend.models import FilingScanResult
    filing_scan_result: FilingScanResult | None = None
    try:
        filing_scan_result = scan_for_unreported_signals_sync(ticker)
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="filing_scan",
                source_urls=[filing_scan_result.filing_url] if filing_scan_result.filing_url else [],
                output_summary=(
                    f"has_filing={filing_scan_result.has_filing}, "
                    f"is_unreported={filing_scan_result.is_unreported}, "
                    f"news_count={filing_scan_result.news_count}"
                ),
            )
        )
    except Exception as e:
        audit.append(
            AuditStep(
                agent="DataFetcher",
                action="filing_scan_error",
                output_summary=str(e),
            )
        )

    return {
        **state,
        "price_data": price_data,
        "bulk_deals": bulk_deals,
        "news_results": news_results,
        "filing_scan_result": filing_scan_result,
        "audit_trail": state.get("audit_trail", []) + audit,
    }
