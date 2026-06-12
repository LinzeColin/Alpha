# Alpha Requirements Alignment

| Requirement | Status | Implementation Direction |
|---|---:|---|
| Agent 全自动 paper trading | Improved MVP implemented | `PaperTradingLoop.run_once()` / `run_forever()` with persistent `PaperBroker` state |
| Agent 自动生成真实交易候选订单 | Improved MVP implemented | `OrderIntent` generated from tradable strategy tournament candidate |
| Agent 自动完成风险检查 | Improved MVP implemented | `pre_trade_risk_check()` before queue entry, with notional limit enforcement |
| Agent 自动进入审批队列 | MVP implemented | `ApprovalQueue.enqueue()` |
| Agent 自动生成 broker-ready order ticket | MVP implemented | `BrokerReadyOrderTicket` |
| 每 5 分钟更新一次 | MVP implemented | `refresh_interval_seconds: 300` in service and `configs/agent_loop.yaml` |
| Web dashboard | Improved MVP implemented | `/dashboard`, `/dashboard/state`, `/paper/portfolio`, `/strategy/tournament/run` |
| 策略迭代 | Improved MVP implemented | `run_strategy_tournament()` ranks momentum candidates and selects tradable paper candidate |
| `live_trading.enabled:true` | Rejected | Committed defaults must remain disabled |
| 全自动实盘真实下单 | Rejected | Real-money orders require owner-side broker confirmation |
