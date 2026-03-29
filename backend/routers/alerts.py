"""
Alerts router — fetch alerts and audit trail from Supabase.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured")
    return create_client(url, key)


@router.get("")
def get_alerts():
    """Fetch alerts ordered by absolute impact (highest first), then recency. Limit 20."""
    try:
        client = _get_supabase()
        result = (
            client.table("alerts")
            .select("*")
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        rows = result.data or []
    except Exception:
        return []

    # Sort by abs(estimated_impact_inr_high) descending, nulls last
    def sort_key(row):
        val = row.get("estimated_impact_inr_high")
        return abs(val) if val is not None else -1

    rows.sort(key=sort_key, reverse=True)
    return rows[:20]


@router.get("/{alert_id}/audit")
def get_audit_trail(alert_id: str):
    """Fetch audit trail entries for a given alert_id."""
    try:
        client = _get_supabase()
        result = (
            client.table("audit_trail")
            .select("*")
            .eq("alert_id", alert_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return result.data or []
    except Exception:
        return []
