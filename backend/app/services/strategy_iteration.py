from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app.services.backtest import load_price_fixture
from backend.app.services.risk import risk_score


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    symbol: str
    signal_type: str
    lookback_days: int
    score: float
    total_return: float
    oos_return: float
    hit_rate: float
    validation_windows: int
    max_drawdown: float
    decision: str

    def as_dict(self) -> dict:
        return asdict(self)


def run_strategy_tournament(price_path: str | Path, *, lookbacks: tuple[int, ...] = (5, 10, 20)) -> dict:
    df = load_price_fixture(price_path)
    candidates: list[StrategyCandidate] = []
    for symbol, symbol_df in df.groupby("symbol"):
        closes = symbol_df.sort_values("date")["close"]
        for lookback in lookbacks:
            if len(closes) <= lookback:
                continue
            start = float(closes.iloc[-lookback])
            end = float(closes.iloc[-1])
            total_return = end / start - 1.0
            drawdown = _simple_drawdown(closes.tail(lookback))
            metrics = {"max_drawdown": drawdown, "trade_count": lookback, "turnover": 1.0}
            risk = risk_score(metrics)
            walk_forward = _walk_forward_momentum(closes, lookback)
            momentum_score = total_return + (0.5 * walk_forward["oos_return"]) + (0.01 * walk_forward["hit_rate"]) - abs(drawdown)
            candidates.append(
                StrategyCandidate(
                    strategy_id=f"momentum_{symbol}_{lookback}d",
                    symbol=str(symbol),
                    signal_type="momentum",
                    lookback_days=lookback,
                    score=round(momentum_score, 6),
                    total_return=round(total_return, 6),
                    oos_return=round(walk_forward["oos_return"], 6),
                    hit_rate=round(walk_forward["hit_rate"], 6),
                    validation_windows=int(walk_forward["validation_windows"]),
                    max_drawdown=round(drawdown, 6),
                    decision=str(risk["decision"]),
                )
            )
    ranked = sorted(candidates, key=lambda item: (item.decision == "promote_to_paper", item.score), reverse=True)
    winner = ranked[0] if ranked else None
    validated = [item for item in ranked if item.validation_windows > 0]
    return {
        "status": "completed",
        "candidate_count": len(ranked),
        "validation_summary": {
            "validated_count": len(validated),
            "winner_hit_rate": winner.hit_rate if winner else None,
            "winner_oos_return": winner.oos_return if winner else None,
            "winner_validation_windows": winner.validation_windows if winner else 0,
        },
        "winner": winner.as_dict() if winner else None,
        "candidates": [item.as_dict() for item in ranked],
    }


def _simple_drawdown(closes) -> float:
    running_max = closes.cummax()
    drawdowns = closes / running_max - 1.0
    return float(drawdowns.min())


def _walk_forward_momentum(closes, lookback: int) -> dict:
    """Evaluate one-step-ahead returns when the lookback momentum signal is positive."""
    ordered = closes.reset_index(drop=True)
    returns = []
    hits = 0
    for idx in range(lookback, len(ordered) - 1):
        signal_positive = float(ordered.iloc[idx]) > float(ordered.iloc[idx - lookback])
        if not signal_positive:
            continue
        next_return = float(ordered.iloc[idx + 1]) / float(ordered.iloc[idx]) - 1.0
        returns.append(next_return)
        if next_return > 0:
            hits += 1
    if not returns:
        return {"oos_return": 0.0, "hit_rate": 0.0, "validation_windows": 0}
    compounded = 1.0
    for value in returns:
        compounded *= 1.0 + value
    return {
        "oos_return": compounded - 1.0,
        "hit_rate": hits / len(returns),
        "validation_windows": len(returns),
    }
