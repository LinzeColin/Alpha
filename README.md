# Alpha - Personal Quant Agent Workspace

Alpha is a local-first personal quant agent workspace for research, backtesting,
automatic paper trading, order-intent review, broker-ready ticket generation, and
dashboard visibility.

## Local run

```bash
python -m pip install -e .
python -m pytest tests -q
python -m backend.app.services.paper_trading_loop --once
uvicorn backend.app.main:app --reload
```

Start/stop dashboard helper:

```bash
scripts/start_alpha_dashboard.sh
scripts/stop_alpha_dashboard.sh
```

Open:

```text
http://localhost:8000/health
http://localhost:8000/dashboard
http://localhost:8000/dashboard/state
```

Useful API endpoints:

```text
POST /paper/run-once
GET  /paper/portfolio
POST /strategy/tournament/run
GET  /orders/approval-queue
```

## Safety

- Live trading is disabled by default.
- Live broker adapter fails closed.
- Policy load failure means reject.
- External API must never trigger live trading.
- Alpha can generate broker-ready order tickets for owner review, but must not
  autonomously submit real-money broker orders.
