# Alpha 交接说明

时间：2026-06-13，Australia/Sydney

## 当前目标

把 Alpha 打造成 GitHub 备份的本地优先个人量化智能体工作台：自动模拟交易、策略迭代、风险检查、审批队列、经纪商就绪订单工单、运行健康、长运行预检和中文控制台。

## 当前状态

- 权威仓库：`https://github.com/LinzeColin/Alpha`。
- 本地默认真实下单仍禁用，`live_trading.enabled` 不得提交为启用。
- 控制台入口：`/dashboard`；状态接口：`/dashboard/state`。
- 控制台显示、脚本输出、策略校验错误、工单 HTML、工单 CSV 表头、富途牛牛开放网关状态、行情刷新错误、就绪预检工单文案和主要文档已按中文显示规则更新。
- API 机器字段、路径、枚举、工单号、股票代码和 `provider_id=moomoo_opend` 保持稳定；用户可见展示优先使用中文字段或中文标签。
- 模拟经纪商状态/回执、策略锦标赛候选、审批队列时效、风险原因和页面时间显示已补中文展示兜底，前端未知枚举不直接露出英文状态值。
- 新增 `scripts/verify_chinese_display.py`，作为无额外浏览器依赖的中文显示审计门槛。
- 新增 `scripts/verify_dashboard_http_smoke.py`，通过本地 HTTP 检查 `/health`、`/dashboard` 和 `/dashboard/state` 的中文文案、关键中文字段、响应式布局契约和真实下单禁用边界。
- 行情状态提供 `provider_zh`、`source_kind_zh`、`data_quality_zh`、`real_market_data_zh`、`refresh_error_zh` 等中文展示字段；控制台刷新失败优先显示中文错误兜底。
- 经纪商工单 JSON 仍保留机器字段；默认 HTML 视图和 CSV 下载面向人工操作改为中文。
- 富途牛牛开放网关仍只允许只读探测和只读行情快照；不得创建交易上下文、不得解锁交易、不得调用真实下单。
- `scripts/start_alpha_dashboard.sh` 和 `scripts/stop_alpha_dashboard.sh` 修复了变量紧贴中文标点时的 zsh 解析问题。
- 自动模拟交易循环和自动维护循环会分别写入 `runtime/agent_loop_status.json` 与 `runtime/ops_maintenance_status.json`；`/readiness/paper-trading` 和 `/readiness/soak` 可以读取新鲜心跳并校验进程仍存活，避免把已退出的 App 误判为就绪。
- 自动维护循环每轮追加 `runtime/soak_readiness_history.jsonl`；`/readiness/soak/history` 和控制台“长运行预检”显示历史采样数、连续无失败采样数、连续完全通过采样数、最近失败时间和最近采样表。

## 关键决策

- Alpha 可以自动生成候选订单和经纪商就绪工单，但不能自动提交真实资金订单。
- 真实资金执行必须由所有者在经纪商侧确认。
- 所有用户可见运行面默认中文；机器接口保持稳定。
- `/readiness/paper-trading` 是模拟交易交付门槛；`/readiness/soak` 是 30 天长运行开始门槛，不代表已经完成 30 天验证。
- `runtime/soak_readiness_history.jsonl` 是 30 天观察证据，不是 30 天已完成证明；连续无失败采样数必须随真实运行时间积累。

## 当前中文显示相关文件

