# Task Pack 09 — Tiny-Live E-Safe Gate

## Goal

Implement the gate that allows future tiny-live autonomous mode only under strict conditions.

This task still must not place real live orders in tests.

## Files to Inspect

```text
quant/execution/live_order_guard.py
quant/execution/kill_switch.py
quant/execution/reconciliation.py
packages/policies/risk_policy.yaml
apps/api/app/core/policy_engine.py
```

## Files to Create / Modify

```text
quant/execution/tiny_live_gate.py
quant/execution/live_broker_base.py
quant/execution/live_execution_service.py
quant/execution/order_journal.py

apps/api/app/routes/live_readiness.py

tests/unit/test_tiny_live_gate.py
tests/unit/test_order_journal.py
tests/integration/test_e_safe_readiness.py
```

## E-Safe Readiness Checklist

All must pass:

```text
1. live_trading.enabled=true in config AND risk policy.
2. OWNER_E_SAFE_ACK=true.
3. Ring-fenced account ID configured.
4. Kill switch exists and is not force_paused.
5. Broker read-only reconciliation passes.
6. Daily order count below limit.
7. Max order value below limit.
8. Asset is allowed stock/ETF.
9. Strategy status is tiny_live_candidate or tiny_live_active.
10. Strategy has paper trading history.
11. Risk report exists and is current.
12. OrderIntent has idempotency key.
13. No unresolved audit critical events.
```

## Important

Live execution service may call an injected fake broker in tests.

Do not implement real broker order placement unless explicitly requested in a later task pack.

## API Endpoints

```text
GET /live/readiness
POST /live/order-intent/evaluate
POST /live/order-intent/simulate-execution
```

## Tests

```bash
pytest tests/unit/test_tiny_live_gate.py
pytest tests/unit/test_order_journal.py
pytest tests/integration/test_e_safe_readiness.py
```

## Acceptance Criteria

```text
1. E-Safe readiness fails by default.
2. Enabling only env var is insufficient.
3. Enabling only policy is insufficient.
4. Missing ring-fenced account blocks.
5. Missing idempotency key blocks.
6. Fake broker execution works only when all gates pass.
7. Real broker execution is not implemented or remains disabled.
```

## Rollback

Revert tiny-live gate files.
