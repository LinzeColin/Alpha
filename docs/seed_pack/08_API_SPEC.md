# API Spec

Base URL:

```text
http://localhost:8000
```

## 1. Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "mode": "research_and_paper_only",
  "live_trading_enabled": false,
  "kill_switch_active": false
}
```

## 2. Owner Summary

```http
GET /owner/summary
```

Response:

```json
{
  "system_mode": "research_and_paper_only",
  "strategies": {"research": 3, "paper": 2, "live_guarded": 0},
  "paper_pnl": 0.0,
  "risk_alerts": [],
  "required_owner_actions": []
}
```

## 3. Strategy Validate

```http
POST /strategy/validate
```

Request:

```json
{
  "name": "ETF Momentum v0",
  "asset_class": "etf",
  "universe": ["SPY", "QQQ", "IWM", "TLT"],
  "rebalance_frequency": "monthly",
  "signals": [{"type": "momentum", "lookback_days": 126}],
  "risk": {"no_leverage": true, "no_short": true, "no_options": true}
}
```

Response:

```json
{
  "valid": true,
  "warnings": [],
  "normalized_strategy": {}
}
```

## 4. Backtest Run

```http
POST /backtest/run
```

Request:

```json
{
  "strategy": {},
  "data_source": "fixture",
  "initial_capital": 10000,
  "cost_bps": 2,
  "slippage_bps": 5
}
```

Response:

```json
{
  "run_id": "bt_001",
  "metrics": {
    "total_return": 0.12,
    "max_drawdown": -0.08,
    "volatility": 0.15,
    "turnover": 1.2,
    "trade_count": 20
  }
}
```

## 5. Paper Order

```http
POST /paper/order
```

Request:

```json
{
  "strategy_id": "s_001",
  "idempotency_key": "abc",
  "symbol": "SPY",
  "side": "buy",
  "quantity": 1,
  "price": 500
}
```

## 6. Live Order Intent

```http
POST /live/order-intent
```

Default response:

```json
{
  "status": "rejected",
  "reason": "live trading disabled by policy"
}
```

## 7. Kill Switch

```http
POST /kill-switch/activate
POST /kill-switch/deactivate
GET  /kill-switch/status
```

## 8. Monetization API Preview

```http
POST /api/v1/strategy/validate
POST /api/v1/backtest/run
POST /api/v1/risk/score
POST /api/v1/portfolio/rebalance
GET  /api/v1/market/regime
```

Rules:

```text
- External API cannot trigger live trading.
- Every request logs usage_event.
- API key required outside localhost.
- Rate limit required before public exposure.
```

