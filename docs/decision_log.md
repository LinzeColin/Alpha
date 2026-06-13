# Alpha 决策日志

## 2026-06-13：GitHub 是权威连续性来源

- 决策：使用 `https://github.com/LinzeColin/Alpha` 作为 Alpha 的权威备份与连续开发来源。
- 原因：后续任何 agent 接手时，需要稳定、可检查的代码、规则、文档、测试证据和交接状态。
- 影响：每次有意义的 run 必须提交并推送，除非网络、认证或用户明确指示阻止。

## 2026-06-13：真实资金执行边界

- 决策：Alpha 可以自动运行研究、模拟交易、风险检查、审批队列和经纪商就绪订单工单，但不得自主提交真实资金经纪商订单。
- 原因：交易系统必须把真实资金执行控制权留给所有者。
- 影响：已提交默认配置保持 `live_trading.enabled: false`；真实交易候选只以 `OrderIntent -> 风控 -> 审批队列 -> BrokerReadyOrderTicket` 形式进入人工确认流程。

## 2026-06-13：5 分钟候选单刷新

- 决策：订单候选循环默认刷新间隔为 300 秒。
- 原因：用户要求候选单及时更新，同时必须保留风控与复核门槛。
- 影响：FastAPI 控制台生命周期启动应用托管自动模拟交易循环，启动后立即运行一次，然后按配置间隔休眠。

## 2026-06-13：候选单时效决定可操作性

- 决策：只有未过期的 `pending_owner_approval` 工单才算所有者可操作候选。
- 原因：经纪商就绪工单会过期；过期候选可以审计，但不应被当成可执行。
- 影响：审批队列区分有效待确认、过期待确认、风控阻止和总数；控制台显示可操作性、时效性和剩余秒数。

## 2026-06-13：本地 App 入口

- 决策：Alpha 交付 macOS `.app` 入口，背后复用同一控制台启动脚本。
- 原因：用户需要稳定的本地网页工作台入口，而不是每次手动敲终端命令。
- 影响：`outputs/applications/Alpha.applescript` 生成 `Alpha.app`，并安装到 Downloads、用户 Applications 和系统 `/Applications`。

## 2026-06-13：策略迭代必须有样本外证据

- 决策：策略锦标赛候选必须提供 walk-forward 样本外收益、命中率和验证窗口数。
- 原因：单窗口动量排序不足以支撑策略晋级。
- 影响：`run_strategy_tournament()` 返回验证摘要，控制台显示样本外收益、命中率、验证窗口和策略稳定度。

## 2026-06-13：模拟执行层与成本模型

- 决策：模拟交易必须通过可替换的本地沙盒经纪商适配器，并默认记录固定佣金与滑点模型。
- 原因：成熟模拟交易不能用零成本成交高估策略表现。
- 影响：`LocalSandboxPaperBrokerAdapter` 记录参考价、模拟成交价、5.00 基点滑点、每笔 1.00 AUD 模拟佣金、累计成本和中文执行模型。

## 2026-06-13：模拟交易循环必须感知现金、持仓和目标敞口

- 决策：`PaperTradingLoop` 正常优先生成策略胜出标的的买入候选；但在买入前必须先检查 `max_position_weight_pct` 和 `max_total_gross_exposure_pct`，若持仓或总敞口超限则生成“目标仓位再平衡”卖出候选；若现金不足且仍有可卖持仓，则生成现金回收减仓候选。
- 原因：长期 5 分钟循环如果只买入，会把本地模拟现金耗尽并持续产生被拒绝模拟订单；如果只做现金回收，又会在下一轮重新买回，形成不成熟的振荡。
- 影响：再平衡/减仓卖单仍走 `OrderIntent -> 风控 -> 审批队列 -> BrokerReadyOrderTicket -> 本地模拟成交`，不会触发真实资金订单；用户可见策略名会显示“目标仓位再平衡”或“现金回收减仓”。

## 2026-06-13：纸面经纪商 provider 必须 fail-closed

- 决策：纸面交易经纪商通过 `configs/paper_broker.yaml` 选择，默认只能使用本地沙盒；外部 paper API provider 在真实实现、凭据隔离、纸面模式证明和回归测试完成前必须返回未就绪状态。
- 原因：外部经纪商 paper API 是后续成熟 paper trading 的必要入口，但不能因为误配或半成品代码绕过真实下单边界。
- 影响：`build_paper_broker_adapter()` 支持默认本地沙盒和外部 paper API fail-closed 壳；控制台显示纸面交易提供方、适配器就绪、允许纸面下单、外部纸面 API、未就绪原因和下一步。

## 2026-06-13：模拟交易成熟度验收使用临时运行态

