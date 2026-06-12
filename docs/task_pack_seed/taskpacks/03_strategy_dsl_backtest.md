# Task Pack 03 — Strategy DSL and Backtest Engine

## Goal

Implement a restricted JSON strategy DSL and deterministic backtest engine for stock/ETF strategies.

The LLM must generate DSL, not arbitrary executable strategy code.

## Files to Inspect

```text
quant/data/
packages/policies/risk_policy.yaml
packages/schemas/strategy_dsl.schema.json
```

## Files to Create / Modify

```text
packages/schemas/strategy_dsl.schema.json

quant/strategies/dsl.py
quant/strategies/registry.py
quant/backtest/engine.py
quant/backtest/metrics.py
quant/backtest/costs.py
quant/backtest/slippage.py
quant/backtest/models.py

apps/api/app/routes/strategies.py
apps/api/app/routes/backtests.py

tests/unit/test_strategy_dsl.py
tests/unit/test_backtest_engine.py
tests/unit/test_backtest_metrics.py
```

## DSL Requirements

Allowed first-version strategy types:

```text
- momentum_rotation
- moving_average_cross
- volatility_filter
- rebalance_fixed_weight
```

Prohibited:

```text
- leverage
- short selling
- options
- margin
- CFDs
- crypto live trading
- arbitrary Python code
- arbitrary shell commands
```

## Strategy DSL Example

```json
{
  "name": "dev_fixture_etf_momentum_rotation",
  "asset_class": "equity_etf",
  "universe": ["SPY", "QQQ", "IWM", "TLT", "GLD"],
  "timeframe": "1d",
  "rebalance_frequency": "monthly",
  "signals": [
    {
      "type": "momentum",
      "lookback_days": 126,
      "rank_descending": true
    },
    {
      "type": "volatility_filter",
      "lookback_days": 20,
      "max_volatility": 0.3
    }
  ],
  "portfolio": {
    "max_positions": 2,
    "max_weight_per_asset": 0.5,
    "cash_if_no_signal": true
  },
  "cost_model": {
    "commission_bps": 0.0,
    "spread_bps": 2.0
  },
  "slippage_model": {
    "slippage_bps": 2.0
  },
  "risk": {
    "no_leverage": true,
    "no_short": true,
    "max_drawdown_pct": 10
  }
}
```

The symbols are fixtures/examples, not investment recommendations.

## Backtest Requirements

Metrics:

```text
- total_return
- annualized_return
- volatility
- sharpe_like_ratio
- max_drawdown
- turnover
- number_of_trades
- exposure
- win_rate optional
```

Hard requirements:

```text
1. Cost model required.
2. Slippage model required.
3. Deterministic fixture backtests.
4. No look-ahead bias in signal generation.
5. Reject insufficient historical data.
```

## API Endpoints

```text
POST /strategies/validate
POST /backtests/run
GET /backtests/{id}
```

## Tests

```bash
pytest tests/unit/test_strategy_dsl.py
pytest tests/unit/test_backtest_engine.py
pytest tests/unit/test_backtest_metrics.py
```

## Acceptance Criteria

```text
1. Valid DSL passes.
2. DSL with leverage/short/options/margin fails.
3. Backtest runs on local fixtures.
4. Same input returns same output.
5. Cost and slippage affect results.
6. Backtest result is persisted or serializable.
```

## Rollback

Revert strategy/backtest files and API routes.
