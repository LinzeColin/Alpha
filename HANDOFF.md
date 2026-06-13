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
- Every paper cycle now appends strategy tournament evidence to `runtime/strategy_tournament_history.jsonl`.
- `/strategy/tournament/history` and dashboard "策略迭代历史" expose run count, latest winner, winner streak, stability ratio, OOS return, hit rate, decision, and market-data quality.
- Strategy history records and summaries now provide owner-facing Chinese fields such as `winner_strategy_id_zh`, `winner_decision_zh`, and `market_data_quality_zh`.
- Every paper cycle now appends paper portfolio performance evidence to `runtime/paper_performance_history.jsonl`.
- `/paper/performance/history` and dashboard "模拟绩效" expose run count, latest equity, cumulative return, latest equity change, high watermark, max drawdown, current drawdown, and recent equity rows.
- Paper execution now includes a fixed-cost/slippage model: 买入成交使用 5.00 个基点的模拟滑点和 1.00 AUD 模拟佣金，并在 API/dashboard/CLI 中显示参考价、成交价、佣金、执行模型和累计佣金；面向用户的文本统一显示为“基点”。
- Dashboard state includes `paper_portfolio` and `strategy_tournament`.
- Local launcher scripts exist at `scripts/start_alpha_dashboard.sh` and `scripts/stop_alpha_dashboard.sh`.
- Dashboard startup now starts the app-managed `AutoPaperAgentRuntime`: one immediate paper cycle, then 300-second refreshes.
- `/agent/loop/status` exposes automatic loop state, run count, last result summary, next run time, and errors.
- `scripts/start_alpha_dashboard.sh` now performs a startup health check and removes stale pid files on failure.
- Approval queue now derives ticket freshness from `expires_at`; only fresh `pending_owner_approval` tickets count as owner-actionable.
- Dashboard user-facing display is now Chinese: page title, buttons, metric labels, table headers, empty states, and status/actionability mappings render in Chinese while API machine fields remain stable.
- Dashboard display now also localizes agent names, adapter names, account labels, strategy IDs, order type/time-in-force, risk reasons, and unknown status fallbacks.
- `python -m backend.app.services.paper_trading_loop --once` now defaults to a Chinese human-readable summary; use `--json` for raw machine JSON output.
- Local launcher scripts now print Chinese startup/shutdown messages.
- Paper trading execution now flows through `LocalSandboxPaperBrokerAdapter`, which returns broker-like paper receipts without credentials or real order submission.
- `/paper/broker/status` and the dashboard "模拟交易执行层" section expose paper adapter status, mode, connection, credential requirement, live-order disabled state, trade count, and latest simulated fill.
- `/broker/moomoo/status` and the dashboard "Moomoo OpenD" section now expose local Moomoo OpenD read-only probe status: Python API package availability, local OpenD port, read-only readiness, trade unlock disabled state, and real-order submission disabled state.
- Approval queue now has owner-facing review transitions: `owner_reviewed`, `owner_rejected`, and `broker_ticket_exported`, exposed through API routes and Chinese dashboard buttons.
- Approval queue export is non-executing: export requires prior owner review and records `live_order_submission_enabled: false`; risk-blocked tickets cannot be reviewed/exported.
- Broker-ready order tickets now have manual-only JSON/CSV export packages at `/orders/approval-queue/{ticket_id}/broker-ticket` and `/broker-ticket.csv`, plus a Chinese owner-facing HTML view at `/broker-ticket/view`.
- Dashboard owner actions now include "查看工单" and "下载工单表格" for reviewed/exported tickets; "查看工单" opens the Chinese HTML view rather than raw JSON.
- The backend now rejects owner review or broker-ticket export for expired tickets, preserving the 300-second freshness gate beyond the UI layer.
- Approval queue now uses SQLite by default at `runtime/approval_queue.sqlite3`; `.json` paths remain supported for compatibility and one-time sibling migration.
- `/orders/approval-queue`, `/owner/summary`, `/agent/status`, and dashboard state expose approval queue storage status.
- Market data now flows through `MarketDataGateway`: cache-first, fixture fallback, optional Stooq public delayed CSV refresh, and visible dashboard/API source quality.
- `/market-data/status`, `/market-data/refresh`, and dashboard "行情数据" expose provider, source kind, data quality, latest date, latest prices, cache age, and refresh status.
- `/ops/health`, `/ops/backup`, `scripts/check_alpha_ops.sh`, and dashboard "运行健康" now expose 30-day E-Safe operational evidence: loop cadence, SQLite queue durability, paper portfolio state, Moomoo OpenD read-only probe status, market data quality, process/log status, latest backup, and live-order safety boundary.
- Runtime backups are written locally under `runtime/backups/alpha_state_*/` and include a SQLite approval queue snapshot, paper portfolio, available market-data cache, PID, log tail, and manifest.
- Dashboard startup now also starts the app-managed `AutoOpsMaintenanceRuntime`: health sampling every 300 seconds, stale-backup creation, backup rotation, and JSONL health history.
- `/ops/maintenance/status` exposes automatic maintenance state, run count, backup count, next maintenance time, history file, retention config, and Chinese display fields.
- `/readiness/paper-trading`, dashboard "交付就绪", and `python -m backend.app.services.paper_readiness` now expose a 6月20日 paper-trading delivery readiness report covering automatic loop, strategy iteration, paper execution, OrderIntent, risk checks, approval queue, broker-ready ticket, five-minute freshness, local App entry, and real-order boundary.
- Owner-facing API/status surfaces now include non-breaking Chinese display fields such as `status_zh`, `reason_zh`, `enabled_zh`, and `task_running_zh`; raw machine fields remain stable.
- Chinese display coverage includes FastAPI/OpenAPI metadata, owner summary actions, approval queue storage/freshness/actionability, HTTP error detail, and Moomoo OpenD next-step guidance.
- `AGENTS.md` now records the product rule: user-visible dashboard, App/script output, statuses, risk reasons, and owner-facing messages must default to Chinese.
- `scripts/start_alpha_dashboard.sh` now performs a post-health-check stability confirmation before reporting startup success.
- AppleScript `Alpha.app` is installed at `/Users/linzezhang/Downloads/Alpha.app`, `/Users/linzezhang/Applications/Alpha.app`, and `/Applications/Alpha.app`.
- GitHub connector backup now contains the core runtime/dashboard/code/test changes from this run.
- Repo launcher exists at `outputs/applications/Alpha.command`; an older external copy was observed at `/Users/linzezhang/Downloads/applicatioins/Alpha.command`.

