# Alpha - 个人量化智能体工作台

Alpha 是本地优先的个人量化智能体工作台，用于研究、回测、全自动模拟交易、候选订单审核、经纪商就绪订单工单生成和控制台状态展示。

## 本地运行

```bash
python -m pip install -e .
python -m pytest tests -q
python -m backend.app.services.paper_trading_loop --once
uvicorn backend.app.main:app --reload
```

`paper_trading_loop --once` 默认输出中文人工可读摘要；如需给自动化读取原始机器字段，使用：

```bash
python -m backend.app.services.paper_trading_loop --once --json
```

启动/停止本地工作台：

```bash
scripts/start_alpha_dashboard.sh
scripts/stop_alpha_dashboard.sh
```

控制台启动后，FastAPI 应用生命周期会启动自动模拟交易智能体运行时：立即运行一次模拟交易周期，然后每 300 秒刷新一次。

默认运行状态写入本地 `runtime/` 目录：

```text
runtime/approval_queue.sqlite3
runtime/paper_portfolio.json
```

`.app` 格式入口已安装到：

```text
/Users/linzezhang/Downloads/Alpha.app
/Users/linzezhang/Applications/Alpha.app
/Applications/Alpha.app
```

可访问：

```text
http://localhost:8000/health
http://localhost:8000/dashboard
http://localhost:8000/dashboard/state
```

常用 API 端点：

```text
POST /paper/run-once
GET  /paper/portfolio
GET  /paper/broker/status
POST /strategy/tournament/run
GET  /agent/loop/status
GET  /orders/approval-queue
POST /orders/approval-queue/{ticket_id}/owner-review
POST /orders/approval-queue/{ticket_id}/reject
POST /orders/approval-queue/{ticket_id}/mark-exported
```

## 安全边界

- 实盘交易默认禁用。
- 实盘 broker adapter 失败即关闭。
- 策略/风控配置加载失败即拒绝。
- 外部 API 不得触发真实资金下单。
- Alpha 可以生成供用户审核的经纪商就绪订单工单，但不得自主提交真实资金订单。
- 当前模拟交易执行层使用 `LocalSandboxPaperBrokerAdapter`；它返回 broker-like paper receipt，但不需要凭据，也不允许真实下单。
- 审批队列默认使用 SQLite 持久化，支持在网页/API 中标记“已人工复核”“已拒绝”“工单已导出”；这些动作只更新本地审计状态，不会调用真实 broker 下单接口。

## 中文显示

- 控制台页面、按钮、表格、状态、风险原因、执行层名称、策略名称和本地命令摘要默认中文显示。
- API 字段名、内部枚举、工单号、文件路径和股票代码保持机器可读格式，供测试、MCP、后续券商适配器和自动化流程稳定使用。
