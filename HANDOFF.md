# Alpha 交接说明

时间：2026-06-13，Australia/Sydney

## 当前目标

把 Alpha 打造成 GitHub 备份的本地优先个人量化智能体工作台：自动模拟交易、策略迭代、风险检查、审批队列、经纪商就绪订单工单、运行健康、长运行预检和中文控制台。

## 当前状态

- 权威仓库：`https://github.com/LinzeColin/Alpha`。
- 本地默认真实下单仍禁用，`live_trading.enabled` 不得提交为启用。
- 控制台入口：`/dashboard`；状态接口：`/dashboard/state`。
- 控制台显示、脚本输出、策略校验错误、工单 HTML、工单 CSV 表头、富途牛牛开放网关状态、外部纸面账户同步、行情刷新错误、就绪预检工单文案和主要文档已按中文显示规则更新。
- API 机器字段、路径、枚举、工单号、股票代码和 `provider_id=moomoo_opend` 保持稳定；用户可见展示优先使用中文字段或中文标签。
- 模拟经纪商状态/回执、策略锦标赛候选、审批队列时效、风险原因和页面时间显示已补中文展示兜底，前端未知枚举不直接露出英文状态值。
- 新增 `scripts/verify_chinese_display.py`，作为无额外浏览器依赖的中文显示审计门槛。
- 新增 `scripts/verify_dashboard_http_smoke.py`，通过本地 HTTP 检查 `/health`、`/dashboard` 和 `/dashboard/state` 的中文文案、关键中文字段、响应式布局契约和真实下单禁用边界。
- 新增 `scripts/verify_dashboard_chrome_visual.py`，通过本机 Chrome headless 检查桌面/移动截图、渲染后可见中文文案、旧英文 UI 禁用项、像素多样性和响应式布局契约；JSON 报告可提交，截图/HTML 因包含本机路径只保留本地。
- `.gitignore` 精确忽略视觉验收 `.html/.png`，避免把本机绝对路径和运行态截图推送到 GitHub；`outputs/visual_acceptance/dashboard_chrome_visual_report.json` 保留为提交证据。
- 新增 `backend/app/services/app_entry.py` 和 `scripts/verify_app_entry.py`，验证仓库、Downloads、用户 Applications、系统 Applications 四处 `Alpha.app` 的应用包结构、Info.plist、可执行 applet、关键文件指纹一致性，以及 AppleScript/命令入口是否指向当前仓库控制台启动脚本；证据写入 `outputs/app_entry/app_entry_readiness_latest.json`。
- 新增 `/readiness/app-entry` 和控制台“本地应用入口”面板，显示应用入口总体状态、检查项、四处 `Alpha.app` 路径、plist、可执行状态和指纹一致性。
- 行情状态提供 `provider_zh`、`source_kind_zh`、`data_quality_zh`、`real_market_data_zh`、`refresh_error_zh` 等中文展示字段；控制台刷新失败优先显示中文错误兜底。
- 经纪商工单 JSON 仍保留机器字段；默认 HTML 视图和 CSV 下载面向人工操作改为中文。
- 富途牛牛开放网关仍只允许只读探测和只读行情快照；不得创建交易上下文、不得解锁交易、不得调用真实下单。
- 2026-06-13 本机只读验收已确认：`moomoo-api 10.7.6708` 可导入，提权只读探测确认 OpenD `127.0.0.1:11111` 已连通，并通过 `OpenQuoteContext` 获取 `US.SPY`、`US.QQQ`、`US.TLT` 共 3 行行情快照；证据见 `outputs/moomoo_opend_readiness_20260613.json`。
- 新增 `configs/paper_broker.yaml` 和 `build_paper_broker_adapter()`；默认 `local_sandbox` 继续本地模拟成交；`alpaca_paper` 已实现 paper host allowlist、环境变量凭据门槛和 mock 下单回执但默认关闭；`ibkr_paper`、`moomoo_paper`、`external_paper_api` 目前只返回中文未就绪状态并 fail-closed。
- Alpaca paper 适配依据见 `docs/paper_broker_provider_notes.md`；当前已实现默认关闭的账户/持仓/最近订单只读同步和纸面订单 mock 下单路径，尚未完成用户真实 Alpaca paper account E2E。
- Moomoo paper 下单未实现；官方 paper 示例仍需要创建交易上下文并调用 `place_order(..., trd_env=TrdEnv.SIMULATE)`，与当前安全扫描门槛冲突，必须另开受控适配 run 后再做。
- 控制台“模拟交易执行层”已显示纸面交易提供方、适配器就绪、允许纸面下单、外部纸面 API、未就绪原因和下一步。
- `PaperTradingLoop` 已具备现金/持仓/目标敞口约束感知：正常优先生成买入候选；若单标的仓位或总敞口超过 policy 上限，则优先生成“目标仓位再平衡”卖出候选；若现金不足以覆盖预计买入成交价、滑点和佣金但组合仍有可卖持仓，则生成现金回收减仓候选；两类卖单都会继续通过风控、审批队列、经纪商就绪工单和本地模拟成交。
- 新增 `backend/app/services/paper_maturity.py` 和 `scripts/verify_paper_trading_maturity.py`：用临时本地状态验收连续模拟周期、目标仓位再平衡卖单、现金回收减仓、风控、审批队列、经纪商就绪工单、5分钟 TTL 和真实下单禁用边界，并写入 `outputs/paper_maturity/paper_trading_maturity_latest.json`。
- `scripts/start_alpha_dashboard.sh` 和 `scripts/stop_alpha_dashboard.sh` 修复了变量紧贴中文标点时的 zsh 解析问题。
- 自动模拟交易循环和自动维护循环会分别写入 `runtime/agent_loop_status.json` 与 `runtime/ops_maintenance_status.json`；`/readiness/paper-trading` 和 `/readiness/soak` 可以读取新鲜心跳并校验进程仍存活，避免把已退出的 App 误判为就绪；`/readiness/paper-trading` 还会验证 `next_run_at - last_run_completed_at` 与 300 秒刷新契约一致。
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
- `backend/app/services/broker_paper_adapter.py`
- `backend/app/services/strategy_iteration.py`
- `backend/app/schemas/strategy_dsl.py`
- `configs/paper_broker.yaml`
- `scripts/start_alpha_dashboard.sh`
- `scripts/stop_alpha_dashboard.sh`
- `scripts/verify_chinese_display.py`
- `scripts/verify_dashboard_http_smoke.py`
- `scripts/verify_dashboard_chrome_visual.py`
- `scripts/verify_app_entry.py`
- `backend/app/services/app_entry.py`
- `outputs/app_entry/app_entry_readiness_latest.json`
- `outputs/visual_acceptance/dashboard_chrome_visual_report.json`
- `tests/test_dashboard_state.py`
- `tests/test_dashboard_chrome_visual.py`
- `tests/test_broker_ticket_export.py`
- `tests/test_broker_paper_adapter.py`
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
- `docs/paper_broker_provider_notes.md`
- `docs/requirements_alignment.md`
- `HANDOFF.md`
- `outputs/moomoo_opend_readiness_20260613.json`

