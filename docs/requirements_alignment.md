# Alpha 需求对齐

| 需求 | 状态 | 当前实现 |
|---|---:|---|
| Agent 全自动模拟交易 | 已实现增强 MVP | FastAPI 应用托管的 `AutoPaperAgentRuntime` 会在控制台启动后立即运行，然后每 300 秒刷新一次；每次周期写入模拟组合绩效历史，并把模拟佣金/滑点计入权益；`PaperTradingLoop.run_forever()` 仍可用于命令行。 |
| 经纪商模拟执行适配器 | 已实现增强 MVP | `PaperTradingLoop` 通过 `LocalSandboxPaperBrokerAdapter` 执行本地沙盒模拟订单，并返回类经纪商模拟回执；本地适配器默认使用固定佣金与滑点模型；外部经纪商模拟接口尚未接入。 |
| Agent 自动生成真实交易候选订单 | 已实现增强 MVP | 从可交易策略锦标赛候选中生成 `OrderIntent`；候选单只进入人工复核队列，不自动提交真实资金订单。 |
| Agent 自动完成风险检查 | 已实现增强 MVP | 入队前执行 `pre_trade_risk_check()`，并强制检查名义金额限制。 |
| Agent 自动进入审批队列 | 已实现增强 MVP | 使用 `ApprovalQueue.enqueue()` 入队；默认 SQLite 持久化；控制台/API 支持已人工复核、拒绝、工单已导出状态流。 |
| Agent 自动生成经纪商就绪订单工单 | 已实现增强 MVP | `BrokerReadyOrderTicket` 包含 `expires_at`；控制台/API 标注有效与过期候选单；已复核且仍有效的工单可通过 `/broker-ticket`、中文 `/broker-ticket/view` 和 `.csv` 导出为人工经纪商录入包。 |
| 每 5 分钟更新一次 | 已实现增强 MVP | 服务、`configs/agent_loop.yaml`、应用运行时、控制台刷新和候选单有效期均使用 `refresh_interval_seconds: 300`。 |
| 网页控制台 | 已实现增强 MVP | `/dashboard`、`/dashboard/state`、`/agent/loop/status`、`/paper/portfolio`、`/paper/performance/history`、`/strategy/tournament/run`；队列表显示可操作性/时效性/剩余秒数、SQLite 存储状态，并提供中文复核、拒绝、导出操作。 |
| 行情数据网关 | 已实现 MVP | `MarketDataGateway` 默认缓存优先，缺失时回退到样例数据；`/market-data/status` 和控制台显示行情来源、质量、最新日期、最新价格；`/market-data/refresh` 可尝试刷新 Stooq 公共延迟行情缓存或富途牛牛只读行情缓存。 |
| 30 天运行健康与备份 | 已实现增强 MVP | `/ops/health`、`/ops/backup`、`/ops/maintenance/status`、`scripts/check_alpha_ops.sh` 和控制台“运行健康”显示自动循环、SQLite 审批队列、模拟组合、富途牛牛开放网关只读探测、行情质量、进程/日志、最近备份、自动维护状态和真实下单边界；自动循环和自动维护会写入本地心跳文件，供就绪检查跨进程验证；自动维护每轮追加 `runtime/soak_readiness_history.jsonl`，控制台显示连续无失败采样数。 |
| 6月15日模拟交易交付就绪报告 | 已实现 MVP | `/readiness/paper-trading`、控制台“交付就绪”和 `python -m backend.app.services.paper_readiness` 逐项验证自动循环、策略迭代、模拟成交、`OrderIntent`、风控、审批队列、经纪商就绪工单、5分钟时效、本地 App 入口和真实下单边界，并标注 6月17日网页与本地应用入口目标。 |
| 30 天长运行预检 | 已实现增强 MVP | `/readiness/soak`、`/readiness/soak/history`、控制台“长运行预检”、`scripts/check_alpha_soak.sh` 和 `python -m backend.app.services.soak_readiness` 聚合 App 入口、模拟交易交付就绪、5分钟循环、有效经纪商就绪工单、运行健康、自动维护、恢复备份和真实下单边界；历史摘要显示采样总数、连续无失败采样数、连续完全通过采样数、最近失败时间和最近采样记录；该报告只证明是否可以开始本地长运行，不等于已经完成 30 天验证。 |
| 模拟执行层可见性 | 已实现增强 MVP | `/paper/broker/status` 和控制台“模拟交易执行层”显示适配器、模式、连接、凭据要求、是否允许真实下单、执行模型、模拟滑点、单笔佣金、累计佣金、最新模拟成交和最近成交成本。 |
| 富途牛牛开放网关本机集成 | 已实现只读行情 MVP | `/broker/moomoo/status`、`/broker/moomoo/quote-snapshot` 和控制台“富途牛牛开放网关（只读）”显示 Python 接口包、软件开发包可导入、开放网关本机端口、只读就绪、只读行情快照、交易解锁、真实下单禁用和禁止操作；当前不读取交易凭据、不创建交易上下文、不解锁交易、不调用真实下单。 |
| 操作及时性和时间有效性 | 已实现增强 MVP | `ApprovalQueue.summary()` 只把未过期的待人工确认候选单计为用户可操作；后端拒绝复核/导出过期工单；过期候选单保留用于审计。 |
| 稳定网页交互平台入口 | 已实现增强 MVP | AppleScript `Alpha.app` 已安装到 Downloads、用户 Applications 和系统 `/Applications`；命令入口保留用于兼容；`scripts/verify_dashboard_http_smoke.py --exercise-actions` 会通过 HTTP 检查 `/health`、`/dashboard` 和 `/dashboard/state` 的中文文案、关键状态、响应式布局契约和真实下单禁用边界，并安全调用模拟交易周期与运行备份端点。 |
| 全中文显示 | 已实现增强 MVP | 控制台标题、按钮、指标、表格、空状态、状态映射、启动/停止脚本提示、命令行摘要、策略迭代历史、策略锦标赛候选、模拟经纪商状态/回执、模拟绩效、风险原因、中文工单导出表、FastAPI 元信息、HTTP 错误说明、所有者摘要、审批队列时效/存储状态和富途牛牛下一步提示均提供中文展示；API 机器字段和值保持稳定，所有者可见字段补 `*_zh`；`scripts/verify_chinese_display.py` 和 `scripts/verify_dashboard_http_smoke.py` 作为中文显示审计门槛。 |
| 策略迭代 | 已实现增强 MVP | `run_strategy_tournament()` 使用 walk-forward 样本外收益、命中率、验证窗口和可交易选择对 momentum 候选排序；每次模拟交易周期持久化 `runtime/strategy_tournament_history.jsonl` 并显示策略稳定度。 |
| `live_trading.enabled:true` | 已拒绝 | 提交默认值必须保持禁用。 |
| 全自动实盘真实下单 | 已拒绝 | 真实资金订单需要用户在经纪商侧确认。 |
