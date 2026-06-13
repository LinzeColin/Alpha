# df5372a local paper broker adapter patch backup

本文件记录本地提交 `df5372a Add local paper broker adapter` 的远端补丁备份与恢复方式。

## 远端备份文件

- `outputs/patches/df5372a-add-local-paper-broker-adapter.patch.gz.b64`
- 补丁备份写入 GitHub commit: `8deb2b4b76409bafc1c9cf294546830f99bea8b8`

由于当前本机 `git push origin main` 无法读取 GitHub HTTPS 用户名，且 SSH push 缺少可用 public key，本地 commit 还不能直接 push 到 `main`。本补丁文件用于保证后续 agent 或开发者可以从 GitHub 恢复本地变更。

## 恢复命令

在仓库根目录执行：

```bash
base64 -d outputs/patches/df5372a-add-local-paper-broker-adapter.patch.gz.b64 | gunzip > /tmp/df5372a-add-local-paper-broker-adapter.patch
git am /tmp/df5372a-add-local-paper-broker-adapter.patch
```

## 本地验证结果

- `.venv/bin/python -m pytest tests/test_broker_paper_adapter.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py tests/test_agent_runtime.py -q` -> `11 passed`
- `.venv/bin/python -m pytest tests -q` -> `23 passed`
- `git diff --check` -> passed
- `.venv/bin/python -m backend.app.services.paper_trading_loop --once --queue-path /tmp/alpha_broker_paper_queue.json --paper-state-path /tmp/alpha_broker_paper_portfolio.json` -> 生成 broker paper receipt，`mode=paper`，`live_order_submission_enabled=false`
- Browser dashboard smoke -> `Alpha 控制台`、`模拟交易执行层`、`允许真实下单 否` 可见，无浏览器错误

## 变更摘要

- 新增 `LocalSandboxPaperBrokerAdapter`，为模拟交易生成 broker-like paper receipt。
- `paper_trading_loop` 接入 paper broker adapter，同时保留原 `paper_order` 兼容字段。
- `agent_runtime`、`/state`、`/paper/broker/status`、dashboard 增加模拟交易执行层状态。
- 增加 adapter、loop、runtime、dashboard 测试。
- 更新 `README.md`、`docs/decision_log.md`、`docs/requirements_alignment.md`、`HANDOFF.md`。

## 安全边界

该提交只实现本地模拟交易执行适配器，不启用真实 broker 下单。默认真实下单仍被禁止，`live_order_submission_enabled=false`。