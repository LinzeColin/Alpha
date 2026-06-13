# Alpha 需求对齐

| 需求 | 状态 | 当前实现 |
|---|---:|---|
| Agent 全自动 paper trading | 已实现增强 MVP | FastAPI 应用托管的 `AutoPaperAgentRuntime` 会在控制台启动后立即运行，然后每 300 秒刷新一次；`PaperTradingLoop.run_forever()` 仍可用于 CLI |
| Broker paper execution adapter | 已实现 MVP | `PaperTradingLoop` 通过 `LocalSandboxPaperBrokerAdapter` 执行本地 sandbox paper order，并返回 broker-like paper receipt；外部 broker paper API 尚未接入 |
| Agent 自动生成真实交易候选订单 | 已实现增强 MVP | 从可交易策略锦标赛候选中生成 `OrderIntent` |
| Agent 自动完成风险检查 | 已实现增强 MVP | 入队前执行 `pre_trade_risk_check()`，并强制检查名义金额限制 |
| Agent 自动进入审批队列 | 已实现增强 MVP | 使用 `ApprovalQueue.enqueue()` 入队；dashboard/API 支持已人工复核、拒绝、工单已导出状态流 |
| Agent 自动生成 broker-ready order ticket | 已实现增强 MVP | `BrokerReadyOrderTicket` 包含 `expires_at`；控制台/API 标注有效与过期候选单 |
| 每 5 分钟更新一次 | 已实现增强 MVP | 服务、`configs/agent_loop.yaml`、应用运行时、控制台 JS 刷新和候选单 TTL 均使用 `refresh_interval_seconds: 300` |
| Web dashboard | 已实现增强 MVP | `/dashboard`、`/dashboard/state`、`/agent/loop/status`、`/paper/portfolio`、`/strategy/tournament/run`；队列表显示可操作性/时效性/剩余秒数，并提供中文复核、拒绝、导出操作；策略表显示样本外收益/命中率/验证窗口 |
| Paper broker visibility | 已实现 MVP | `/paper/broker/status` 和 dashboard "模拟交易执行层" 显示 adapter、模式、连接、凭据要求、是否允许真实下单、最新模拟成交 |
| 操作及时性和时间有效性 | 已实现增强 MVP | `ApprovalQueue.summary()` 只把未过期的待人工确认候选单计为用户可操作；过期候选单保留用于审计 |
| 稳定 webpage 交互平台入口 | 已实现增强 MVP | AppleScript `Alpha.app` 已安装到 Downloads、用户 Applications 和系统 `/Applications`；命令入口保留用于兼容 |
| 全中文显示 | 已实现 MVP | 控制台标题、按钮、指标、表格、空状态、状态映射和启动/停止脚本提示均显示中文；API 机器字段和值保持稳定 |
| 策略迭代 | 已实现增强 MVP | `run_strategy_tournament()` 使用 walk-forward 样本外收益、命中率、验证窗口和可交易选择对 momentum 候选排序 |
| `live_trading.enabled:true` | 已拒绝 | 提交默认值必须保持禁用 |
| 全自动实盘真实下单 | 已拒绝 | 真实资金订单需要用户在 broker 侧确认 |
