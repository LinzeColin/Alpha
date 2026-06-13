# Alpha Decision Log

## 2026-06-13: GitHub Is Authoritative

Decision: Use `https://github.com/LinzeColin/Alpha` as the authoritative project backup and continuity surface.

Reason: Future agents need a stable, inspectable state source for code, docs, tests, rules, and handoff.

Consequence: Every meaningful run must commit and push code/docs/test evidence unless blocked.

## 2026-06-13: Execution Boundary

Decision: Alpha will automate paper trading, risk checks, approval queues, and broker-ready order tickets. It will not autonomously submit real-money broker orders.

Reason: Trading systems must preserve owner control at the real-money execution boundary.

Consequence: Committed defaults keep `live_trading.enabled: false`; live candidates enter an approval queue as tickets.

## 2026-06-13: Five-Minute Candidate Refresh

Decision: The order-intent loop has a default refresh cadence of 300 seconds.

Reason: The user requires timely candidate updates while still keeping risk checks and review gates explicit.

Consequence: `paper_trading_loop.run_forever()` remains available for CLI use, and the FastAPI dashboard lifecycle starts an app-managed automatic paper loop that runs immediately and then sleeps for the configured interval.

## 2026-06-13: Ticket Freshness Is Actionability

Decision: Only unexpired `pending_owner_approval` tickets count as owner-actionable live candidates.

Reason: Broker-ready tickets can become stale; a candidate older than its TTL should remain auditable but should not be treated as executable.

Consequence: `ApprovalQueue.summary()` separates fresh pending, expired pending, blocked, and total tickets. The dashboard shows actionability, freshness, and seconds until expiry.

## 2026-06-13: App Bundle Entrypoints

Decision: Alpha should ship a macOS `.app` entrypoint in Downloads and Applications, backed by the same dashboard start script.

Reason: The user needs a stable local webpage workspace entry that behaves like a normal app instead of requiring terminal commands.

Consequence: `outputs/applications/Alpha.applescript` generates `Alpha.app`, and copies were installed to Downloads, user Applications, and system `/Applications`.

## 2026-06-13: Strategy Iteration Requires Walk-Forward Evidence

Decision: Strategy tournament candidates must expose simple out-of-sample evidence: walk-forward return, hit rate, and validation window count.

Reason: Last-window momentum ranking is too weak for strategy promotion. Even fixture-level MVP strategy iteration should show whether a signal had repeated one-step-ahead confirmation.

Consequence: `run_strategy_tournament()` now returns `validation_summary`, and each candidate includes `oos_return`, `hit_rate`, and `validation_windows`. The dashboard tournament table displays these fields.

## 2026-06-13: User-Facing Chinese Display

Decision: Alpha runtime surfaces should display Chinese text for the owner-facing dashboard and local launcher messages.

Reason: The user requires the whole system to be readable in Chinese during operation.

Consequence: `/dashboard` translates titles, buttons, metrics, tables, empty states, and status/actionability values into Chinese. API field names and machine-readable enum values remain stable for tests and automation.

## 2026-06-13: Human Runtime Output Defaults To Chinese

Decision: Owner-facing runtime output should default to Chinese, including dashboard display names and `paper_trading_loop --once` CLI summaries.

Reason: The user requires the operating workspace to be readable without interpreting raw machine enum values.

Consequence: Dashboard rendering maps agent IDs, adapter IDs, strategy IDs, order types, validity, risk reasons, capabilities, and unknown status fallbacks into Chinese. The CLI keeps a `--json` option for raw automation output.

## 2026-06-13: Broker Paper Adapter Boundary

Decision: Paper trading execution should flow through a replaceable broker paper adapter, starting with `LocalSandboxPaperBrokerAdapter`.

Reason: The MVP needs a broker-like paper execution receipt and dashboard visibility before connecting any real broker paper API. This keeps the execution surface testable without accepting credentials or enabling real-money order submission.

Consequence: `PaperTradingLoop` now returns `paper_broker_adapter` and `broker_paper_order` receipts. The dashboard exposes a Chinese "模拟交易执行层" section showing adapter, mode, connection, credential requirement, and whether real order submission is enabled.

## 2026-06-13: Approval Queue Is Interactive But Non-Executing

