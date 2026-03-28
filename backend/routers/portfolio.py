"""
Portfolio router — CRUD for holdings with live price enrichment.
"""
from __future__ import annotations

import os

import yfinance as yf
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    return create_client(url, key)


class HoldingCreate(BaseModel):
    ticker: str
    quantity: float
    avg_buy_price: float


@router.get("")
def get_portfolio():
    """Fetch holdings from Supabase and enrich with live price data."""
    client = _get_supabase()
    result = client.table("holdings").select("*").eq("user_id", "demo_user").execute()
    holdings = result.data or []

    enriched = []
    for h in holdings:
        ticker = h["ticker"]
        current_price = 0.0
        day_change_pct = 0.0
        try:
            info = yf.Ticker(ticker).fast_info
            current_price = float(info.last_price or 0.0)
            day_change_pct = float(
                getattr(info, "regular_market_change_percent", None) or 0.0
            )
        except Exception:
            pass

        avg_buy_price = float(h.get("avg_buy_price", 0.0))
        quantity = float(h.get("quantity", 0.0))
        unrealised_pnl = (current_price - avg_buy_price) * quantity

        enriched.append({
            "id": h.get("id"),
            "ticker": ticker,
            "quantity": quantity,
            "avg_buy_price": avg_buy_price,
            "current_price": current_price,
            "day_change_pct": day_change_pct,
            "unrealised_pnl": unrealised_pnl,
            "created_at": h.get("created_at"),
        })

    return enriched


@router.post("/holding", status_code=201)
def add_holding(body: HoldingCreate):
    """Validate ticker via yfinance, then insert into Supabase."""
    ticker = body.ticker.strip().upper()

    # Validate ticker
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.last_price
        if price is None or price <= 0:
            raise ValueError("No price data")
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid or unrecognised ticker: {ticker}")

    client = _get_supabase()
    row = {
        "user_id": "demo_user",
        "ticker": ticker,
        "quantity": body.quantity,
        "avg_buy_price": body.avg_buy_price,
    }
    result = client.table("holdings").upsert(row, on_conflict="user_id,ticker").execute()
    return result.data[0] if result.data else row


@router.delete("/holding/{ticker}", status_code=200)
def delete_holding(ticker: str):
    """Delete a holding from Supabase."""
    ticker = ticker.strip().upper()
    client = _get_supabase()
    client.table("holdings").delete().eq("ticker", ticker).eq("user_id", "demo_user").execute()
    return {"deleted": ticker}
