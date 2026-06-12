# Task Pack 04 — Risk Engine and Strategy Promotion Gates

## Goal

Implement risk scoring and strategy promotion workflow.

No strategy may move from research/backtest to paper trading unless it passes risk gates.

## Files to Inspect

```text
quant/backtest/
quant/strategies/
packages/policies/risk_policy.yaml
```

## Files to Create / Modify

```text
quant/risk/models.py
quant/risk/risk_engine.py
quant/risk/promotion.py
quant/risk/drawdown.py
quant/risk/concentration.py
quant/risk/turnover.py

apps/api/app/routes/risk.py

tests/unit/test_risk_engine.py
tests/unit/test_strategy_promotion.py
```

## Strategy Lifecycle

```text
draft
-> validated
-> backtested
-> risk_review
-> rejected | research_more | paper_candidate
-> paper_active
-> tiny_live_candidate
-> tiny_live_active
-> paused
```

## Promotion Rules

MVP default:

```yaml
promotion:
  require_cost_model: true
  require_slippage_model: true
  require_min_trades: 10
  require_out_of_sample_placeholder: true
  max_drawdown_pct: 10
  max_turnover_monthly: 2.0
  min_backtest_days: 252
  allow_only_stocks_etfs: true
```

If fixture data cannot satisfy long history requirements, implement the fields and make tests use configurable thresholds.

## Required Behavior

```text
1. Reject strategy without cost model.
2. Reject strategy without slippage model.
3. Reject strategy with prohibited assets.
4. Reject excessive drawdown.
5. Reject excessive turnover.
6. Return structured risk report with reasons.
7. Every promotion decision is audit logged.
```

## Risk Report Model

```text
strategy_id
backtest_id
risk_score
max_drawdown
volatility
turnover
concentration
warnings
decision
reasons
created_at
```

## Tests

```bash
pytest tests/unit/test_risk_engine.py
pytest tests/unit/test_strategy_promotion.py
```

## Acceptance Criteria

```text
1. Risk engine computes metrics from backtest results.
2. Promotion gates work deterministically.
3. Rejected strategy cannot enter paper trading.
4. Passed strategy becomes paper_candidate only.
5. Audit events are generated.
```

## Out of Scope

```text
- Real live trading
- Agent-generated strategies
- Crypto execution
```

## Rollback

Revert risk engine and promotion files.
