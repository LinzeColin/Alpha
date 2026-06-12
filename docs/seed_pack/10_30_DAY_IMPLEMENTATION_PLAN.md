# 30-Day Implementation Plan

## Goal

30 天内把系统从 MVP 开发到 guarded E-mode 能力：可以无人值守运行、自动策略研究、自动回测、自动纸面交易、具备小额全自动实盘能力，但所有真实交易均受硬限额、policy、kill switch、audit 约束。

## Week 1 - Control Plane + Backtest Foundation

| Day | Work | Acceptance |
|---|---|---|
| 1 | Repo skeleton, FastAPI, config, tests | App runs, /health ok |
| 2 | Strategy DSL schema | Valid ETF DSL passes, prohibited configs fail |
| 3 | Policy engine | Missing/invalid policy fail closed |
| 4 | Sample data ingestion | fixture data loaded |
| 5 | Backtest runner | deterministic metrics |
| 6 | Risk metrics | max drawdown, volatility, turnover |
| 7 | Owner summary report | markdown + API summary |

## Week 2 - Paper Autonomous System

| Day | Work | Acceptance |
|---|---|---|
| 8 | PaperBroker | simulated orders only |
| 9 | Paper portfolio | positions/cash/PnL update |
| 10 | Strategy promotion gate | reject/hold/promote_to_paper |
| 11 | Daily workflow runner | unattended daily cycle |
| 12 | Multi-strategy tournament | ranked strategies |
| 13 | Audit completeness | every decision traced |
| 14 | Owner Console v0 | daily summary, alerts, strategy statuses |

## Week 3 - Guarded Live Capability + Crypto Sandbox

| Day | Work | Acceptance |
|---|---|---|
| 15 | LiveBroker interface | default fail closed |
| 16 | ExecutionGateway | policy/risk/idempotency checks |
| 17 | Kill switch | block live intents |
| 18 | Broker adapter stub | paper/live separation |
| 19 | Crypto arb monitor | mock/sandbox price spread scoring |
| 20 | API endpoints | risk/backtest/validate/rebalance APIs |
| 21 | Guarded tiny-live dry run | no real credential required; policy-gated path tested |

## Week 4 - E-mode Engineering Readiness + Deployment

| Day | Work | Acceptance |
|---|---|---|
| 22 | Docker compose | api/worker/db/redis local deployment |
| 23 | Scheduler | daily jobs with retries |
| 24 | Chaos tests | data missing, policy invalid, duplicate orders |
| 25 | E-mode config path | can enable guarded live only with explicit config |
| 26 | Observability | logs, trace IDs, audit dashboard/API |
| 27 | API monetization metering | usage events + auth |
| 28 | End-to-end paper run | research -> paper -> report |
| 29 | End-to-end guarded live simulation | rejected by default, allowed only in mocked live mode |
| 30 | Release package | tests pass, docs, deployment checklist |

## 30-Day E-mode Definition

The system is considered to have reached E-mode engineering readiness if:

```text
- It can run unattended.
- It can produce live order intents autonomously.
- ExecutionGateway can submit to a broker adapter if policy allows.
- Default config blocks real trading.
- Mock live mode demonstrates full autonomous path.
- Real live mode requires explicit credentials and policy changes.
- Kill switch, idempotency, audit, risk limits, and broker health checks are enforced.
```

## Velocity Controls

```text
- One issue per day when possible.
- Do not build frontend before backend safety tests pass.
- Do not integrate real broker before fail-closed tests pass.
- Do not add complex ML before deterministic rule strategies work.
- Do not add x402 before internal API metering works.
```

