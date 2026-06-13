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
- Strategy iteration now includes walk-forward one-step OOS return, hit rate, and validation window counts.
- Dashboard state includes `paper_portfolio` and `strategy_tournament`.
- Local launcher scripts exist at `scripts/start_alpha_dashboard.sh` and `scripts/stop_alpha_dashboard.sh`.
- Dashboard startup now starts the app-managed `AutoPaperAgentRuntime`: one immediate paper cycle, then 300-second refreshes.
- `/agent/loop/status` exposes automatic loop state, run count, last result summary, next run time, and errors.
- `scripts/start_alpha_dashboard.sh` now performs a startup health check and removes stale pid files on failure.
- Approval queue now derives ticket freshness from `expires_at`; only fresh `pending_owner_approval` tickets count as owner-actionable.
- Dashboard user-facing display is now Chinese: page title, buttons, metric labels, table headers, empty states, and status/actionability mappings render in Chinese while API machine fields remain stable.
- Local launcher scripts now print Chinese startup/shutdown messages.
- Paper trading execution now flows through `LocalSandboxPaperBrokerAdapter`, which returns broker-like paper receipts without credentials or real order submission.
- `/paper/broker/status` and the dashboard "模拟交易执行层" section expose paper adapter status, mode, connection, credential requirement, live-order disabled state, trade count, and latest simulated fill.
- Approval queue now has owner-facing review transitions: `owner_reviewed`, `owner_rejected`, and `broker_ticket_exported`, exposed through API routes and Chinese dashboard buttons.
- Approval queue export is non-executing: export requires prior owner review and records `live_order_submission_enabled: false`; risk-blocked tickets cannot be reviewed/exported.
- Approval queue now uses SQLite by default at `runtime/approval_queue.sqlite3`; `.json` paths remain supported for compatibility and one-time sibling migration.
- `/orders/approval-queue`, `/owner/summary`, `/agent/status`, and dashboard state expose approval queue storage status.
- AppleScript `Alpha.app` is installed at `/Users/linzezhang/Downloads/Alpha.app`, `/Users/linzezhang/Applications/Alpha.app`, and `/Applications/Alpha.app`.
- GitHub connector backup now contains the core runtime/dashboard/code/test changes from this run.
- Repo launcher exists at `outputs/applications/Alpha.command`; an older external copy was observed at `/Users/linzezhang/Downloads/applicatioins/Alpha.command`.

## Key Decisions

- The system will automate paper trading and order ticket generation.
- The system will not autonomously submit real-money broker orders.
- Broker-ready real-money candidates flow through `OrderIntent -> risk check -> approval queue -> BrokerReadyOrderTicket`.
- Refresh cadence target is 300 seconds by default.
- Use one app-managed paper loop; do not start a second external agent process beside the dashboard.
- User-visible runtime surfaces should display Chinese; API field names and enum values stay machine-readable and stable.
- Paper execution adapters may be broker-like, but committed defaults must stay local sandbox or broker paper/read-only only.
- Dashboard approval actions update local ticket state only; they do not call any real broker order endpoint.
- Default durable runtime state is local-first: SQLite approval queue plus JSON paper portfolio.

## Files To Read First