## 验证结果

已通过：

```bash
.venv/bin/python -m pytest tests/test_dashboard_chrome_visual.py tests/test_dashboard_http_smoke.py tests/test_dashboard_state.py -q
# 18 passed

.venv/bin/python -m pytest tests/test_broker_paper_adapter.py tests/test_paper_trading_loop.py tests/test_dashboard_http_smoke.py tests/test_dashboard_state.py -q
# 30 passed

.venv/bin/python -m pytest tests/test_broker_paper_adapter.py -q
# 11 passed

.venv/bin/python -m pytest tests -q
# 90 passed

.venv/bin/python scripts/verify_chinese_display.py
# status_zh=通过, error_count=0, checked_state_key_count=21, checked_static_text_count=26

python /Users/linzezhang/.codex/skills/webapp-testing/scripts/with_server.py --server ".venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8140" --port 8140 --timeout 60 -- .venv/bin/python scripts/verify_dashboard_http_smoke.py --base-url http://127.0.0.1:8140 --timeout 15 --exercise-actions
# status_zh=通过, error_count=0, checked_dashboard_text_count=13, checked_state_field_count=15, checked_layout_contract_count=10, exercised_action_count=2

python /Users/linzezhang/.codex/skills/webapp-testing/scripts/with_server.py --server ".venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8132" --port 8132 --timeout 60 -- .venv/bin/python scripts/verify_dashboard_chrome_visual.py --base-url http://127.0.0.1:8132 --output-dir outputs/visual_acceptance --timeout 15 --virtual-time-budget-ms 4000
# status_zh=通过, error_count=0, checked_viewport_count=2, desktop=1440x1000, mobile=390x844, visible_text_character_count=9762；macOS Chrome headless 已产出截图/DOM 后不自动退出，脚本已主动回收并记录 chrome_timeout_recovered=true

python /Users/linzezhang/.codex/skills/webapp-testing/scripts/with_server.py --server ".venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8142" --port 8142 --timeout 60 -- .venv/bin/python scripts/verify_dashboard_chrome_visual.py --base-url http://127.0.0.1:8142 --output-dir /private/tmp/alpha_visual_check_20260613b --timeout 30 --virtual-time-budget-ms 4000
# 临时复跑：desktop 视口通过并生成截图/DOM，mobile 截图在本机 Chrome headless/GPU 进程超时；未覆盖已提交的 outputs/visual_acceptance/dashboard_chrome_visual_report.json 通过证据。

python scripts/verify_app_entry.py
# status_zh=通过，仓库、Downloads、用户 Applications、系统 Applications 的 Alpha.app 应用包完整，安装副本关键文件指纹与仓库 Alpha.app 一致，AppleScript/命令入口指向当前仓库 scripts/start_alpha_dashboard.sh；证据见 outputs/app_entry/app_entry_readiness_latest.json

git diff --check
# passed

rg -n "place_order|unlock_trade|submit_real|Open.*TradeContext|live_order_submission_enabled\s*[:=]\s*true|trade_context_enabled\s*[:=]\s*true|live_trading.enabled|live_trading:\s*\{\s*enabled:\s*true" backend configs tests AGENTS.md README.md docs scripts
# 当前代码、配置、README 和主文档没有真实下单启用路径；命中项是禁用断言、false 字段、项目规则，以及历史 seed/task pack 文档中的非执行示例。

rg -n "place_order|unlock_trade|submit_real|Open.*TradeContext|live_order_submission_enabled\s*[:=]\s*true|trade_context_enabled\s*[:=]\s*true|live_trading.enabled|live_trading:\s*\{\s*enabled:\s*true|api\.alpaca\.markets/v2/orders|https://api\.alpaca\.markets" backend configs tests AGENTS.md README.md docs scripts
# Alpaca live host 只出现在测试中用于验证会被拒绝；实际适配器只允许 https://paper-api.alpaca.markets。

MOOMOO_API_HOME=runtime/moomoo_api_home .venv/bin/python -c "import json; from backend.app.services.moomoo_broker_probe import probe_moomoo_opend; print(json.dumps(probe_moomoo_opend(), ensure_ascii=False, sort_keys=True, indent=2))"
# 提权只读探测：status_zh=只读探测就绪，package.version=10.7.6708，opend_connected=true，live_order_submission_enabled=false

MOOMOO_API_HOME=runtime/moomoo_api_home .venv/bin/python -c "import json; from backend.app.services.moomoo_broker_probe import probe_moomoo_quote_snapshot; print(json.dumps(probe_moomoo_quote_snapshot(), ensure_ascii=False, sort_keys=True, indent=2))"
# 提权只读行情：status_zh=已获取，row_count=3，symbols=US.SPY/US.QQQ/US.TLT，trade_context_enabled=false，live_order_submission_enabled=false
```

