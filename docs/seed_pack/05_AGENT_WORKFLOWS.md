# Agent Workflows

## 1. Agent Map

| Agent | Input | Output | Can call live broker? |
|---|---|---|---|
| Data Agent | data source config | normalized market data | No |
| Research Agent | market data, previous reports | research notes, hypotheses | No |
| Strategy Agent | hypotheses | StrategyDSL | No |
| Backtest Agent | StrategyDSL + data | BacktestRun | No |
| Risk Agent | BacktestRun / Portfolio | RiskReport | No |
| Governor Agent | all intents/reports | Decision | No direct broker access |
| Paper Trading Agent | approved paper signal | simulated order | Paper only |
| Live Execution Agent | approved live intent | broker order | Only via ExecutionGateway |
| Crypto Arb Agent | exchange prices | opportunity score | Sandbox/paper only in MVP |
| API Monetization Agent | API usage | invoice/metering event | No trading |
| Console Agent | structured state | owner report | No |

## 2. Daily Research Cycle

```text
Schedule: market close + configurable daily time

1. Data Agent syncs market data.
2. Data quality checks run.
3. Research Agent summarizes market regime.
4. Strategy Agent proposes strategy DSL changes or new candidates.
5. Backtest Agent runs accepted candidates.
6. Risk Agent scores strategies.
7. Governor Agent classifies each strategy:
   - reject
   - hold_research
   - promote_to_paper
   - requires_owner_attention
8. Paper Trading Agent updates paper portfolio.
9. Console Agent writes daily report.
10. Audit log stores all decisions.
```

## 3. Strategy Promotion Workflow

```text
Strategy Candidate
  -> DSL Schema Validation
  -> Prohibited Feature Check
  -> Backtest Run
  -> Cost/Slippage Check
  -> OOS Check
  -> Risk Score
  -> Governor Decision
  -> Paper Trading Queue
```

Promotion gates:

```text
- strategy schema valid
- no leverage
- no short selling
- no options
- no external capital
- backtest years >= policy min
- min trades >= policy min
- max drawdown <= threshold
- includes cost model
- includes slippage model
- deterministic fixture test available
```

## 4. Paper Trading Workflow

```text
1. Load active paper strategies.
2. Generate signal using latest validated data.
3. Convert signal to order intent.
4. Check paper portfolio constraints.
5. Submit simulated order.
6. Update paper portfolio.
7. Compare paper performance vs expected backtest behavior.
8. Generate drift alert if deviation exceeds threshold.
```

## 5. Live Execution Workflow

```text
1. Receive LiveOrderIntent.
2. Validate schema.
3. Check policy live_trading.enabled.
4. Check kill switch.
5. Check market data freshness.
6. Check broker health.
7. Check max order notional.
8. Check max daily orders.
9. Check daily/weekly/monthly loss limits.
10. Check duplicate order hash.
11. Write pre-trade audit event.
12. Submit via broker adapter.
13. Reconcile order status.
14. Write post-trade audit event.
```

Failure modes:

```text
- Any check fails -> reject
- Policy missing -> reject
- Audit sink unavailable -> reject
- Broker state unknown -> reject
- Duplicate idempotency key -> reject
```

## 6. Crypto Arbitrage Workflow

MVP mode: monitor + paper/sandbox only.

```text
1. Pull quotes from exchange adapters or mock adapters.
2. Normalize symbols and trading pairs.
3. Compute gross spread.
4. Estimate trading fees, withdrawal fees, slippage, latency risk.
5. Compute net spread.
6. Score opportunity.
7. If score above threshold, create paper/sandbox order.
8. No withdrawal call exists in MVP.
```

## 7. System-facing API Workflow

```text
1. External system or internal agent calls API.
2. API key validates.
3. Rate limit checks.
4. Request schema validates.
5. Service runs risk/backtest/rebalance/regime classification.
6. Response returned.
7. Usage event stored.
8. Later: Stripe/x402 billing event generated.
```

No external API endpoint may trigger live trading.

## 8. Owner Console Daily Report

Report sections:

```text
- System mode
- Kill switch status
- Strategies promoted/rejected
- Paper PnL and drawdown
- Live exposure if enabled
- Crypto opportunities detected
- API usage/revenue if enabled
- Required owner actions
- Anomalies and failed jobs
```