- `backend/app/api/routes.py`
- `backend/app/services/display_locale.py`
- `backend/app/services/moomoo_broker_probe.py`
- `backend/app/services/ops_health.py`
- `backend/app/services/market_data_gateway.py`
- `backend/app/services/agent_runtime.py`
- `backend/app/services/ops_runtime.py`
- `backend/app/services/paper_readiness.py`
- `backend/app/services/soak_readiness.py`
- `backend/app/services/soak_history.py`
- `backend/app/services/runtime_status.py`
- `backend/app/services/broker_ticket_export.py`
- `backend/app/services/strategy_iteration.py`
- `backend/app/schemas/strategy_dsl.py`
- `scripts/start_alpha_dashboard.sh`
- `scripts/stop_alpha_dashboard.sh`
- `scripts/verify_chinese_display.py`
- `scripts/verify_dashboard_http_smoke.py`
- `tests/test_dashboard_state.py`
- `tests/test_broker_ticket_export.py`
- `tests/test_moomoo_broker_probe.py`
- `tests/test_market_data_gateway.py`
- `tests/test_agent_runtime.py`
- `tests/test_ops_runtime.py`
- `tests/test_paper_readiness.py`
- `tests/test_soak_readiness.py`
- `tests/test_soak_history.py`
- `tests/test_ops_health.py`
- `tests/test_strategy_dsl.py`
- `AGENTS.md`
- `README.md`
- `docs/decision_log.md`
- `docs/requirements_alignment.md`
- `HANDOFF.md`

## 验证结果

已通过：

```bash
.venv/bin/python -m pytest tests/test_soak_history.py tests/test_ops_runtime.py tests/test_dashboard_state.py tests/test_soak_readiness.py -q
# 17 passed

.venv/bin/python -m pytest tests -q
# 77 passed

.venv/bin/python scripts/verify_chinese_display.py
# status_zh=通过, error_count=0

python /Users/linzezhang/.codex/skills/webapp-testing/scripts/with_server.py --server ".venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8125" --port 8125 --timeout 60 -- .venv/bin/python scripts/verify_dashboard_http_smoke.py --base-url http://127.0.0.1:8125 --exercise-actions
# status_zh=通过, error_count=0, checked_layout_contract_count=10, exercised_action_count=2

git diff --check
# passed
```

安全扫描结果：没有发现真实下单启用路径；命中项只包含禁用说明、测试断言和 `live_order_submission_enabled=false` 相关字段。

短周期运行验证：`ALPHA_MARKET_DATA_PROVIDER=moomoo_opend` 下启动 `AutoPaperAgentRuntime` 与 `AutoOpsMaintenanceRuntime` 各完成 1 轮；`runtime/soak_readiness_history.jsonl` 写入 1 条采样，`consecutive_no_fail_count=1`、`latest_fail_count=0`、`completion_status_zh=观察运行中`、`live_order_submission_enabled=false`。该验证只使用本机富途牛牛开放网关只读行情/本地模拟交易，不创建交易上下文、不解锁交易、不提交真实订单。

运行态检查：普通沙箱内绑定 `127.0.0.1` 会触发权限限制；提权后本地 uvicorn HTTP smoke 已验证 `/dashboard`、`/health` 和 `/dashboard/state` 的中文文案、关键中文字段、10 条响应式布局契约和真实下单禁用边界，并安全调用 `/paper/run-once` 与 `/ops/backup`。当前环境可导入 Playwright，但缺少 Playwright Chromium 二进制，系统 Chrome headless 会被关闭，因此尚未完成截图级视觉验收；后续若需要最终视觉证据，建议安装浏览器测试依赖或用 Browser/Chrome 工具打开 `http://127.0.0.1:8000/dashboard` 再截屏。

## 未解决风险

- 30 天长运行尚未完成，只能声明具备开始预检/观察运行条件。
- 外部经纪商模拟接口尚未接入；当前是真实本机只读行情加本地沙盒模拟成交。
- GitHub `main` 可能与远端历史不一致，当前应优先推送备份分支，禁止强推。
- 30 天长运行仍需要真实时间跨度的历史采样；当前心跳只证明 App/循环在当前进程下新鲜运行。

## 下一步

1. 提交并推送长运行采样历史改动到 GitHub 备份分支，建议 `codex/alpha-soak-history-20260613`，不要强推 `main`。
2. 继续补 dashboard 稳定性：增加 Browser/Chrome 或 Playwright 视觉验收脚本，检查长运行预检、长运行历史、审批队列和中文状态在真实页面中不重叠、不露 raw enum。
3. 继续补外部 broker paper API 适配调研和接口壳，但仍不得接入真实下单。
