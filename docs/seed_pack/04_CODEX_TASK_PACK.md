# Codex Task Pack - Build Personal Alpha Agent Workspace MVP

## 0. Codex Operating Mode

Start in **plan/read-only mode**. Do not scan the entire repository recursively. Work one issue at a time.

Default working directory:

```text
repo/
```

Before implementation, Codex must read:

```text
../docs/02_PRD.md
../docs/03_ARCHITECTURE.md
../docs/06_RISK_GOVERNANCE.md
../configs/trading_governor_policy.yaml
../schemas/strategy_dsl.schema.json
```

## 1. Goal

Build a local-first MVP of a Personal Alpha Agent Workspace with:

```text
- Stock/ETF strategy DSL validation
- Market data fixture ingestion
- Deterministic backtest runner
- Risk scoring
- Paper trading broker
- Fail-closed live broker adapter
- Governor policy engine
- Audit logging
- Owner console summary API
```

Live trading must be implemented as an interface but default to `disabled` and `fail_closed`.

## 2. Scope

### In scope

```text
- FastAPI backend skeleton
- Pydantic strategy schemas
- YAML policy loader
- deterministic sample backtest
- paper broker simulator
- live broker fail-closed adapter
- risk metrics calculation
- audit event sink
- test suite
- config files
- docs
```

### Out of scope for first issue

```text
- Real broker credentials
- Real live order placement
- Frontend dashboard
- Stripe/x402 production billing
- Crypto live execution
- Options, leverage, shorts
- External customer-facing endpoints
```

## 3. File Plan

Codex may create/modify these files first:

```text
repo/pyproject.toml
repo/README.md
repo/backend/app/main.py
repo/backend/app/api/routes.py
repo/backend/app/schemas/strategy_dsl.py
repo/backend/app/services/policy.py
repo/backend/app/services/risk.py
repo/backend/app/services/backtest.py
repo/backend/app/services/paper_broker.py
repo/backend/app/services/live_broker.py
repo/backend/app/services/audit.py
repo/configs/trading_governor_policy.yaml
repo/tests/test_strategy_dsl.py
repo/tests/test_policy.py
repo/tests/test_live_broker_fail_closed.py
repo/tests/test_backtest_fixture.py
repo/data/sample_prices.csv
```

Do not modify anything outside `repo/` unless explicitly instructed.

## 4. Implementation Steps

### Issue 1 - Strategy DSL and policy engine

Goal:

```text
Implement strategy DSL validation and GovernorPolicy fail-closed rules.
```

Tasks:

```text
1. Define StrategyDSL Pydantic models.
2. Reject leverage, short selling, options, external capital, crypto withdrawals.
3. Load YAML policy from repo/configs/trading_governor_policy.yaml.
4. Implement PolicyDecision allow/reject/requires_approval.
5. Add tests for valid ETF momentum strategy and invalid prohibited configs.
```

Acceptance:

```text
pytest repo/tests/test_strategy_dsl.py repo/tests/test_policy.py passes
```

### Issue 2 - Backtest fixture runner

Goal:

```text
Implement deterministic backtest over sample CSV data.
```

Tasks:

```text
1. Load sample_prices.csv.
2. Implement a simple monthly momentum rotation strategy.
3. Include transaction cost and slippage parameters.
4. Output metrics: total_return, cagr, volatility, max_drawdown, turnover, trade_count.
5. Ensure deterministic output.
```

Acceptance:

```text
pytest repo/tests/test_backtest_fixture.py passes
```

### Issue 3 - Risk engine

Goal:

```text
Score backtest and paper strategy risk.
```

Tasks:

```text
1. Implement drawdown calculation.
2. Implement volatility calculation.
3. Implement concentration and turnover checks.
4. Implement promotion decision helper.
5. Require cost_model and slippage_model before promotion.
```

Acceptance:

```text
Risk report returns reject/hold/promote_to_paper based on configured thresholds.
```

### Issue 4 - Paper broker and paper portfolio

Goal:

```text
Simulate orders without touching real broker APIs.
```

Tasks:

```text
1. Implement PaperBroker.submit_order.
2. Validate cash, position, symbol, side, quantity.
3. Store simulated trade events.
4. Update paper portfolio.
5. Add duplicate order idempotency key.
```

Acceptance:

```text
Paper order updates simulated portfolio only.
Duplicate order intent is rejected.
```

### Issue 5 - Live broker fail-closed adapter

Goal:

```text
Create a live broker interface that cannot place real orders unless explicitly enabled.
```

Tasks:

```text
1. Define LiveBroker interface.
2. Implement FailClosedLiveBroker.
3. Implement submit_order_intent that rejects by default.
4. Require live_trading.enabled=true, policy hash, kill_switch=false, max_notional checks.
5. Add test that live order cannot be placed by default.
```

Acceptance:

```text
pytest repo/tests/test_live_broker_fail_closed.py passes
```

### Issue 6 - Owner console API

Goal:

```text
Expose local endpoints for system state.
```

Routes:

```text
GET  /health
GET  /owner/summary
POST /strategy/validate
POST /backtest/run
POST /paper/order
POST /live/order-intent
POST /kill-switch/activate
POST /kill-switch/deactivate
```

Acceptance:

```text
FastAPI starts locally.
/health returns ok.
/live/order-intent rejects by default.
```

### Issue 7 - Daily agent workflow stubs

Goal:

```text
Add stub workflows for research, backtest, risk, paper, report.
```

Tasks:

```text
1. Implement workflow functions without requiring OpenAI key.
2. Add interfaces for future OpenAI Agents SDK integration.
3. Generate markdown owner report from structured state.
```

Acceptance:

```text
Running python -m backend.app.services.daily_cycle creates a deterministic markdown report.
```

## 5. Test Commands

```bash
cd repo
python -m pytest tests -q
python -m backend.app.main
```

Optional API test:

```bash
uvicorn backend.app.main:app --reload
curl http://localhost:8000/health
```

## 6. Rollback Plan

```text
- All generated reports and backtest results must be versioned.
- No live trading code should be wired to a real broker in MVP.
- If policy engine fails, all order intents reject.
- If test fixture output changes unexpectedly, block merge.
- If audit log fails, block live order intent.
```

## 7. Risks

| Risk | Mitigation |
|---|---|
| Accidental live order | fail-closed adapter, disabled config, no credentials in repo |
| Overfitting | OOS/walk-forward gates in later issue |
| Data leakage | strategy validator tags features and data windows |
| Duplicate execution | idempotency key and order hash |
| LLM hallucination | structured schemas only; no free-text order execution |
| Regulatory scope creep | no external advice, no third-party capital |

## 8. Final Acceptance Criteria

```text
1. All tests pass.
2. Strategy DSL validates and rejects prohibited configs.
3. Backtest fixture is deterministic.
4. Risk report exists.
5. Paper broker works without real broker access.
6. Live broker fails closed by default.
7. Owner summary endpoint exists.
8. Audit events are emitted for policy, backtest, paper order, live rejection.
9. Config files are documented.
10. README explains how to run locally.
```

