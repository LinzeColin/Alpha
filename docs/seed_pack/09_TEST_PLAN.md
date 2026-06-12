# Test Plan

## 1. Test Strategy

The test suite must prioritize correctness and safety over feature breadth.

## 2. Unit Tests

```text
- Strategy DSL accepts valid ETF strategy.
- Strategy DSL rejects leverage.
- Strategy DSL rejects short selling.
- Strategy DSL rejects options.
- Strategy DSL rejects crypto withdrawals.
- Policy loader rejects missing policy.
- Policy loader fails closed on parse error.
- Risk engine calculates drawdown.
- Risk engine calculates volatility.
- Backtest fixture output is deterministic.
```

## 3. Integration Tests

```text
- Validate strategy -> run backtest -> risk report -> governor decision.
- Paper order -> portfolio update -> audit event.
- Live order intent -> rejected by default -> audit event.
- Kill switch active -> live intent rejected.
- Duplicate idempotency key -> second order rejected.
```

## 4. Chaos / Stability Tests

```text
- Market data file missing -> strategy does not trade.
- Broker health unknown -> live intent rejected.
- Audit sink throws error -> live intent rejected.
- Policy YAML invalid -> live intent rejected.
- Worker retry -> does not duplicate order.
- System clock outside market hours -> live intent rejected or queued.
```

## 5. Security Tests

```text
- No broker credentials committed.
- API monetization endpoints require auth when not local.
- No external endpoint can call live execution.
- Config disables crypto withdrawal.
- Tool gateway rejects unknown tools.
```

## 6. Test Commands

```bash
cd repo
python -m pytest tests -q
python -m pytest tests/test_live_broker_fail_closed.py -q
```

## 7. Definition of Done

```text
- All tests pass.
- Live broker default rejection test passes.
- Risk governor tests pass.
- Audit event produced for live rejection.
- Backtest fixture deterministic.
```

