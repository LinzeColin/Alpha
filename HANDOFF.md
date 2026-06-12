# Alpha Handoff

Timestamp: 2026-06-13 Australia/Sydney

## Current Goal

Build Alpha as a GitHub-backed personal quant agent workspace with automatic paper trading, strategy iteration foundations, risk checks, approval queue, broker-ready order tickets, and dashboard visibility.

## Current State

- GitHub remote confirmed: `https://github.com/LinzeColin/Alpha`
- Local repo initialized on `main`
- Seed implementation and docs imported from the provided Alpha delivery pack
- Safety boundary recorded in `AGENTS.md`
- Default committed live trading config remains disabled
- MVP paper loop now generates `OrderIntent`, runs `pre_trade_risk_check`, fills a paper order, queues a `BrokerReadyOrderTicket`, and exposes dashboard state.
- Dashboard is available at `/dashboard`; API state is available at `/dashboard/state`.
- Paper portfolio state now persists through `PaperBroker.save/load`.
- Strategy iteration now runs a fixture momentum tournament and selects the best tradable candidate under risk/notional limits.
- Dashboard state includes `paper_portfolio` and `strategy_tournament`.
- Local launcher scripts exist at `scripts/start_alpha_dashboard.sh` and `scripts/stop_alpha_dashboard.sh`.
- Repo launcher exists at `outputs/applications/Alpha.command`; an older external copy was observed at `/Users/linzezhang/Downloads/applicatioins/Alpha.command`.

## Key Decisions

- The system will automate paper trading and order ticket generation.
- The system will not autonomously submit real-money broker orders.
- Broker-ready real-money candidates flow through `OrderIntent -> risk check -> approval queue -> BrokerReadyOrderTicket`.
- Refresh cadence target is 300 seconds by default.

## Files To Read First

- `AGENTS.md`
- `README.md`
- `HANDOFF.md`
- `docs/decision_log.md`
- `configs/trading_governor_policy.yaml`
- `backend/app/services/paper_trading_loop.py`
- `backend/app/services/strategy_iteration.py`
- `backend/app/services/paper_broker.py`
- `scripts/start_alpha_dashboard.sh`
- `scripts/stop_alpha_dashboard.sh`

## Validation Commands

```bash
python -m pytest tests -q
python -m backend.app.services.paper_trading_loop --once
```

Latest validation:

```text
python -m pip install -e .[dev] -> passed
python -m pytest tests -q -> 16 passed
python -m backend.app.services.paper_trading_loop --once -> generated pending_owner_approval ticket and filled paper order
two-cycle smoke -> persisted paper portfolio trade_count=2 and cash=9816.10
curl /health -> ok, refresh_interval_seconds=300
curl /dashboard/state -> pending ticket, paper_portfolio, and strategy_tournament visible
curl /dashboard -> contains Paper Portfolio, Strategy Tournament, Run Paper Cycle, and 300000ms refresh
scripts/start_alpha_dashboard.sh -> starts the local dashboard and writes runtime/alpha_dashboard.pid/log
Dashboard HTML/API fallback -> contains System Snapshot, Paper Portfolio, Strategy Tournament, Approval Queue, Run Paper Cycle, and 300000ms refresh
Repo launcher -> outputs/applications/Alpha.command exists and is executable
External legacy launcher observed -> /Users/linzezhang/Downloads/applicatioins/Alpha.command exists and is executable
```

## Unresolved Risks

- Current market data is fixture-only.
- Broker paper integration is not connected yet.
- Dashboard is local MVP only.
- Approval queue is local file/in-memory capable, not a durable production database yet.
- Real broker live order submission remains intentionally out of scope.
- Strategy tournament is fixture-level and not yet walk-forward/OOS validated.

## Next Step

Commit and back up this strategy-iteration/persistent-paper upgrade, then start broker paper integration design.
