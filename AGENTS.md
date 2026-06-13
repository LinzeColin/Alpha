# Alpha Development Rules

## Core Goal

Build Alpha as a local-first personal quant agent workspace. The system may automate research, backtesting, paper trading, risk checks, approval queues, broker-ready order tickets, audit logging, and dashboard status.

Committed code must not implement or enable unattended real-money order submission. Real-money execution must remain outside the autonomous agent path and require owner-side broker confirmation.

## GitHub Continuity Rule

The authoritative project repository is:

```text
https://github.com/LinzeColin/Alpha
```

All source code, project rules, docs, Task Packs, handoff notes, decision logs, test evidence, and delivery manifests must be committed and pushed to GitHub after every meaningful run.

Local-only state is not authoritative except:

- uncommitted secrets and `.env` files
- broker credentials and account identifiers
- machine-specific cache files
- runtime queues, logs, and local databases

## Safety Boundaries

- `live_trading.enabled` must remain `false` in committed default config.
- No committed code may directly call a real broker `place_order` endpoint.
- No agent may receive raw broker trading credentials.
- Real broker integration work is limited to read-only probes, broker paper APIs, or owner-confirmed order tickets.
- All live order candidates must be represented as `OrderIntent` and `BrokerReadyOrderTicket`.
- All live candidates must pass policy, risk, audit, kill-switch, idempotency, and freshness gates before entering the approval queue.
- If any policy or audit dependency fails, the system must reject or pause, not continue.

## 中文显示规则

- 用户可见的网页控制台、按钮、表格、状态、错误提示、本地命令摘要和 App 启动/停止输出必须默认中文显示。
- API 字段名、内部枚举、工单号、文件路径、股票代码和协议型机器值可以保持英文/ASCII，以保证测试、MCP、后续券商适配器和自动化流程稳定。
- 新增用户界面或 CLI 输出时，必须为状态、风险原因、执行层名称、策略名称、行情状态和审批操作提供中文展示映射。
- 若必须暴露机器字段给用户，界面应同时显示中文标签或中文解释，不得只展示 raw enum。

## Required Handoff Discipline

Update `HANDOFF.md` when goals, state, decisions, validation, or next steps change. Update `docs/decision_log.md` for durable product or safety decisions.

Every implementation run should report:

- changed files
- commands run
- test results
- remaining risks
- recommended next step

## Default Verification

Use the smallest useful checks first:

```bash
python -m pytest tests -q
python -m backend.app.services.paper_trading_loop --once
```

Run the API locally when touching routes or dashboard behavior:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Then inspect:

```text
http://127.0.0.1:8000/dashboard
http://127.0.0.1:8000/health
```

## Out Of Scope Unless Explicitly Re-approved

- autonomous real-money broker order submission
- leverage, margin, CFDs, options, short selling
- crypto withdrawals or cross-exchange transfers
- third-party financial advice or public buy/sell signals
- managing external capital