Decision: Owner-facing approval queue actions may update local ticket state to `owner_reviewed`, `owner_rejected`, or `broker_ticket_exported`, but must not submit broker orders.

Reason: The workspace needs a usable dashboard workflow for reviewing timely broker-ready candidates. The real-money boundary still belongs to the owner inside the broker app/API session.

Consequence: `/orders/approval-queue/{ticket_id}/owner-review`, `/reject`, and `/mark-exported` record status history and review/export metadata. Export requires prior owner review, risk-blocked tickets cannot be reviewed/exported, and exported tickets record `live_order_submission_enabled: false`.

## 2026-06-13: Approval Queue Uses SQLite By Default

Decision: The default runtime approval queue should persist to `runtime/approval_queue.sqlite3`.

Reason: A five-minute autonomous paper loop will create repeated order candidates. The queue must survive dashboard restarts and support reliable owner actions without rewriting a whole JSON file on every transition.

Consequence: `ApprovalQueue` chooses SQLite for `.sqlite`, `.sqlite3`, and `.db` paths, keeps JSON compatibility for `.json`, and exposes storage status to `/orders/approval-queue`, `/owner/summary`, `/agent/status`, and the dashboard.

## 2026-06-13: Market Data Gateway Is Observable And Fail-Soft

Decision: Paper trading and dashboard reads should resolve prices through `MarketDataGateway` instead of directly depending on the sample CSV.

Reason: Strategy iteration and paper trading need a clear path from fixture data toward real public market data while staying reliable when the external source is unavailable.

Consequence: Alpha now supports a cache-first market data gateway with optional Stooq public delayed CSV refresh. Dashboard/API surfaces show provider, source kind, quality, latest date, prices, cache age, and fallback status. External refresh failure falls back to local data and does not enable any live trading behavior.

## 2026-06-13: 30-Day Ops Health Requires Local Evidence

Decision: Alpha should expose a local ops health check and one-click runtime backup before claiming 30-day unattended paper-trading readiness.

Reason: A five-minute automatic loop can appear healthy while the queue, process, logs, backups, or paper portfolio are stale or missing. The owner needs direct evidence that the system is still generating timely candidates and can be recovered after restart.

Consequence: `/ops/health`, `/ops/backup`, `scripts/check_alpha_ops.sh`, and the dashboard "运行健康" panel now summarize automatic loop cadence, SQLite queue durability, paper portfolio state, market data quality, process/log status, latest backup, and the real-money execution boundary.

## 2026-06-13: Ops Maintenance Is App-Managed

Decision: The dashboard application should own scheduled health sampling, runtime backup creation, and backup rotation instead of relying only on manual terminal commands.

Reason: A 30-day E-Safe paper-trading run needs continuous evidence and recoverability even when the owner does not manually trigger backups.

Consequence: FastAPI lifespan starts `AutoOpsMaintenanceRuntime` beside the paper loop. It samples ops health every 300 seconds, writes `runtime/ops_health_history.jsonl`, creates a backup when the latest backup is older than the configured interval, prunes backups to the configured retention count, and exposes state through `/ops/maintenance/status` and the dashboard.

## 2026-06-13: 中文显示是产品验收项

Decision: Alpha 的用户可见运行界面、App/脚本输出、控制台状态、风险原因和人工操作文案必须默认中文显示。

Reason: 用户要求“整个系统彻底的全中文显示”，运行期间不应让 owner 通过 raw enum 才能理解系统状态。

Consequence: API 字段名、内部枚举、工单号、文件路径和股票代码继续保持机器可读格式；Dashboard、CLI 摘要和 owner-facing API 会提供中文映射或 `*_zh` 字段。新增界面或命令输出必须补对应中文展示测试。

## 2026-06-13: Broker-Ready Ticket Export Is Manual-Only

Decision: 已人工复核且仍在有效期内的候选单可以导出为 JSON/CSV 人工录入工单包，但 Alpha 不调用真实经纪商下单接口。

Reason: 用户需要可操作的 broker-ready order ticket；同时真实资金执行边界必须留在 owner 的经纪商确认侧。

Consequence: `/orders/approval-queue/{ticket_id}/broker-ticket` 和 `.csv` 提供标准化工单包，包含中文展示字段、CSV 行、安全提示和 `live_order_submission_enabled: false`。过期工单不能被复核或导出。
