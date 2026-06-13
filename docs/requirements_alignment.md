# Alpha 需求对齐

| 需求 | 状态 | 当前实现 |
|---|---:|---|
| Agent 全自动 paper trading | 已实现增强 MVP | FastAPI 应用托管的 `AutoPaperAgentRuntime` 会在控制台启动后立即运行，然后每 300 秒刷新一次；每次周期写入模拟组合绩效历史，并把模拟佣金/滑点计入权益；`PaperTradingLoop.run_forever()` 仍可用于 CLI |
| Broker paper execution adapter | 已实现增强 MVP | `PaperTradingLoop` 通过 `LocalSandboxPaperBrokerAdapter` 执行本地 sandbox paper order，并返回 broker-like paper receipt；本地 adapter 默认使用固定佣金与滑点模型；外部 broker paper API 尚未接入 |
| Agent 自动生成真实交易候选订单 | 已实现增强 MVP | 从可交易策略锦标赛候选中生成 `OrderIntent` |
| Agent 自动完成风险检查 | 已实现增强 MVP | 入队前执行 `pre_trade_risk_check()`，并强制检查名义金额限制 |
| Agent 自动进入审批队列 | 已实现增强 MVP | 使用 `ApprovalQueue.enqueue()` 入队；默认 SQLite 持久化；dashboard/API 支持已人工复核、拒绝、工单已导出状态流 |
| Agent 自动生成 broker-ready order ticket | 已实现增强 MVP | `BrokerReadyOrderTicket` 包含 `expires_at`；控制台/API 标注有效与过期候选单；已复核且仍有效的工单可通过 `/broker-ticket`、中文 `/broker-ticket/view` 和 `.csv` 导出为人工经纪商录入包 |
| 每 5 分钟更新一次 | 已实现增强 MVP | 服务、`configs/agent_loop.yaml`、应用运行时、控制台 JS 刷新和候选单 TTL 均使用 `refresh_interval_seconds: 300` |
| Web dashboard | 已实现增强 MVP | `/dashboard`、`/dashboard/state`、`/agent/loop/status`、`/paper/portfolio`、`/paper/performance/history`、`/strategy/tournament/run`；队列表显示可操作性/时效性/剩余秒数、SQLite 存储状态，并提供中文复核、拒绝、导出操作；策略表显示样本外收益/命中率/验证窗口；模拟绩效面板显示收益率、权益变化、回撤、执行模型和累计佣金；新增 "长运行预检" 面板 |
| Market data gateway | 已实现 MVP | `MarketDataGateway` 默认缓存优先，缺失时回退到样例数据；`/market-data/status` 和 dashboard 显示行情来源、质量、最新日期、最新价格；`/market-data/refresh` 可尝试刷新 Stooq 公共延迟行情缓存 |
| 30 天运行健康与备份 | 已实现增强 MVP | `/ops/health`、`/ops/backup`、`/ops/maintenance/status`、`scripts/check_alpha_ops.sh` 和 dashboard "运行健康" 显示自动循环、SQLite 审批队列、模拟组合、Moomoo OpenD 只读探测、行情质量、进程/日志、最近备份、自动维护状态和真实下单边界；应用托管 ops maintenance 默认每 300 秒采样健康状态、每天自动备份一次并保留最近 30 份 |
| 6月20日模拟交易交付就绪报告 | 已实现 MVP | `/readiness/paper-trading`、dashboard "交付就绪" 和 `python -m backend.app.services.paper_readiness` 逐项验证自动循环、策略迭代、模拟成交、OrderIntent、风控、审批队列、broker-ready 工单、5分钟时效、本地 App 入口和真实下单边界；缺少运行中循环或新鲜工单时明确标记不可交付 |
| 30 天长运行预检 | 已实现 MVP | `/readiness/soak`、dashboard "长运行预检"、`scripts/check_alpha_soak.sh` 和 `python -m backend.app.services.soak_readiness` 聚合 App 入口、模拟交易交付就绪、5分钟循环、有效 broker-ready 工单、运行健康、自动维护、恢复备份和真实下单边界；该报告只证明是否可以开始本地 soak，不等于已经完成 30 天验证 |
| Paper broker visibility | 已实现增强 MVP | `/paper/broker/status` 和 dashboard "模拟交易执行层" 显示 adapter、模式、连接、凭据要求、是否允许真实下单、执行模型、模拟滑点、单笔佣金、累计佣金、最新模拟成交和最近成交成本 |
| Moomoo OpenD 本机集成 | 已实现只读行情 MVP | `/broker/moomoo/status`、`/broker/moomoo/quote-snapshot` 和 dashboard "Moomoo OpenD" 显示 Python API 包、SDK 可导入、OpenD 本机端口、只读就绪、只读行情快照、交易解锁、真实下单禁用和禁止操作；当前不读取交易凭据、不创建交易上下文、不解锁交易、不调用真实下单 |
| 操作及时性和时间有效性 | 已实现增强 MVP | `ApprovalQueue.summary()` 只把未过期的待人工确认候选单计为用户可操作；后端拒绝复核/导出过期工单；过期候选单保留用于审计 |
| 稳定 webpage 交互平台入口 | 已实现增强 MVP | AppleScript `Alpha.app` 已安装到 Downloads、用户 Applications 和系统 `/Applications`；命令入口保留用于兼容 |
| 全中文显示 | 已实现增强 MVP | 控制台标题、按钮、指标、表格、空状态、状态映射、启动/停止脚本提示、CLI 摘要、策略迭代历史、模拟绩效、风险原因、工单导出包、OpenAPI 元信息、HTTP 错误说明、owner 摘要、审批队列时效/存储状态和 Moomoo 下一步提示均提供中文展示；API 机器字段和值保持稳定，owner-facing 字段补 `*_zh` |
| 策略迭代 | 已实现增强 MVP | `run_strategy_tournament()` 使用 walk-forward 样本外收益、命中率、验证窗口和可交易选择对 momentum 候选排序；每次 paper cycle 持久化 `runtime/strategy_tournament_history.jsonl` 并显示策略稳定度 |
| `live_trading.enabled:true` | 已拒绝 | 提交默认值必须保持禁用 |
| 全自动实盘真实下单 | 已拒绝 | 真实资金订单需要用户在 broker 侧确认 |
