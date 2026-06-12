# Task Pack 07 — Broker Read-Only Adapter and Live Guard Stub

## Goal

Implement broker read-only adapter interfaces and live order guard.

Live trading remains disabled.

## Files to Inspect

```text
quant/execution/order_models.py
quant/portfolio/
packages/policies/risk_policy.yaml
apps/api/app/core/policy_engine.py
```

## Files to Create / Modify

```text
quant/execution/broker_base.py
quant/execution/broker_readonly.py
quant/execution/alpaca_readonly_adapter.py
quant/execution/ibkr_readonly_adapter.py
quant/execution/live_order_guard.py
quant/execution/live_broker_stub.py
quant/execution/kill_switch.py
quant/execution/reconciliation.py

apps/api/app/routes/broker.py
apps/api/app/routes/kill_switch.py

tests/unit/test_live_order_guard.py
tests/unit/test_kill_switch.py
tests/unit/test_reconciliation.py
tests/integration/test_live_adapter_fails_closed.py
```

## Required Behavior

```text
1. Broker read-only adapters may expose account/positions/orders if configured.
2. If not configured, they return structured unavailable status.
3. Live broker stub always rejects by default.
4. LiveOrderGuard rejects if live_trading.enabled=false.
5. LiveOrderGuard rejects missing idempotency key.
6. LiveOrderGuard rejects prohibited assets/actions.
7. KillSwitch force-pauses all live actions.
8. Reconciliation mismatch triggers pause.
```

## PreTradeRiskCheck

Fields:

```text
order_intent_id
strategy_id
symbol
asset_class
notional
current_position
projected_position
daily_order_count
daily_loss_pct
policy_decision
allowed
reasons
created_at
```

## API Endpoints

```text
GET /broker/status
GET /broker/positions
POST /kill-switch/enable
POST /kill-switch/disable
GET /kill-switch/status
```

## Tests

```bash
pytest tests/unit/test_live_order_guard.py
pytest tests/unit/test_kill_switch.py
pytest tests/unit/test_reconciliation.py
pytest tests/integration/test_live_adapter_fails_closed.py
```

## Acceptance Criteria

```text
1. Live order cannot execute by default.
2. Kill switch blocks live action.
3. Policy failure blocks live action.
4. Reconciliation mismatch blocks live action.
5. Tests require no real broker credentials.
```

## Rollback

Revert broker/guard files and routes.
