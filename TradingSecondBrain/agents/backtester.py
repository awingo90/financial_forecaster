"""Tiny, deterministic backtester used by the Trader agent.

We deliberately keep this simple: a rules-driven SMA-cross + ATR-stop backtest
that produces sample size, Sharpe, max drawdown, and regime coverage. This is
*not* meant to be a research-grade backtester — it's a sanity-check the agent
must pass before raising confidence above 70 (per VAULT.md §6).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .market_data import get_prices


@dataclass(slots=True)
class BacktestResult:
    ticker: str
    sample_size: int
    sharpe: float
    max_dd: float
    regimes_covered: list[str]
    cagr: float
    win_rate: float


def _regime(returns: pd.Series) -> str:
    annual = returns.mean() * 252
    vol = returns.std() * np.sqrt(252)
    if annual > 0.10 and vol < 0.25:
        return "bull"
    if annual < -0.10:
        return "bear"
    return "range"


def sma_cross_backtest(ticker: str, fast: int = 20, slow: int = 50,
                       lookback_days: int = 365 * 3) -> BacktestResult:
    df = get_prices(ticker, lookback_days=lookback_days)
    if df.empty or len(df) < slow + 50:
        return BacktestResult(ticker, 0, 0.0, 0.0, [], 0.0, 0.0)

    df = df.copy()
    df["sma_fast"] = df["Close"].rolling(fast).mean()
    df["sma_slow"] = df["Close"].rolling(slow).mean()
    df["signal"] = (df["sma_fast"] > df["sma_slow"]).astype(int)
    df["pos"] = df["signal"].shift(1).fillna(0)
    df["ret"] = df["Close"].pct_change().fillna(0)
    df["strat"] = df["pos"] * df["ret"]

    eq = (1 + df["strat"]).cumprod()
    rets = df["strat"]
    sharpe = float(rets.mean() / (rets.std() + 1e-9) * np.sqrt(252))
    max_dd = float((eq / eq.cummax() - 1).min())
    cagr = float(eq.iloc[-1] ** (252 / len(eq)) - 1) if len(eq) > 252 else 0.0
    trades = (df["pos"].diff().abs() > 0).sum()
    win_rate = float((df.loc[df["pos"] == 1, "ret"] > 0).mean()) if (df["pos"] == 1).any() else 0.0

    # Regime coverage: split into 3 windows
    windows = np.array_split(df["ret"].dropna(), 3)
    regimes = sorted({_regime(w) for w in windows if len(w) > 50})

    return BacktestResult(
        ticker=ticker,
        sample_size=int(trades),
        sharpe=sharpe,
        max_dd=max_dd,
        regimes_covered=regimes,
        cagr=cagr,
        win_rate=win_rate,
    )


if __name__ == "__main__":
    import sys, json
    t = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    r = sma_cross_backtest(t)
    print(json.dumps(r.__dict__, indent=2))
