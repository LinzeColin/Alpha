# Alpha Requirements Alignment

| Requirement | Status | Implementation Direction |
|---|---:|---|
| Agent 全自动 paper trading | MVP implemented | `PaperTradingLoop.run_once()` and `run_forever()` |
| Agent 自动生成真实交易候选订单 | MVP implemented | `OrderIntent` generated from strategy signal |
| Agent 自动完成风险检查 | MVP implemented | `pre_trade_risk_check()` before queue entry |
| Agent 自动进入审批队列 | MVP implemented | `ApprovalQueue.enqueue()` |
| Agent 自动生成 broker-ready order ticket | MVP implemented | `BrokerReadyOrderTicket` |
| 每 5 分钟更新一次 | MVP implemented | `refresh_interval_seconds: 300` in service and `configs/agent_loop.yaml` |
| Web dashboard | MVP implemented | `/dashboard` and `/dashboard/state` |
| `live_trading.enabled:true` | Rejected | Committed defaults must remain disabled |
| 全自动实盘真实下单 | Rejected | Real-money orders require owner-side broker confirmation |