- `AGENTS.md`
- `README.md`
- `HANDOFF.md`
- `docs/decision_log.md`
- `configs/trading_governor_policy.yaml`
- `backend/app/services/paper_trading_loop.py`
- `backend/app/services/strategy_iteration.py`
- `backend/app/services/paper_broker.py`
- `backend/app/services/agent_runtime.py`
- `outputs/applications/Alpha.applescript`
- `outputs/applications/Alpha.app`
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
python -m pytest tests -q -> 20 passed
python -m backend.app.services.paper_trading_loop --once -> generated pending_owner_approval ticket and filled paper order
two-cycle smoke -> persisted paper portfolio trade_count=2 and cash=9816.10
curl /health -> ok, refresh_interval_seconds=300
curl /dashboard/state -> pending ticket, paper_portfolio, and strategy_tournament visible
curl /agent/loop/status -> app-managed loop visible with run_count=1, status=sleeping, next_run_at=300 seconds later, error_count=0
curl /dashboard -> 控制台 HTML 可访问，并包含 300000ms 前端刷新配置
scripts/start_alpha_dashboard.sh -> starts the local dashboard, app-managed paper loop, and writes runtime/alpha_dashboard.pid/log
scripts/stop_alpha_dashboard.sh -> waits for uvicorn shutdown and releases port 8000 cleanly
uvicorn foreground runtime check -> /agent/loop/status showed enabled=true, task_running=true, interval_seconds=300, run_count=1, next_run_at populated, error_count=0
freshness validation -> pytest 20 passed; isolated paper loop generated ticket.expires_at matching intent.expires_at
app launcher validation -> plutil -lint passed for repo, Downloads, user Applications, and system Applications Alpha.app copies
app launch validation -> open -n /Users/linzezhang/Downloads/Alpha.app started dashboard; /agent/loop/status returned task_running=true, interval_seconds=300, run_count=1, error_count=0
approval queue freshness API -> /orders/approval-queue returned fresh_pending_count=3, expired_pending_count=11, and fresh/expired actionability fields
strategy tournament validation -> 9 candidates, 9 validated, winner momentum_QQQ_20d, hit_rate=1.0, oos_return=0.025701, validation_windows=9
Dashboard Chinese display test -> .venv/bin/python -m pytest tests/test_dashboard_state.py -q -> 4 passed
Full regression -> .venv/bin/python -m pytest tests -q -> 21 passed
Diff hygiene -> git diff --check -> passed
浏览器中文控制台验证 -> 标题 Alpha 控制台, lang zh-CN, 旧英文可见短语=[], 已成功点击 运行模拟交易周期, 控制台错误=[]
Launcher text verification -> scripts/start_alpha_dashboard.sh prints Chinese startup and health-check messages
Broker paper adapter unit tests -> .venv/bin/python -m pytest tests/test_broker_paper_adapter.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py tests/test_agent_runtime.py -q -> 11 passed
Broker paper adapter full regression -> .venv/bin/python -m pytest tests -q -> 23 passed
Broker paper isolated loop -> generated broker_paper_order status=filled, mode=paper, live_order_submission_enabled=false, broker_order_id=paper_...
Browser broker execution layer verification -> dashboard showed 模拟交易执行层, 模式=模拟交易, 允许真实下单=否, consoleErrors=[]
Repo launcher -> outputs/applications/Alpha.command exists and is executable
External app launchers -> /Users/linzezhang/Downloads/Alpha.app, /Users/linzezhang/Applications/Alpha.app, and /Applications/Alpha.app exist and pass plist validation
Approval queue review actions -> pending ticket can be marked owner_reviewed, then broker_ticket_exported; exported ticket records live_order_submission_enabled=false
SQLite approval queue validation -> ticket persists across `ApprovalQueue` instances, owner review/export survives reload, and storage status reports backend=sqlite durable=true
```

## Unresolved Risks

- Current market data is fixture-only.
- External broker paper API integration is not connected yet; local sandbox paper adapter abstraction now exists.
- Dashboard is local MVP only.
- Approval queue is SQLite-backed locally, but still needs production-grade backup/rotation and multi-process contention hardening before long unattended runs.
- Real broker live order submission remains intentionally out of scope.
- Strategy tournament is still fixture-level; it now has simple walk-forward/OOS metrics, but not multi-year OOS, cost-model, slippage-model, or walk-forward portfolio validation.
- Local `git push -u origin main` is blocked by missing HTTPS credentials (`could not read Username`); GitHub connector synced core runtime files, but older `docs/seed_pack/**` and `docs/task_pack_seed/**` still need a normal authenticated push or follow-up connector sync.

## Next Step

Authenticate GitHub CLI/HTTPS push or continue connector-based sync, then implement a concrete broker paper/read-only adapter for the user's chosen broker or add real market data ingestion.
