# 18806c6 interactive approval queue actions patch backup

本文件记录本地提交 `18806c6 Add interactive approval queue actions` 的远端补丁备份与恢复方式。

## 远端备份文件

- `outputs/patches/18806c6-add-interactive-approval-queue-actions.patch.gz.b64`
- 补丁备份写入 GitHub commit: `4d4bc3a6d537657af007f930ef53fb6cff66e6e7`

当前本机 `git push origin main` 仍被 GitHub HTTPS 凭据阻断：`fatal: could not read Username for 'https://github.com': Device not configured`。因此本地 commit 暂不能直接进入 `main`，本补丁用于后续 agent 或开发者从 GitHub 恢复本地变更。

## 恢复命令

在仓库根目录执行：

```bash
base64 -d outputs/patches/18806c6-add-interactive-approval-queue-actions.patch.gz.b64 | gunzip > /tmp/18806c6-add-interactive-approval-queue-actions.patch
git am /tmp/18806c6-add-interactive-approval-queue-actions.patch
```

## 本地验证结果

- `.venv/bin/python -m pytest tests/test_approval_queue.py tests/test_dashboard_state.py -q` -> `10 passed`
- `.venv/bin/python -m pytest tests -q` -> `27 passed`
- `.venv/bin/python -m backend.app.services.paper_trading_loop --once --queue-path /tmp/alpha_review_queue.json --paper-state-path /tmp/alpha_review_portfolio.json` -> generated pending owner approval ticket and filled paper order with `live_order_submission_enabled=false`
- `git diff --check` -> passed
- Browser dashboard smoke -> `Alpha 控制台` rendered; clicked `标记已复核`; clicked `标记已导出`; backend logs showed both POSTs returned `200 OK`; browser console errors `[]`
- Safety scan -> committed `configs/trading_governor_policy.yaml` keeps `live_trading.enabled: false`; approval export records `live_order_submission_enabled: false`

## 变更摘要

- `ApprovalQueue` 增加 `owner_reviewed`、`owner_rejected`、`broker_ticket_exported` 状态转换。
- 所有状态转换写入 `status_history`、`owner_review` 或 `broker_ticket_export` 审计字段。
- 导出前必须先人工复核；风控阻止票据不能复核或导出；导出仍明确 `live_order_submission_enabled=false`。
- 新增审批队列操作 API：`owner-review`、`reject`、`mark-exported`。
- Dashboard 审批队列增加中文操作按钮和复核/导出指标。
- 更新 README、decision log、requirements alignment、HANDOFF。

## 安全边界

该提交只实现本地审批状态管理，不启用真实 broker 下单，不接收 broker 凭据，不调用真实 `place_order`。