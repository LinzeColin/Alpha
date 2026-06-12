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

## Validation Commands

```bash
python -m pytest tests -q
python -m backend.app.services.paper_trading_loop --once
```

Latest validation:

```text
python -m pip install -e .[dev] -> passed
python -m pytest tests -q -> 11 passed
python -m backend.app.services.paper_trading_loop --once -> generated pending_owner_approval ticket and filled paper order
curl /health -> ok, refresh_interval_seconds=300
curl /dashboard/state -> pending ticket visible
Browser dashboard check -> rendered and Run Paper Cycle increased pending tickets
```

## Unresolved Risks

- Current market data is fixture-only.
- Broker paper integration is not connected yet.
- Dashboard is local MVP only.
- Approval queue is local file/in-memory capable, not a durable production database yet.
- Real broker live order submission remains intentionally out of scope.

## Next Step

Commit and push the first GitHub-backed MVP baseline, then start broker paper integration design.
