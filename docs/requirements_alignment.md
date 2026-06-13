# Alpha Requirements Alignment

| Requirement | Status | Implementation Direction |
|---|---:|---|
| Agent 全自动 paper trading | Improved MVP implemented | FastAPI app-managed `AutoPaperAgentRuntime` runs immediately on dashboard startup, then every 300 seconds; `PaperTradingLoop.run_forever()` remains available for CLI |
| Agent 自动生成真实交易候选订单 | Improved MVP implemented | `OrderIntent` generated from tradable strategy tournament candidate |
| Agent 自动完成风险检查 | Improved MVP implemented | `pre_trade_risk_check()` before queue entry, with notional limit enforcement |
| Agent 自动进入审批队列 | MVP implemented | `ApprovalQueue.enqueue()` |
| Agent 自动生成 broker-ready order ticket | MVP implemented | `BrokerReadyOrderTicket` |
| 每 5 分钟更新一次 | Improved MVP implemented | `refresh_interval_seconds: 300` in service, `configs/agent_loop.yaml`, app runtime, and dashboard JS refresh |
| Web dashboard | Improved MVP implemented | `/dashboard`, `/dashboard/state`, `/agent/loop/status`, `/paper/portfolio`, `/strategy/tournament/run` |
| 稳定 webpage 交互平台入口 | Improved MVP implemented | `scripts/start_alpha_dashboard.sh` starts dashboard; app lifecycle starts the paper agent runtime; `outputs/applications/Alpha.command` and `outputs/applicatioins/Alpha.command` launch it |
| 策略迭代 | Improved MVP implemented | `run_strategy_tournament()` ranks momentum candidates and selects tradable paper candidate |
| `live_trading.enabled:true` | Rejected | Committed defaults must remain disabled |
| 全自动实盘真实下单 | Rejected | Real-money orders require owner-side broker confirmation |
