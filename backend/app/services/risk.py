from __future__ import annotations

import numpy as np
import pandas as pd
from backend.app.services.policy import GovernorPolicy


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdowns = equity_curve / running_max - 1.0
    return float(drawdowns.min())


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.empty:
        return 0.0
    return float(returns.std(ddof=0) * np.sqrt(periods_per_year))


def risk_score(metrics: dict) -> dict:
    warnings = []
    score = 100
    if abs(metrics.get("max_drawdown", 0)) > 0.10:
        score -= 30
        warnings.append("max_drawdown_above_10pct")
    if metrics.get("trade_count", 0) < 10:
        score -= 20
        warnings.append("low_trade_count")
    if metrics.get("turnover", 0) > 3:
        score -= 20
        warnings.append("high_turnover")
    decision = "promote_to_paper" if score >= 70 else "hold_research"
    if score < 50:
        decision = "reject"
    return {"risk_score": max(score, 0), "warnings": warnings, "decision": decision}


def pre_trade_risk_check(intent: dict, policy: GovernorPolicy, *, kill_switch_active: bool = False) -> dict:
    """Validate an order candidate before it can enter the owner approval queue."""
    limits = policy.data.get("risk_limits", {})
    max_notional = float(limits.get("max_order_value_aud", 0))
    notional = float(intent.get("estimated_notional_aud", 0))
    quantity = float(intent.get("quantity", 0))
    price = float(intent.get("estimated_price", 0))
    side = str(intent.get("side", "")).lower()
    idempotency_key = str(intent.get("idempotency_key", ""))

    if kill_switch_active:
        return {"allowed": False, "status": "rejected", "reason": "kill switch active"}
    if not idempotency_key:
        return {"allowed": False, "status": "rejected", "reason": "missing idempotency key"}
    if side not in {"buy", "sell"}:
        return {"allowed": False, "status": "rejected", "reason": "invalid side"}
    if quantity <= 0 or price <= 0 or notional <= 0:
        return {"allowed": False, "status": "rejected", "reason": "invalid quantity, price, or notional"}
    if max_notional <= 0:
        return {"allowed": False, "status": "rejected", "reason": "max order value not configured"}
    if notional > max_notional:
        return {"allowed": False, "status": "rejected", "reason": "max order value exceeded"}
    return {"allowed": True, "status": "approved_for_owner_review", "reason": "pre-trade risk checks passed"}