安全扫描结果：没有发现当前可执行真实下单启用路径；命中项包含禁用说明、测试断言、`live_order_submission_enabled=false` 字段、历史 seed/task pack 文档中的非执行示例，以及用于拒绝 live Alpaca host 的测试样例。

短周期运行验证：`ALPHA_MARKET_DATA_PROVIDER=moomoo_opend` 下启动 `AutoPaperAgentRuntime` 与 `AutoOpsMaintenanceRuntime` 各完成 1 轮；`runtime/soak_readiness_history.jsonl` 写入 1 条采样，`consecutive_no_fail_count=1`、`latest_fail_count=0`、`completion_status_zh=观察运行中`、`live_order_submission_enabled=false`。该验证只使用本机富途牛牛开放网关只读行情/本地模拟交易，不创建交易上下文、不解锁交易、不提交真实订单。

现金回收验证：当前运行态组合曾出现 `cash=7.94`、`TLT=111` 的现金不足状态；新逻辑运行一次后生成 `TLT / 卖出 / 数量 1.0` 候选，风控通过、审批队列入队、模拟成交完成，现金回升到 `92.67`，`live_order_submission_enabled=false`。

目标敞口再平衡验证：在运行态 `TLT` 严重超配时，`python -m backend.app.services.paper_trading_loop --once` 生成 `TLT / 卖出 / 数量 1.165909`，策略显示“目标仓位再平衡 TLT”，风控通过、审批队列入队、模拟成交完成，现金回升到 `104.81`，`live_order_submission_enabled=false`。