## Key Decisions

- The system will automate paper trading and order ticket generation.
- The system will not autonomously submit real-money broker orders.
- Broker-ready real-money candidates flow through `OrderIntent -> risk check -> approval queue -> BrokerReadyOrderTicket`.
- Refresh cadence target is 300 seconds by default.
- Use one app-managed paper loop; do not start a second external agent process beside the dashboard.
- User-visible runtime surfaces must display Chinese; API field names, enum values, ticket IDs, paths, and symbols stay machine-readable and stable.
- Owner-facing API errors must return a stable machine `code` plus Chinese `message_zh`.
- Paper-trading delivery readiness is a separate gate from ops health; do not claim June 20 readiness unless `/readiness/paper-trading` has no failing items under the app-managed runtime.
- If a raw machine value must be shown to the owner, show it with a Chinese label or adjacent Chinese explanation.
- Paper execution adapters may be broker-like, but committed defaults must stay local sandbox or broker paper/read-only only.
- Dashboard approval actions update local ticket state only; they do not call any real broker order endpoint.
- Default durable runtime state is local-first: SQLite approval queue plus JSON paper portfolio.
- Raw JSON/CSV broker-ticket outputs remain available for automation and manual broker import, but the default dashboard owner view must be Chinese HTML.
- Moomoo OpenD integration starts as a read-only environment probe only; it must not create an unlocked trade context or call any real order method.

