from __future__ import annotations

from pathlib import Path
from typing import Dict
import pandas as pd
from .risk import max_drawdown, annualized_volatility


def load_price_fixture(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values("date")


def run_buy_and_hold_fixture(path: str | Path, initial_capital: float = 10000, cost_bps: float = 2, slippage_bps: float = 5) -> Dict[str, float]:
    """Deterministic simple benchmark: equal-weight buy and hold on fixture symbols."""
    df = load_price_fixture(path)
    pivot = df.pivot(index="date", columns="symbol", values="close").dropna()
    rets = pivot.pct_change().dropna()
    portfolio_rets = rets.mean(axis=1)
    one_time_cost = (cost_bps + slippage_bps) / 10000.0
    equity = initial_capital * (1 - one_time_cost) * (1 + portfolio_rets).cumprod()
    total_return = equity.iloc[-1] / initial_capital - 1
    return {
        "total_return": round(float(total_return), 6),
        "max_drawdown": round(max_drawdown(equity), 6),
        "volatility": round(annualized_volatility(portfolio_rets), 6),
        "turnover": 1.0,
        "trade_count": int(len(pivot.columns)),
        "ending_equity": round(float(equity.iloc[-1]), 2),
    }
