"""
Analysis router — triggers the LangGraph pipeline for portfolio tickers.
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

from backend.models import Holding
from backend.orchestrator import run_pipeline

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

_executor = ThreadPoolExecutor(max_workers=4)


def _get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    return create_client(url, key)


def _load_portfolio() -> list[Holding]:
    """Load holdings from Supabase and return as Holding objects."""
    client = _get_supabase()
    result = client.table("holdings").select("*").eq("user_id", "demo_user").execute()
    holdings = []
    for row in (result.data or []):
        holdings.append(
            Holding(
                ticker=row["ticker"],
                quantity=float(row["quantity"]),
                avg_buy_price=float(row["avg_buy_price"]),
            )
        )
    return holdings


class RunAnalysisRequest(BaseModel):
    tickers: Optional[List[str]] = None
    scenario: Optional[str] = None


class SingleTickerRequest(BaseModel):
    ticker: str
    scenario: Optional[str] = None


@router.post("/run")
async def run_analysis(body: RunAnalysisRequest):
    """Run the full pipeline for each ticker in the portfolio (or provided list)."""
    portfolio = _load_portfolio()

    tickers = body.tickers
    if not tickers:
        tickers = [h.ticker for h in portfolio]

    if not tickers:
        return []

    loop = asyncio.get_event_loop()

    async def run_one(ticker: str):
        return await loop.run_in_executor(
            _executor,
            run_pipeline,
            ticker,
            portfolio,
            body.scenario,
        )

    results = await asyncio.gather(*[run_one(t) for t in tickers], return_exceptions=True)

    alerts = []
    for r in results:
        if isinstance(r, Exception):
            continue
        alert = r.get("alert") if isinstance(r, dict) else None
        if alert:
            alerts.append(alert)

    return alerts


@router.post("/ticker")
async def run_ticker_analysis(body: SingleTickerRequest):
    """Run the pipeline for a single ticker."""
    portfolio = _load_portfolio()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        run_pipeline,
        body.ticker,
        portfolio,
        body.scenario,
    )

    alert = result.get("alert") if isinstance(result, dict) else None
    if alert is None:
        raise HTTPException(status_code=404, detail="No alert generated for this ticker")
    return alert