## Files To Read First

- `AGENTS.md`
- `README.md`
- `HANDOFF.md`
- `docs/decision_log.md`
- `configs/trading_governor_policy.yaml`
- `backend/app/services/paper_trading_loop.py`
- `backend/app/services/market_data_gateway.py`
- `backend/app/services/moomoo_broker_probe.py`
- `backend/app/services/ops_health.py`
- `backend/app/services/ops_runtime.py`
- `backend/app/services/display_locale.py`
- `backend/app/services/paper_performance.py`
- `backend/app/services/broker_paper_adapter.py`
- `backend/app/services/strategy_journal.py`
- `backend/app/services/live_broker.py`
- `backend/app/services/broker_ticket_export.py`
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
python -m backend.app.services.paper_trading_loop --once --json
curl http://127.0.0.1:8000/market-data/status
curl http://127.0.0.1:8000/paper/performance/history
curl http://127.0.0.1:8000/broker/moomoo/status
curl http://127.0.0.1:8000/strategy/tournament/history
curl http://127.0.0.1:8000/ops/health
curl http://127.0.0.1:8000/ops/maintenance/status
curl http://127.0.0.1:8000/readiness/paper-trading
curl http://127.0.0.1:8000/orders/approval-queue/{ticket_id}/broker-ticket
curl http://127.0.0.1:8000/orders/approval-queue/{ticket_id}/broker-ticket/view
curl http://127.0.0.1:8000/orders/approval-queue/{ticket_id}/broker-ticket.csv
scripts/check_alpha_ops.sh --backup
python -m backend.app.services.paper_readiness
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
Full Chinese display validation -> dashboard HTML/user-facing mappings include Chinese agent/adapter/order/risk labels; CLI summary hides raw status IDs while preserving --json for automation
Market data gateway validation -> fixture fallback, mocked Stooq refresh, paper loop market_data status, and dashboard market data panel covered by tests
Real Stooq refresh attempt -> sandbox DNS blocked; non-sandbox reached TLS but failed local Python certificate verification (`CERTIFICATE_VERIFY_FAILED`); fallback remained functional
Ops health target tests -> .venv/bin/python -m pytest tests/test_ops_health.py tests/test_dashboard_state.py -q -> 8 passed
Full regression after ops health -> .venv/bin/python -m pytest tests -q -> 35 passed
CLI ops health -> scripts/check_alpha_ops.sh reported stale PID as unavailable before service restart; this exposed a real stale-runtime condition
CLI runtime backup -> scripts/check_alpha_ops.sh --backup generated runtime/backups/alpha_state_20260613T023557Z
Foreground uvicorn loop verification -> /agent/loop/status returned enabled=true, task_running=true, interval_seconds=300, run_count=1, error_count=0, next_run_at populated, latest ticket pending_owner_approval, broker_paper_order_status=filled
Ops health API verification -> /ops/health returned overall_status=degraded, pass_count=6, warn_count=2, fail_count=0; warnings were fixture market data and stale startup-script PID while the app-managed loop was running
Ops backup API verification -> POST /ops/backup generated runtime/backups/alpha_state_20260613T023753Z and health_after_backup retained fail_count=0
Dashboard Browser verification -> title Alpha 控制台, lang zh-CN, 运行健康/生成运行备份/总体状态/安全边界/检查项 visible, forbidden English phrases=[], browserErrors=[]
Start script hardening -> scripts/start_alpha_dashboard.sh now rechecks PID and /health one second after initial readiness before reporting success
Diff hygiene -> git diff --check -> passed
Safety scan -> no new real broker place_order path; committed live-order defaults and runtime boundary remain disabled
Ops maintenance target tests -> .venv/bin/python -m pytest tests/test_ops_runtime.py tests/test_ops_health.py tests/test_dashboard_state.py -q -> 10 passed
Automatic maintenance full regression -> .venv/bin/python -m pytest tests -q -> 37 passed
Full Chinese display target tests -> .venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_agent_runtime.py tests/test_ops_runtime.py tests/test_live_broker_fail_closed.py -q -> 10 passed
Full Chinese display full regression -> .venv/bin/python -m pytest tests -q -> 38 passed
Runtime Chinese API verification -> /health returned status_zh=正常 and mode_zh=研究、模拟交易与候选订单人工复核模式
Runtime Chinese loop verification -> /agent/loop/status returned status_zh=等待下次运行, task_running_zh=是, ticket_status_zh=待人工确认, broker_paper_order_status_zh=模拟成交
Runtime Chinese maintenance verification -> /ops/maintenance/status returned status_zh=等待下次维护, task_running_zh=是, rotation_status_zh=未变化, history_row_count=5
Fail-closed live intent Chinese verification -> POST /live/order-intent returned status_zh=已拒绝, reason_zh=策略已禁用真实资金交易, message_zh=真实资金下单被拒绝
Dashboard HTML Chinese verification -> /dashboard contains Alpha 控制台, 运行模拟交易周期, 自动维护, 等待下次维护; forbidden English phrases checked in source query were absent
Diff hygiene after Chinese display changes -> git diff --check -> passed
Broker ticket export target tests -> .venv/bin/python -m pytest tests/test_broker_ticket_export.py tests/test_approval_queue.py tests/test_dashboard_state.py -q -> 19 passed
Broker ticket export full regression -> .venv/bin/python -m pytest tests -q -> 42 passed
Broker ticket export runtime API verification -> generated ticket_a03c19291ad8, owner_reviewed, broker-ticket manual_entry_allowed=true, live_order_submission_enabled=false, CSV header present, marked broker_ticket_exported
Broker ticket export safety scan -> no new real broker place_order path; new export package records live_order_submission_enabled=false
Strategy journal target tests -> .venv/bin/python -m pytest tests/test_strategy_journal.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py tests/test_strategy_iteration.py -q -> 14 passed
Strategy journal full regression -> .venv/bin/python -m pytest tests -q -> 44 passed
Strategy journal diff hygiene -> git diff --check -> passed
Full Chinese display reinforcement -> strategy history API now returns winner_strategy_id_zh, winner_decision_zh, market_data_quality_zh; dashboard and CLI summary prefer Chinese display fields
Runtime strategy history verification -> POST /paper/run-once returned strategy_journal.status_zh=已写入, winner_strategy_id_zh=动量策略 QQQ 20日, winner_decision_zh=可进入模拟交易, live_order_submission_enabled=false
Runtime strategy history API verification -> GET /strategy/tournament/history returned run_count=3, current_winner_streak=3, stability_ratio_zh=100.00%, latest_winner_strategy_id_zh=动量策略 QQQ 20日
Browser dashboard Chinese verification -> /dashboard lang=zh-CN, 策略迭代历史/策略稳定度/动量策略 QQQ 20日/可进入模拟交易 visible, forbidden English/raw enum phrases=[], browser console errors=0
Safety scan after strategy journal -> no new real broker place_order path; committed dashboard/API still report live_order_submission_enabled=false
Paper performance target tests -> .venv/bin/python -m pytest tests/test_paper_performance.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py -q -> 13 passed
Paper performance full regression -> .venv/bin/python -m pytest tests -q -> 46 passed
Paper performance diff hygiene -> git diff --check -> passed
Paper performance safety scan -> no new real broker place_order path; live-order submission remains disabled
Runtime paper performance verification -> POST /paper/run-once returned paper_performance.status_zh=已写入, latest_record.strategy_id_zh=动量策略 TLT 20日, total_return_zh=0.00%, live_order_submission_enabled=false
Runtime paper performance API verification -> GET /paper/performance/history returned run_count=2, latest_total_equity=10000.0, total_return_zh=0.00%, max_drawdown_zh=0.00%, latest_trade_side_zh=买入
Browser paper performance verification -> /dashboard lang=zh-CN, 模拟绩效/模拟收益率/累计收益率/最大回撤/权益高水位/动量策略 TLT 20日 visible, forbidden English/raw enum phrases=[], browser console errors=0
Execution cost target tests -> .venv/bin/python -m pytest tests/test_broker_paper_adapter.py tests/test_paper_broker_persistence.py tests/test_paper_performance.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py tests/test_agent_runtime.py -q -> 17 passed
Execution cost full regression -> .venv/bin/python -m pytest tests -q -> 46 passed
Execution cost diff hygiene -> git diff --check -> passed
Execution cost safety scan -> no new real broker place_order path; live-order submission remains disabled
Runtime execution cost verification -> POST /paper/run-once returned execution_model_zh=固定佣金与滑点模型, average_fill_price=91.996, reference_price=91.95, commission=1.0, slippage_bps=5.0, live_order_submission_enabled=false
Runtime dashboard state cost verification -> /dashboard/state exposed paper_broker_status.execution_model_zh=固定佣金与滑点模型, commission_per_order=1.0, slippage_bps=5.0, paper_performance.latest_total_commission=3.0
Browser execution cost verification -> /dashboard lang=zh-CN, 固定佣金与滑点模型/模拟滑点/单笔佣金/累计佣金/最近成交成本 visible, forbidden English/raw enum phrases=[], browser console errors=0
Chinese broker-ticket view target tests -> .venv/bin/python -m pytest tests/test_broker_ticket_export.py tests/test_dashboard_state.py tests/test_broker_paper_adapter.py tests/test_paper_trading_loop.py tests/test_agent_runtime.py -q -> 18 passed
Chinese broker-ticket view full regression -> .venv/bin/python -m pytest tests -q -> 47 passed
Chinese broker-ticket view diff hygiene -> git diff --check -> passed
Chinese broker-ticket view safety scan -> no new real broker place_order path; live-order submission remains disabled
Chinese unit display scan -> owner-facing `bps` text removed from dashboard/CLI/cost receipt; raw `slippage_bps` machine fields remain for API stability
Runtime broker-ticket view verification -> generated ticket_fcd7cb8153f4, owner_reviewed, `/broker-ticket/view` returned Alpha 经纪商就绪工单, 仅供所有者在经纪商系统中人工确认录入, no raw manual_owner_broker_confirmation_only
Dashboard runtime view-path verification -> `/dashboard` lang zh-CN, contains `/broker-ticket/view`, 未出现英文滑点单位；Browser DOM check also confirmed the ticket button onclick target before Browser connection interrupted
Moomoo read-only probe target tests -> .venv/bin/python -m pytest tests/test_moomoo_broker_probe.py tests/test_dashboard_state.py tests/test_ops_health.py tests/test_broker_ticket_export.py tests/test_broker_paper_adapter.py -q -> 20 passed
Moomoo read-only probe full regression -> .venv/bin/python -m pytest tests -q -> 51 passed
Moomoo read-only probe diff hygiene -> git diff --check -> passed
Moomoo read-only probe safety scan -> no new real broker place_order/unlock_trade path; live-order submission remains disabled
Runtime Moomoo probe verification -> GET /broker/moomoo/status returned status_zh=API 包未安装, opend_connected=true, package_available=false, read_only_ready=false, live_order_submission_enabled=false, trade_unlock_required=false
Runtime dashboard Moomoo verification -> GET /dashboard/state exposed Moomoo OpenD mode_zh=只读连接探测 and forbidden_operations_zh includes 解锁交易/提交真实资金订单/修改真实账户
Runtime ops health Moomoo verification -> GET /ops/health included Moomoo OpenD 只读探测 as warn because OpenD port is reachable but current .venv cannot import moomoo/futu API package; real-order submission false
Owner-facing Chinese API reinforcement target tests -> .venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_approval_queue.py tests/test_moomoo_broker_probe.py tests/test_live_broker_fail_closed.py -q -> 23 passed
Owner-facing Chinese API reinforcement full regression -> .venv/bin/python -m pytest tests -q -> 53 passed
Owner-facing Chinese API reinforcement diff hygiene -> git diff --check -> passed
Owner-facing Chinese API reinforcement safety scan -> no new real broker place_order/unlock_trade path; live-order submission remains disabled
Moomoo local environment recheck -> lsof shows `moomoo_Op` listening on 127.0.0.1:11111; escalated read-only `nc -zv 127.0.0.1 11111` succeeded; sandboxed socket checks may return Operation not permitted
Moomoo API package recheck -> system `python3 -m pip show moomoo futu-api futu` and `.venv/bin/python -m pip show moomoo futu-api futu` both reported package not found
Alpha Moomoo probe recheck -> escalated `.venv/bin/python` probe returned status=api_missing, status_zh=API 包未安装, opend_connected=true, package_available=false
Paper readiness target tests -> .venv/bin/python -m pytest tests/test_paper_readiness.py tests/test_dashboard_state.py -q -> 11 passed
Paper readiness full regression -> .venv/bin/python -m pytest tests -q -> 55 passed
Paper readiness CLI verification -> .venv/bin/python -m backend.app.services.paper_readiness returned overall_status_zh=不可交付, pass/warn/fail=7/1/2 because no live loop snapshot and no fresh pending ticket in the current runtime state
Paper readiness safety scan -> no new real broker place_order/unlock_trade path; readiness report states it does not submit real-money orders
```

## Unresolved Risks

- Market data gateway exists, but default mode remains cache/fixture fallback; Stooq refresh is public delayed data and not broker-grade real-time market data.
- This machine's current Python SSL trust chain blocked live Stooq refresh during validation; do not disable SSL verification by default.
- External broker paper API integration is not connected yet; local sandbox paper adapter abstraction, Moomoo OpenD read-only probe, and manual broker-ready JSON/CSV/Chinese HTML ticket export now exist.
- Moomoo OpenD is installed and listening on `127.0.0.1:11111`; Codex's sandboxed socket checks may be blocked, but an escalated read-only port check succeeded. The project `.venv` still cannot import `moomoo` or `futu`; install the correct API package into `.venv` before building quote/account read-only calls.
- `/readiness/paper-trading` and `python -m backend.app.services.paper_readiness` now exist; current CLI evidence is `不可交付` until the app-managed loop is running and a fresh pending candidate ticket exists.
- Dashboard is local MVP only.
- Approval queue is SQLite-backed locally and automatic backup/rotation now exists; it still needs a normal macOS `.app` long-run soak and multi-process contention hardening before claiming unattended 30-day robustness.
- The current execution environment may reclaim `nohup` background servers between tool calls; foreground uvicorn verified the app runtime, and the start script now detects post-health-check instability, but final `.app` long-run verification should be done from the user's normal macOS session.
- Real broker live order submission remains intentionally out of scope.
- Strategy tournament is still fixture-level; it now has simple walk-forward/OOS metrics, persistent strategy history, persistent paper performance history, and a fixed paper execution cost model, but not multi-year OOS, broker-specific fee schedules, borrow costs, tax lots, or walk-forward portfolio validation.
- Local `git push -u origin main` is blocked by missing HTTPS credentials (`could not read Username`); GitHub connector synced core runtime files, but older `docs/seed_pack/**` and `docs/task_pack_seed/**` still need a normal authenticated push or follow-up connector sync.

## Next Step

Authenticate GitHub CLI/HTTPS push or continue connector-based sync, then install the Moomoo/Futu Python API into the project `.venv`, implement read-only quote/account probes, and run a normal macOS `.app` long-run soak.
