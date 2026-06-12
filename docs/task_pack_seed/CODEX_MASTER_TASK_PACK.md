# Codex Master Task Pack
# Personal System-Facing Quant Agent Space MVP

## 0. Mission

Build a personal system-facing agent space that can research, backtest, paper trade, and eventually run tiny-live autonomous stock/ETF strategies inside hard safety limits.

This project is not a human-facing agency, not a freelancer bot, not a signal-selling community, and not a financial advice product.

The owner should interact only with:
- AI console
- dashboards
- logs
- approvals / kill switch
- configuration files

The system should interact with:
- market data APIs
- broker paper trading APIs
- broker read-only APIs
- local backtest engine
- risk/governor engine
- audit database
- optional Stripe/x402-style API payment layer later

## 1. Current Target Configuration

User-selected target:

```text
Revenue lines:
- A: self-funded stock/ETF quant trading agent
- B: portfolio / ETF rebalancing agent
- C: crypto / arbitrage scanner and later bot
- D: system-facing API revenue layer

Initial asset class:
- stocks / ETFs first

Autonomy target:
- start with paper + tiny-live guarded mode
- within 30 days reach E-Safe, meaning ring-fenced full autonomy under hard-coded risk limits

Risk appetite:
- medium/high systematic alpha
- high-return opportunities allowed only after explicit safety gates
```

## 2. Non-Negotiable Safety Rules

Codex must preserve these rules throughout the repo:

```text
1. Live trading is disabled by default.
2. Any policy engine failure must reject, not allow.
3. No agent may directly call a live broker order method.
4. All live orders must go through:
   Signal -> OrderIntent -> PreTradeRiskCheck -> LiveOrderGuard -> BrokerAdapter -> Reconciliation.
5. All order attempts must have an idempotency key.
6. All strategies must include transaction cost and slippage assumptions before promotion.
7. Strategies using leverage, short selling, options, CFDs, margin, or crypto live trading are rejected in MVP.
8. Crypto is scanner + paper only in MVP.
9. API revenue layer must not return personalized buy/sell recommendations.
10. No real API keys, secrets, account IDs, or credentials may be committed.
11. Any missing data, broker error, reconciliation error, duplicate order, or risk report failure must pause trading.
12. Kill switch must override all automation.
```

## 3. Engineering Mode for Codex

Use this protocol for every task pack.

### Before modifying files, Codex must output:

```text
1. Task pack ID being executed.
2. Assumptions.
3. Files/directories to inspect.
4. Files/directories to create or modify.
5. Tests to run.
6. Risk and rollback plan.
7. Out-of-scope items.
```

### During implementation:

```text
- Do not scan the entire repo unless the task explicitly allows it.
- Do not refactor unrelated directories.
- Do not add new dependencies without stating why.
- Prefer deterministic tests and local fixtures over live API calls.
- Never make real broker calls in tests.
- Never require real credentials in CI.
```

### After implementation, Codex must output:

```text
1. Diff summary.
2. Tests run and results.
3. Any failing tests with exact error.
4. Remaining risks.
5. Next recommended task pack.
```

## 4. Implementation Order

Run exactly one task pack at a time:

```text
00_bootstrap_repo.md
01_policy_audit_core.md
02_market_data_gateway.md
03_strategy_dsl_backtest.md
04_risk_engine_promotion.md
05_agent_workflows.md
06_paper_trading_loop.md
07_broker_readonly_live_guard.md
08_dashboard_kill_switch.md
09_tiny_live_e_safe_gate.md
10_crypto_scanner_paper_only.md
11_api_revenue_layer_sandbox.md
12_ops_runbooks_30_day.md
```

Do not jump to live trading before task packs 00-08 are complete and tested.

## 5. Suggested Stack

```text
Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Postgres
- Redis + RQ or Celery
- pytest

Frontend:
- Next.js
- TypeScript
- Tailwind
- lightweight charting library

Agents:
- OpenAI Agents SDK
- structured outputs
- guardrails
- tracing / audit logging

Quant:
- local deterministic backtest engine first
- OpenBB / broker data adapter interfaces
- IBKR paper/read-only adapter or Alpaca paper adapter
- crypto scanner later, no live crypto in MVP

Payments:
- Stripe sandbox first
- x402 stub only, not production in MVP
```

## 6. 30-Day E-Safe Roadmap

```text
Day 1-2:
- bootstrap repo
- policy and audit core
- no live trading

Day 3-5:
- market data gateway
- sample stock/ETF universe
- deterministic data fixtures

Day 6-8:
- strategy DSL
- backtest engine
- cost/slippage model

Day 9-11:
- research/strategy/backtest/risk/governor agents
- structured outputs and audit trail

Day 12-14:
- autonomous paper trading loop
- daily AI console report
- L2 achieved

Day 15-17:
- broker read-only adapter
- live adapter stub
- pre-trade risk check
- kill switch

Day 18-21:
- tiny-live approval mode
- then tiny-live autonomous only if tests and reconciliation pass
- L3/L4 achieved

Day 22-24:
- crypto scanner + paper arbitrage simulator
- no live crypto

Day 25-27:
- non-advisory API revenue layer sandbox
- Stripe test payment
- x402 stub

Day 28-30:
- E-Safe: ring-fenced tiny-live autonomy under hard limits
- full audit, kill switch, reconciliation, failure pause
```

## 7. Definition of E-Safe

E-Safe means:

```text
- Agent can run automatically inside a ring-fenced account.
- Agent cannot exceed fixed order, exposure, asset, loss, and frequency limits.
- Agent cannot trade prohibited assets.
- Agent cannot modify risk limits by itself.
- Agent cannot bypass live order guard.
- Any unresolved exception pauses automation.
- Owner does not approve every order but can stop everything instantly.
```

E-Safe does not mean unlimited autonomy.

## 8. First Codex Prompt

Copy this into Codex for the first task:

```text
You are Codex working in a new repository: personal-quant-agent-space.

Execute taskpacks/00_bootstrap_repo.md only.

Operate in plan-first mode. Before modifying files, provide:
1. Assumptions.
2. Files/directories you will create.
3. Commands you will run.
4. Risks.
5. Rollback plan.

Hard constraints:
- Do not implement trading logic.
- Do not connect to broker APIs.
- Do not add real credentials.
- Do not enable live trading.
- Do not refactor anything outside the scope.

After implementation:
1. Run the listed tests/lint/typecheck commands where possible.
2. Provide diff summary.
3. Report failures honestly.
4. Recommend the next task pack.
```