模拟交易成熟度验收：`python scripts/verify_paper_trading_maturity.py --cycles 3` 通过，报告覆盖连续正常周期、目标仓位再平衡卖单、现金回收减仓、风控、审批队列、经纪商就绪工单、5分钟 TTL 和真实下单禁用边界；现金回收分支使用临时策略覆写隔离验证，不修改默认提交配置；安全边界文案明确“不触发真实下单、不提交真实资金订单”。

运行态 5 分钟调度验收：`open -g /Users/linzezhang/Downloads/Alpha.app` 启动后，`/agent/loop/status` 显示 `interval_seconds=300`、`last_run_completed_at=2026-06-13T09:16:20+00:00`、`next_run_at=2026-06-13T09:21:20+00:00`；`/readiness/paper-trading` 返回 `overall_status=healthy`、`pass_count=10`、`scheduled_delay_seconds=300`、有效候选单 `ticket_469b80ceb4e1`，真实下单边界仍为 false。

运行态检查：普通沙箱内绑定 `127.0.0.1` 会触发权限限制；提权后本地 uvicorn HTTP smoke 已验证 `/dashboard`、`/health` 和 `/dashboard/state` 的中文文案、关键中文字段、10 条响应式布局契约和真实下单禁用边界，并安全调用 `/paper/run-once` 与 `/ops/backup`。本机 Chrome headless 已完成截图级视觉验收；由于 DOM HTML 和截图包含本机绝对路径，默认不提交 `.html/.png`，只提交 `outputs/visual_acceptance/dashboard_chrome_visual_report.json`。

## 未解决风险

- 30 天长运行尚未完成，只能声明具备开始预检/观察运行条件。
- Alpaca paper adapter 已有只读同步 mock 测试和 mock 下单测试，但尚未在用户真实 Alpaca paper account 上做 E2E；Moomoo 已完成本机只读行情验收，但 paper 下单适配尚未实现；默认仍是真实本机只读行情加本地沙盒模拟成交。
- GitHub `main` 可能与远端历史不一致，当前应优先推送备份分支，禁止强推。
- 30 天长运行仍需要真实时间跨度的历史采样；当前心跳只证明 App/循环在当前进程下新鲜运行。

## 下一步

1. 提交并推送长运行采样历史改动到 GitHub 备份分支，建议 `codex/alpha-soak-history-20260613`，不要强推 `main`。
2. 继续补外部 broker paper API 的真实 provider 实现前置条件：官方 paper API 文档、凭据隔离方案、纸面模式证明、只允许 paper endpoint 的回归测试。
3. 继续积累真实 30 天长运行采样；每个异常必须进入运行健康/备份/恢复证据链。