- 决策：新增 `scripts/verify_paper_trading_maturity.py`，用临时 SQLite 队列、临时组合状态和临时历史文件连续跑模拟交易周期，并额外验证目标仓位再平衡与现金不足减仓；现金回收分支使用临时策略覆写隔离验证，不修改默认提交配置。
- 原因：6月15日交付需要证明模拟交易链路能连续运行，而不是只通过单一 API smoke；临时运行态可以避免污染真实 runtime。
- 影响：成熟度验收报告覆盖连续周期、风控、审批队列、经纪商就绪工单、5分钟 TTL、模拟成交和真实下单禁用边界；默认输出到 `outputs/paper_maturity/paper_trading_maturity_latest.json`。

## 2026-06-13：Alpaca Paper 适配器只允许 paper host

- 决策：`alpaca_paper` 只允许 `https://paper-api.alpaca.markets`，凭据只从 `ALPACA_PAPER_KEY_ID` 与 `ALPACA_PAPER_SECRET_KEY` 读取，默认配置仍关闭。
- 原因：Alpaca 官方 paper 文档说明 paper 账户使用不同 key 和 paper base URL；订单 API 与 live 规格一致，因此必须靠 host allowlist 和显式配置阻断 live endpoint。
- 影响：`AlpacaPaperBrokerAdapter` 支持 mock 验证的 `POST /v2/orders` paper 下单回执；未配置凭据、base URL 非 paper host、未显式启用时均 fail-closed，不会暴露 secret。

## 2026-06-13：Alpaca Paper 只读同步与纸面下单分开开关

- 决策：`alpaca_paper` 的账户、持仓和最近订单同步必须由 `read_only_sync_enabled` 单独开启；纸面订单提交仍必须由 `order_submission_enabled` 单独开启。
- 原因：只读同步和纸面订单提交的风险不同，分开开关可以先验证账户可见性、中文控制台展示和凭据脱敏，再进入纸面订单 E2E。
- 影响：新增 `/paper/broker/external-snapshot` 和控制台“外部账户同步”展示；账户原始 ID 与 account number 不进入返回快照，真实下单仍固定禁用。

## 2026-06-13：Moomoo 本机安装只开放只读行情路径

- 决策：即使本机已安装 Moomoo、Moomoo OpenD 和 `moomoo-api`，Alpha 当前也只把它作为只读行情和网关就绪来源，不把 `moomoo_paper` 自动升级为可下单 provider。
- 原因：Moomoo 官方 paper 示例仍需要创建交易上下文并调用 `place_order(..., trd_env=TrdEnv.SIMULATE)`；这与项目当前“禁止提交可直接触发真实 broker place_order 路径”的安全扫描门槛冲突，必须作为单独受控适配器重新设计。
- 影响：本机只读验收结果写入 `outputs/moomoo_opend_readiness_20260613.json`；`moomoo_paper` 继续 fail-closed，`live_order_submission_enabled=false`、`trade_context_enabled=false`。

## 2026-06-13：审批队列可交互但不执行真实下单

- 决策：控制台可以把工单标记为已人工复核、已拒绝或工单已导出，但这些动作只更新本地状态。
- 原因：用户需要可用的复核工作流；真实资金执行仍必须在经纪商侧由所有者确认。
- 影响：复核和导出动作记录审计元数据；导出包总是写入 `live_order_submission_enabled: false`。

## 2026-06-13：审批队列默认 SQLite 持久化

- 决策：运行时审批队列默认写入 `runtime/approval_queue.sqlite3`。
- 原因：5 分钟自动循环会持续生成候选，队列必须能跨重启保留。
- 影响：JSON 路径仅作为兼容；控制台和 API 暴露存储后端、持久化状态和路径。

## 2026-06-13：行情数据网关可观察且失败软回退

- 决策：模拟交易和控制台通过 `MarketDataGateway` 解析价格路径。
- 原因：系统需要从样例数据逐步过渡到公共延迟行情和本机只读行情，同时外部失败不能阻塞本地模拟交易。
- 影响：行情状态显示提供方、来源、质量、最新日期、缓存年龄和刷新状态；外部刷新失败时回退到旧缓存或样例数据，不启用真实下单。

## 2026-06-13：运行健康与自动维护

- 决策：Alpha 必须暴露本地运行健康检查、运行备份和应用托管维护循环。
- 原因：30 天本地长运行需要连续证据、日志、备份和可恢复性。
- 影响：`/ops/health`、`/ops/backup`、`/ops/maintenance/status`、`scripts/check_alpha_ops.sh` 和控制台“运行健康”显示循环、队列、组合、行情、进程、日志、备份和安全边界。

