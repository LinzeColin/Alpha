# Alpha 交接说明

时间：2026-06-13，Australia/Sydney

## 当前目标

把 Alpha 打造成 GitHub 备份的本地优先个人量化智能体工作台：自动模拟交易、策略迭代、风险检查、审批队列、经纪商就绪订单工单、运行健康、长运行预检和中文控制台。

## 当前状态

- 权威仓库：`https://github.com/LinzeColin/Alpha`。
- 本地默认真实下单仍禁用，`live_trading.enabled` 不得提交为启用。
- 控制台入口：`/dashboard`；状态接口：`/dashboard/state`。
- 控制台显示、脚本输出、策略校验错误、工单 HTML、工单 CSV 表头、富途牛牛开放网关状态和主要文档已按中文显示规则更新。
- API 机器字段、路径、枚举、工单号、股票代码和 `provider_id=moomoo_opend` 保持稳定；用户可见展示优先使用中文字段或中文标签。
- 经纪商工单 JSON 仍保留机器字段；默认 HTML 视图和 CSV 下载面向人工操作改为中文。
- 富途牛牛开放网关仍只允许只读探测和只读行情快照；不得创建交易上下文、不得解锁交易、不得调用真实下单。
- `scripts/start_alpha_dashboard.sh` 和 `scripts/stop_alpha_dashboard.sh` 修复了变量紧贴中文标点时的 zsh 解析问题。

## 关键决策

- Alpha 可以自动生成候选订单和经纪商就绪工单，但不能自动提交真实资金订单。
- 真实资金执行必须由所有者在经纪商侧确认。
- 所有用户可见运行面默认中文；机器接口保持稳定。
- `/readiness/paper-trading` 是模拟交易交付门槛；`/readiness/soak` 是 30 天长运行开始门槛，不代表已经完成 30 天验证。

## 当前中文显示相关文件

- `backend/app/api/routes.py`
- `backend/app/services/display_locale.py`
- `backend/app/services/moomoo_broker_probe.py`
- `backend/app/services/ops_health.py`
- `backend/app/services/market_data_gateway.py`
- `backend/app/services/broker_ticket_export.py`
- `backend/app/schemas/strategy_dsl.py`
- `scripts/start_alpha_dashboard.sh`
- `scripts/stop_alpha_dashboard.sh`
- `tests/test_dashboard_state.py`
- `tests/test_broker_ticket_export.py`
- `tests/test_moomoo_broker_probe.py`
- `tests/test_market_data_gateway.py`
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
.venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_broker_ticket_export.py tests/test_moomoo_broker_probe.py tests/test_market_data_gateway.py tests/test_strategy_dsl.py tests/test_ops_health.py -q
# 32 passed

.venv/bin/python -m pytest tests -q
# 64 passed

git diff --check
# passed
```

安全扫描结果：没有发现真实下单启用路径；命中项只包含禁用说明、测试断言和 `live_order_submission_enabled=false` 相关字段。

运行态检查：沙箱对本机 HTTP 读取和部分 Python 直接导入调用有阻塞/超时现象；启动脚本 bug 已在本轮修复。控制台静态 HTML 中文显示由测试覆盖，临时 HTTP 读取曾验证到页面包含“富途牛牛开放网关（只读）/富途行情/接口包/软件开发包可导入”，且旧英文标签为空；后续若需要最终视觉证据，建议用 Browser/Chrome 工具或用户本机浏览器打开 `http://127.0.0.1:8000/dashboard` 再截屏。

## 未解决风险

- 30 天长运行尚未完成，只能声明具备开始预检/观察运行条件。
- 外部经纪商模拟接口尚未接入；当前是真实本机只读行情加本地沙盒模拟成交。
- GitHub `main` 可能与远端历史不一致，当前应优先推送备份分支，禁止强推。
- 当前工作树还有 `backend/app/services/agent_runtime.py`、`backend/app/services/ops_runtime.py` 和 `backend/app/services/runtime_status.py` 的未提交运行状态快照持久化改动；本轮中文显示提交应避免误包含这些未确认改动，除非后续明确接手该功能。

## 下一步

1. 只 staging/提交 `HANDOFF.md` 或明确接手运行状态快照持久化改动后再一起提交。
2. 推送备份分支 `codex/soak-readiness-quote`，不要强推 `main`。
3. 继续做长运行采样历史：把 `/readiness/soak` 按周期写入 `runtime/soak_readiness_history.jsonl` 并在控制台显示连续无失败采样数。
