# Task Pack 06 — Autonomous Paper Trading Loop

## Goal

Implement paper trading loop for promoted paper_candidate strategies.

Paper trading must not touch real broker APIs.

## Files to Inspect

```text
quant/risk/
quant/strategies/
quant/backtest/
agents/governor_agent.py
```

## Files to Create / Modify

```text
quant/execution/order_models.py
quant/execution/paper_broker.py
quant/portfolio/paper_portfolio.py
quant/signals/signal_runner.py
quant/scheduler/paper_trading_jobs.py

apps/api/app/routes/paper_trading.py

tests/unit/test_paper_broker.py
tests/unit/test_paper_portfolio.py
tests/integration/test_paper_trading_loop.py
```

## Models

```text
Signal
- strategy_id
- symbol
- target_weight
- generated_at
- reason

OrderIntent
- id
- strategy_id
- symbol
- side
- quantity
- notional
- source_signal_id
- idempotency_key
- mode: paper|live

PaperOrder
- order_intent_id
- fill_price
- quantity
- fees
- status

PaperPortfolio
- cash
- positions
- equity
- pnl
- drawdown
```

## Required Behavior

```text
1. Only paper_candidate or paper_active strategies can run.
2. Signal runner generates target portfolio.
3. Paper broker simulates fills using fixture/latest prices.
4. Portfolio updates after simulated fill.
5. Fees/slippage are included.
6. Paper loop writes audit events.
7. If market data missing, strategy pauses.
```

## API Endpoints

```text
POST /paper-trading/run-once
GET /paper-trading/portfolios
GET /paper-trading/orders
POST /paper-trading/pause-strategy/{id}
```

## Tests

```bash
pytest tests/unit/test_paper_broker.py
pytest tests/unit/test_paper_portfolio.py
pytest tests/integration/test_paper_trading_loop.py
```

## Acceptance Criteria

```text
1. A paper_candidate strategy can produce paper orders.
2. Paper orders update paper portfolio deterministically.
3. No live broker adapter is imported or called.
4. Missing data pauses strategy.
5. Audit log records signal, intent, fill, portfolio update.
```

## Rollback

Revert paper trading files and routes.