## 2026-06-13：中文显示是产品验收项

- 决策：Alpha 的用户可见运行界面、App/脚本输出、控制台状态、风险原因、策略校验错误、富途牛牛提示和人工操作文案必须默认中文显示。
- 原因：用户要求“整个系统彻底的全中文显示”，运行期间不应让所有者通过 raw enum 或英文技术词才能理解系统状态。
- 影响：控制台、命令行摘要、工单 HTML、中文 CSV 表、FastAPI 元信息、HTTP 错误说明、所有者摘要、审批状态、行情刷新错误、策略候选、模拟经纪商状态/回执和富途牛牛下一步提示均提供中文展示；API 字段名、内部枚举、工单号、路径和股票代码保持机器稳定；`scripts/verify_chinese_display.py` 和 `scripts/verify_dashboard_http_smoke.py` 作为回归门槛。

## 2026-06-13：经纪商就绪工单默认中文视图

- 决策：控制台“查看工单”默认打开中文 HTML 工单视图，下载表格默认使用中文表头和中文值。
- 原因：点击工单后直接看到原始 JSON 或英文 CSV 不符合全中文操作体验。
- 影响：`/broker-ticket/view` 渲染中文详情；`.csv` 返回中文人工录入表；原始 JSON 端点保留给自动化和审计。

## 2026-06-13：控制台响应式布局契约

- 决策：Alpha 控制台必须保留移动端断点、按钮换行、表格局部横向滚动、断词和稳定最小宽度等布局保护。
- 原因：6月17日目标是可日常使用的网页/App 入口，不只是 HTTP 可访问；长运行历史、审批队列和行情表在窄屏上不能把页面整体撑坏。
- 影响：`scripts/verify_dashboard_http_smoke.py` 会检查这些布局规则是否仍存在；截图级视觉验收可在安装 Playwright/Chromium 或 Browser/Chrome 工具可用后补强。

## 2026-06-13：截图级中文显示验收

- 决策：全中文显示不能只依赖静态 HTML 字符串检查，必须验证脚本执行后的桌面和移动端可见文本。
- 原因：控制台大部分状态由 `/dashboard/state` 动态渲染，静态检查无法发现运行后英文状态、旧表头或布局空白。
- 影响：`scripts/verify_dashboard_chrome_visual.py` 使用本机 Chrome headless 截图和 DOM dump，检查截图尺寸、像素多样性、渲染后中文文案、旧英文 UI 禁用项和响应式布局契约；`.html/.png` 因可能包含本机路径默认忽略，只提交 JSON 报告。

## 2026-06-13：富途牛牛开放网关只读阶段

- 决策：富途牛牛开放网关第一阶段只做本机只读探测与只读行情快照，不创建交易上下文、不解锁交易、不提交真实订单。
- 原因：用户本机已有相关环境，Alpha 需要把行情路径纳入可观测性，但不能越过人工经纪商确认边界。
- 影响：`/broker/moomoo/status` 和 `/broker/moomoo/quote-snapshot` 返回中文状态、接口包可用性、开放网关连接、只读就绪、禁止操作和 `live_order_submission_enabled=false`。

## 2026-06-13：模拟交易交付与长运行预检分离

- 决策：`/readiness/paper-trading` 是模拟交易交付门槛，`/readiness/soak` 是 30 天本地长运行开始门槛。
- 原因：运行健康不等于需求交付，就绪检查也不等于已经完成 30 天验证。
- 影响：控制台“交付就绪”和“长运行预检”分别显示检查项、通过/关注/失败数和安全边界。

## 2026-06-13：自动运行心跳是就绪证据

- 决策：自动模拟交易循环和自动维护循环必须把运行心跳持久化到本地 `runtime/agent_loop_status.json` 与 `runtime/ops_maintenance_status.json`。
- 原因：网页/App 长运行不能只依赖当前进程内存快照；命令行预检和后续 agent 接手时需要可读取、可审计的新鲜运行证据。
- 影响：就绪检查会校验心跳类型、写入时间、进程号和进程存活状态；心跳缺失、过期或进程已退出时 fail closed，不会把系统误判为正在稳定运行。

## 2026-06-13：长运行预检必须形成采样历史

- 决策：自动维护循环每轮把长运行预检结果追加到 `runtime/soak_readiness_history.jsonl`，控制台和 `/readiness/soak/history` 读取摘要。
- 原因：30 天 E-Safe 不能只看当前一次预检，必须有连续采样证据、连续无失败计数和最近失败时间。
- 影响：控制台“长运行预检”显示历史采样数、连续无失败采样数、连续完全通过采样数、最近失败和最近采样表；该历史证明观察进度，不等于 30 天已经完成。
