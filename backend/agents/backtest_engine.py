"""
BacktestEngine — computes real historical breakout success rates from yfinance data.
No hardcoded or estimated values; uses only actual price history.
"""
from __future__ import annotations

import yfinance as yf
import pandas as pd

from backend.models import BacktestResult


def compute_breakout_success_rate(ticker: str, years: int = 2) -> BacktestResult:
    """
    Scan yfinance price history for breakout events and compute success rate.

    A breakout is: close >= rolling 52W high (252-day, no lookahead) AND
                   volume > 20-day avg volume * 1.2

    Success: price > 5% higher 30 calendar days after the breakout.

    Returns BacktestResult with success_rate_pct=None if sample_size < 1.
    """
    try:
        hist = yf.Ticker(ticker).history(period=f"{years}y")
    except Exception as e:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note=f"yfinance error: {e}",
        )

    if hist.empty:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="No historical data",
        )

    # Compute rolling indicators with shift(1) to avoid lookahead bias
    hist["rolling_52w_high"] = hist["Close"].rolling(252).max().shift(1)
    hist["avg_vol_20d"] = hist["Volume"].rolling(20).mean().shift(1)
    hist = hist.dropna(subset=["rolling_52w_high", "avg_vol_20d"])

    # Identify breakout days
    breakouts = hist[
        (hist["Close"] >= hist["rolling_52w_high"])
        & (hist["Volume"] > hist["avg_vol_20d"] * 1.2)
    ]

    if len(breakouts) == 0:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="No breakout events found",
        )

    gains: list[float] = []
    losses: list[float] = []

    for dt in breakouts.index:
        future_date = dt + pd.Timedelta(days=30)
        future_slice = hist[hist.index >= future_date]
        if future_slice.empty:
            continue
        future_price = float(future_slice.iloc[0]["Close"])
        entry_price = float(hist.loc[dt, "Close"])
        pct_change = (future_price - entry_price) / entry_price * 100
        if pct_change > 5:
            gains.append(pct_change)
        else:
            losses.append(pct_change)

    total = len(gains) + len(losses)
    if total == 0:
        return BacktestResult(
            ticker=ticker,
            success_rate_pct=None,
            sample_size=0,
            avg_gain_pct=None,
            avg_loss_pct=None,
            note="Insufficient forward data",
        )

    return BacktestResult(
        ticker=ticker,
        success_rate_pct=round(len(gains) / total * 100, 1),
        sample_size=total,
        avg_gain_pct=round(sum(gains) / len(gains), 2) if gains else None,
        avg_loss_pct=round(sum(losses) / len(losses), 2) if losses else None,
        note=None,
    )
