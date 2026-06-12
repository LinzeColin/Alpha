# Risk Governance

## 1. Core Rule

```text
No policy, no trade.
No audit, no trade.
No fresh data, no trade.
No idempotency key, no trade.
No broker health, no trade.
```

## 2. Default Live Trading Posture

Live trading code may exist, but the default posture is:

```yaml
live_trading:
  enabled: false
  fail_closed_on_policy_error: true
```

To enable guarded live mode, all must be true:

```text
- live_trading.enabled=true
- environment LIVE_TRADING_ENABLED=true
- broker adapter configured
- kill_switch.active=false
- audit sink healthy
- policy hash matches loaded config
- max notional and daily limits configured
- strategy status=approved_live_guarded
```

## 3. Prohibited Actions

```text
- manage external capital
- provide personal financial advice to third parties
- publish trade signals as recommendations
- options trading in MVP
- leverage in MVP
- short selling in MVP
- crypto withdrawals in MVP
- MEV / flash loans in MVP
- HFT in MVP
- bypass broker limits
```

## 4. Risk Limits

MVP defaults are conservative engineering placeholders, not investment advice.

```yaml
max_order_value_aud: 100
max_daily_orders: 5
max_position_weight_pct: 10
max_total_gross_exposure_pct: 30
max_daily_loss_pct: 0.5
max_weekly_loss_pct: 1.5
max_monthly_loss_pct: 3.0
allow_leverage: false
allow_short_selling: false
allow_options: false
allow_crypto_withdrawal: false
```

## 5. Strategy Gate

```text
Backtest -> Risk score -> Paper -> Live guarded
```

Requirements:

```text
- backtest deterministic
- cost model present
- slippage model present
- OOS test present before live
- min paper days satisfied before scaled live
- max drawdown below threshold
- turnover not excessive
- no forbidden asset class
```

## 6. Kill Switch

Kill switch triggers:

```text
- manual activation
- daily loss limit reached
- broker disconnected
- data stale
- duplicate order detected
- unexpected live position
- audit sink unavailable
- policy parse error
- unknown exception in execution gateway
```

Kill switch behavior:

```text
- block new live orders
- cancel pending orders if broker adapter supports it
- keep data/reporting running
- generate owner alert
- require explicit reset
```

## 7. Audit Requirements

Every event must include:

```text
- trace_id
- actor_type
- actor_id
- event_type
- entity_type
- entity_id
- input payload hash
- decision
- reason
- policy version
- timestamp
```

## 8. Regulatory Scope Control

For Australia:

```text
- System is for own funds only.
- No third-party account management.
- No personalized financial advice to others.
- No public buy/sell recommendations.
- Keep tax event logs for shares and crypto.
```

References:

```text
ASIC financial product advice:
https://www.asic.gov.au/regulatory-resources/financial-services/giving-financial-product-advice/

ATO share investing versus share trading:
https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/share-investing-versus-share-trading

ATO crypto asset investments:
https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments
```

