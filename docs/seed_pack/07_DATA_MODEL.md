# Data Model

## 1. Core Tables

```text
assets
market_data_sources
price_bars
strategies
strategy_versions
backtest_runs
risk_reports
paper_portfolios
paper_orders
live_order_intents
live_orders
crypto_opportunities
api_keys
api_usage_events
audit_events
kill_switch_events
owner_reports
```

## 2. Entity Summary

### assets

```text
id
symbol
name
asset_class: stock|etf|crypto|cash
exchange
currency
active
created_at
```

### strategies

```text
id
name
strategy_type
asset_class
status: draft|research|backtested|paper|approved_live_guarded|paused|rejected
created_by_agent
created_at
updated_at
```

### strategy_versions

```text
id
strategy_id
version
strategy_dsl_json
config_hash
created_at
```

### backtest_runs

```text
id
strategy_version_id
start_date
end_date
universe
initial_capital
cost_model_json
slippage_model_json
metrics_json
status
artifact_path
created_at
```

### risk_reports

```text
id
strategy_version_id
backtest_run_id
risk_score
max_drawdown
volatility
turnover
concentration
warnings_json
decision: reject|hold_research|promote_to_paper|requires_owner_attention
created_at
```

### paper_orders

```text
id
strategy_id
idempotency_key
symbol
side
quantity
simulated_price
fees
status
created_at
```

### live_order_intents

```text
id
strategy_id
idempotency_key
symbol
side
quantity
order_type
limit_price
notional_estimate
status: rejected|approved|submitted|cancelled|failed
policy_decision_json
created_at
```

### audit_events

```text
id
trace_id
actor_type
actor_id
event_type
entity_type
entity_id
payload_hash
payload_json
policy_version
decision
reason
created_at
```

## 3. Idempotency

Every execution intent must have:

```text
idempotency_key = hash(strategy_id + strategy_version + signal_timestamp + symbol + side + quantity + intended_price_band)
```

Duplicate key behavior:

```text
- paper order: reject duplicate
- live intent: reject duplicate
- retries: return original result without resubmission
```

## 4. Storage Strategy

MVP:

```text
- SQLite or Postgres for control state
- CSV fixture data
- local markdown reports
```

Production:

```text
- Postgres
- Parquet price bars
- S3/R2 artifact storage
- immutable backtest artifacts
```

