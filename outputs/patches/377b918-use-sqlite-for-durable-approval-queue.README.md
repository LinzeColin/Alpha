# 377b918 SQLite approval queue patch backup

本文件记录本地提交 `377b918 Use SQLite for durable approval queue` 的远端补丁备份与恢复方式。

## 远端备份文件

- `outputs/patches/377b918-use-sqlite-for-durable-approval-queue.patch.gz.b64`
- 补丁备份写入 GitHub commit: `e9c53a7d8983b6d2391207291cefcd63e31c2f17`

当前本机 `git push origin main` 仍被 GitHub HTTPS 凭据阻断：`fatal: could not read Username for 'https://github.com': Device not configured`。因此本地 commit 暂不能直接进入 `main`，本补丁用于后续 agent 或开发者从 GitHub 恢复本地变更。

## 恢复命令

在仓库根目录执行：

```bash
base64 -d outputs/patches/377b918-use-sqlite-for-durable-approval-queue.patch.gz.b64 | gunzip > /tmp/377b918-use-sqlite-for-durable-approval-queue.patch
git am /tmp/377b918-use-sqlite-for-durable-approval-queue.patch
```

## 本地验证结果

- `.venv/bin/python -m pytest tests/test_approval_queue.py tests/test_dashboard_state.py -q` -> `13 passed`
- `.venv/bin/python -m pytest tests -q` -> `30 passed`
- `.venv/bin/python -m backend.app.services.paper_trading_loop --once --queue-path /tmp/alpha_sqlite_queue.sqlite3 --paper-state-path /tmp/alpha_sqlite_portfolio.json` -> generated pending owner approval ticket and filled paper order with SQLite queue path
- `.venv/bin/python -m backend.app.services.paper_trading_loop --once` -> passed with default runtime queue path `runtime/approval_queue.sqlite3`
- `git diff --check` -> passed
- Browser dashboard smoke -> `Alpha 控制台` rendered; `队列存储`、`SQLite`、`持久化：是` visible; browser console errors `[]`
- Safety scan -> committed `configs/trading_governor_policy.yaml` keeps `live_trading.enabled: false`; no new real broker `place_order` path

## 变更摘要

- `ApprovalQueue` 默认支持 SQLite durable backend：`.sqlite`、`.sqlite3`、`.db` 路径走 SQLite。
- `.json` 路径保留 JSON 文件兼容；无路径仍为内存队列。
- SQLite schema 存储 `ticket_id`、`created_at`、`updated_at`、`status` 和完整 `ticket_json`。
- 默认运行时队列从 `runtime/approval_queue.json` 切换到 `runtime/approval_queue.sqlite3`。
- `/orders/approval-queue`、`/owner/summary`、`/agent/status` 和 dashboard state 暴露 storage status。
- Dashboard 中文显示 `队列存储：SQLite / 持久化：是`。
- `.gitignore` 增加 `*.sqlite3`，防止本地运行态数据库误提交。
- 更新 README、decision log、requirements alignment、HANDOFF。

## 安全边界

该提交只增强本地审批队列持久化，不启用真实 broker 下单，不接收 broker 凭据，不调用真实 `place_order`。