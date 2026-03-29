"""
Portfolio router — CRUD for holdings with live price enrichment.
"""
from __future__ import annotations

import os
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# In-memory fallback store when Supabase is unreachable
_memory_holdings: dict[str, dict] = {}


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
    """Fetch holdings from Supabase (fallback to memory) and enrich with live price data."""
    holdings = []
    try:
        client = _get_supabase()
        result = client.table("holdings").select("*").eq("user_id", "demo_user").execute()
        holdings = result.data or []
        # Sync memory store from Supabase
        for h in holdings:
            _memory_holdings[h["ticker"]] = h
    except Exception:
        # Supabase unreachable — use in-memory store
        holdings = list(_memory_holdings.values())

    enriched = []
    for h in holdings:
        ticker = h["ticker"]
        current_price = 0.0
        day_change_pct = 0.0
        try:
            t = yf.Ticker(ticker)
            # Try fast_info first, fall back to history for NSE tickers
            try:
                current_price = float(t.fast_info.last_price or 0.0)
                day_change_pct = float(getattr(t.fast_info, "regular_market_change_percent", None) or 0.0)
            except Exception:
                pass
            if current_price <= 0:
                hist = t.history(period="5d")
                if not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        prev = float(hist["Close"].iloc[-2])
                        day_change_pct = (current_price - prev) / prev * 100 if prev > 0 else 0.0
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

    # Validate ticker — try fast_info first, fall back to history check
    try:
        t = yf.Ticker(ticker)
        price = None
        try:
            price = t.fast_info.last_price
        except Exception:
            pass
        # fast_info can return None for NSE tickers — fall back to history
        if not price or price <= 0:
            hist = t.history(period="5d")
            if hist.empty:
                raise ValueError("No price data from history either")
            price = float(hist["Close"].iloc[-1])
        if price <= 0:
            raise ValueError("Price is zero or negative")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid or unrecognised ticker: {ticker}")

    try:
        client = _get_supabase()
        row = {
            "user_id": "demo_user",
            "ticker": ticker,
            "quantity": body.quantity,
            "avg_buy_price": body.avg_buy_price,
        }
        result = client.table("holdings").upsert(row, on_conflict="user_id,ticker").execute()
        saved = result.data[0] if result.data else row
        _memory_holdings[ticker] = saved
        return saved
    except Exception:
        # Supabase unreachable — save to memory
        row = {
            "id": ticker,
            "user_id": "demo_user",
            "ticker": ticker,
            "quantity": body.quantity,
            "avg_buy_price": body.avg_buy_price,
            "created_at": datetime.utcnow().isoformat(),
        }
        _memory_holdings[ticker] = row
        return row


@router.delete("/holding/{ticker}", status_code=200)
def delete_holding(ticker: str):
    """Delete a holding from Supabase and memory."""
    ticker = ticker.strip().upper()
    _memory_holdings.pop(ticker, None)
    try:
        client = _get_supabase()
        client.table("holdings").delete().eq("ticker", ticker).eq("user_id", "demo_user").execute()
    except Exception:
        pass
    return {"deleted": ticker}
