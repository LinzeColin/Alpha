# Task Pack 02 — Market Data Gateway

## Goal

Implement a market data gateway with fixture-first deterministic tests and adapter interfaces for real providers.

## Scope

Support stock/ETF OHLCV data retrieval from:
1. local fixture data
2. provider adapter interface
3. OpenBB adapter placeholder
4. Alpaca/IBKR adapter placeholder

No live broker calls in tests.

## Files to Inspect

```text
apps/api/app/core/policy_engine.py
apps/api/app/core/audit_logger.py
packages/policies/risk_policy.yaml
```

## Files to Create / Modify

```text
quant/data/base.py
quant/data/fixture_adapter.py
quant/data/openbb_adapter.py
quant/data/alpaca_adapter.py
quant/data/ibkr_adapter.py
quant/data/cache.py
quant/data/models.py

apps/api/app/routes/market_data.py

tests/fixtures/ohlcv_spy_sample.csv
tests/fixtures/ohlcv_qqq_sample.csv
tests/unit/test_market_data_gateway.py
tests/unit/test_fixture_data_adapter.py
```

## Data Model

OHLCV row:

```text
symbol
timestamp
open
high
low
close
volume
adjusted_close optional
source
```

## Required Behavior

```text
1. Fixture adapter returns deterministic data.
2. Missing symbol returns structured error.
3. Missing data range returns structured error.
4. All data reads create audit events.
5. Real provider adapters must require explicit env config.
6. Tests must not call external APIs.
```

## API Endpoints

```text
GET /market-data/symbols
GET /market-data/history?symbol=SPY&start=YYYY-MM-DD&end=YYYY-MM-DD
GET /market-data/status
```

## Acceptance Criteria

```text
1. API returns fixture history for SPY/QQQ.
2. No live API keys are required.
3. Adapter interface supports future OpenBB/Alpaca/IBKR implementations.
4. Data reads are audit logged.
5. Data errors fail closed for trading use cases.
```

## Tests

```bash
pytest tests/unit/test_market_data_gateway.py
pytest tests/unit/test_fixture_data_adapter.py
```

## Rollback

Revert market data files and routes.
