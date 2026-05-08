"""Lightweight market data adapter. yfinance default; Polygon when key set."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from loguru import logger

from .config import settings


def get_prices(ticker: str, lookback_days: int = 365) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=lookback_days)
    if settings.polygon_api_key:
        try:
            return _polygon(ticker, start, end)
        except Exception as e:
            logger.warning(f"polygon failed, falling back to yfinance: {e}")
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    df.index.name = "date"
    return df


def _polygon(ticker: str, start: date, end: date) -> pd.DataFrame:
    import httpx

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/"
        f"{start.isoformat()}/{end.isoformat()}?adjusted=true&sort=asc&limit=50000"
        f"&apiKey={settings.polygon_api_key}"
    )
    r = httpx.get(url, timeout=30.0)
    r.raise_for_status()
    rows = r.json().get("results", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    return df.set_index("date")[["Open", "High", "Low", "Close", "Volume"]]


def quick_stats(ticker: str) -> dict:
    df = get_prices(ticker, lookback_days=180)
    if df.empty:
        return {"ticker": ticker, "error": "no data"}
    last = float(df["Close"].iloc[-1])
    chg_5 = float(df["Close"].pct_change(5).iloc[-1])
    chg_20 = float(df["Close"].pct_change(20).iloc[-1])
    vol_20 = float(df["Close"].pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5))
    sma_20 = float(df["Close"].rolling(20).mean().iloc[-1])
    sma_50 = float(df["Close"].rolling(50).mean().iloc[-1])
    return {
        "ticker": ticker,
        "last": last,
        "ret_5d": chg_5,
        "ret_20d": chg_20,
        "ann_vol_20d": vol_20,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "above_50dma": last > sma_50,
    }
