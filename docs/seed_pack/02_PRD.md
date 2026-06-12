# PRD - Personal Alpha Agent Workspace

## 1. 产品定位

Personal Alpha Agent Workspace 是一个个人系统型赚钱 Agent Space。它不依赖外部客户沟通，不做冷邮件，不做客服，不靠接单服务赚钱。它面向市场、API、交易系统、回测系统和数据系统运行。

## 2. 用户画像

```text
Owner: 单人开发者/研究者/资金所有者
交互偏好: 只和 AI / Dashboard / 系统配置打交道
风险偏好: 中高风险系统化 alpha + 高风险高收益机会，但需要工程风控
时间目标: 30 天内开发上线并具备全自动实盘能力
```

## 3. 核心目标

| 目标 | 说明 |
|---|---|
| G1 | 建立可运行的个人 Agent Workspace 控制平面 |
| G2 | 支持股票/ETF 策略研究、回测、纸面交易和小额实盘能力 |
| G3 | 支持组合再平衡策略和风险目标控制 |
| G4 | 支持 Crypto 套利监控、paper/sandbox execution |
| G5 | 支持内部能力 API 化，为后续 Stripe/x402 收费做准备 |
| G6 | 30 天内具备 E-mode 全自动能力，但默认 fail-closed |
| G7 | 所有 agent 决策、策略晋级、订单、失败、kill switch 可审计 |

## 4. 非目标

```text
- 不管理第三方资金
- 不提供面向公众的金融建议
- 不发布买卖信号
- 不支持第一版杠杆、期权、融资融券、裸卖空
- 不做高频交易、MEV、跨链闪电贷套利
- 不做冷外联、接单、客服型商业模式
- 不把低代码 workflow 平台作为交易执行核心
```

## 5. 收益引擎

### E1 股票/ETF 量化 Agent

能力：

```text
- 策略 DSL
- 市场数据同步
- 策略生成与参数扫描
- 回测
- out-of-sample 检查
- 成本/滑点模型
- paper trading
- 小额 live execution adapter
```

MVP 策略类型：

```text
- ETF momentum rotation
- volatility target
- moving average trend following
- mean reversion watchlist, paper only
- sector/asset allocation rebalancing
```

### E2 组合再平衡 Agent

能力：

```text
- 目标权重配置
- 当前持仓导入
- 风险暴露计算
- 再平衡订单建议
- drift threshold
- tax-aware note, no tax advice
- paper/live rebalance execution
```

### E3 Crypto 套利 Agent

MVP 只做：

```text
- 价格价差监控
- 费用和滑点估算
- sandbox/paper execution
- opportunity scoring
- exchange health check
```

MVP 不做：

```text
- 自动提款
- 跨交易所真实资金转移
- 杠杆合约
- 永续资金费率重仓
- MEV / flash loan
```

### E4 System-facing API

第一版 API：

```text
POST /api/v1/strategy/validate
POST /api/v1/backtest/run
POST /api/v1/risk/score
POST /api/v1/portfolio/rebalance
GET  /api/v1/market/regime
```

后续收费：

```text
- Stripe usage-based billing
- Stripe Agent Toolkit for restricted payment operations
- x402 machine-to-machine micro-payment endpoint
```

## 6. 用户交互原则

Owner 只看：

```text
- 日报
- 异常
- kill switch 状态
- live exposure
- PnL / drawdown
- strategy promotion queue
- API revenue / usage
```

Owner 不做：

```text
- 和客户销售
- 和外人沟通需求
- 手动跑回测
- 手动整理日报
- 手动复盘每个订单
```

## 7. 自动化等级

| 等级 | 名称 | 描述 | 30 天目标 |
|---|---|---|---|
| L0 | Research only | 只研究，不交易 | Day 3 |
| L1 | Backtest autonomous | 自动回测和生成风险报告 | Day 7 |
| L2 | Paper autonomous | 自动纸面交易 | Day 14 |
| L3 | Tiny live guarded | 小额实盘，硬限额 | Day 21 |
| L4 | Autonomous guarded live | 策略在限额内全自动运行 | Day 30 |
| L5 | Unbounded live autonomy | 无边界全自动 | 永不作为默认目标 |

这里将你的 “E” 工程化定义为：

```text
L4 Autonomous guarded live：
- 可无人值守运行
- 可自动下单
- 有硬限额
- 有 kill switch
- 有审计
- 有异常停机
- 不代表无边界资金自治
```

## 8. 核心用户故事

### US1: 策略从假设到 paper

```text
As Owner,
I want agents to propose and backtest ETF strategies,
so that only strategies passing risk gates enter paper trading.
```

验收：

```text
- Agent 生成 structured strategy DSL
- Backtest 可复现
- Risk report 有 max drawdown、volatility、turnover、cost-adjusted return
- Governor 给出 promote/reject/hold
```

### US2: paper 到 guarded live

```text
As Owner,
I want a strategy with sufficient paper evidence to be promoted to tiny live mode,
so that real capital exposure remains tightly capped.
```

验收：

```text
- min paper days passed
- duplicate order check passed
- live trading env explicitly enabled
- max order notional enforced
- kill switch can stop execution
```

### US3: Crypto 套利监控

```text
As Owner,
I want crypto agents to detect arbitrage candidates without moving real funds,
so that I can evaluate opportunity quality before enabling anything risky.
```

验收：

```text
- Fetch prices from at least 2 exchange adapters or mock adapters
- Compute fees/slippage-adjusted spread
- Produce opportunity score
- No withdrawal capability exists
```

### US4: API 副线

```text
As Owner,
I want internal risk/backtest/rebalance functions exposed as authenticated APIs,
so that later they can be monetized by systems or agents.
```

验收：

```text
- API keys supported
- rate limits supported
- request/response logged
- no live trading endpoint exposed externally
```

## 9. 验收标准

v0.1 complete:

```text
1. Repo can run local FastAPI app.
2. Strategy DSL schema validates stock/ETF strategy and rejects leverage/options/short.
3. Sample market data can be ingested.
4. Deterministic backtest runs on fixture data.
5. Risk report is produced.
6. Paper portfolio updates with simulated orders only.
7. Live broker adapter fails closed by default.
8. Governor policy blocks prohibited actions.
9. Owner console endpoint returns daily summary.
10. Audit log records every agent/workflow/action.
```

v0.2 30-day target:

```text
1. Scheduled daily research cycle runs unattended.
2. Multiple strategies compete in paper mode.
3. Tiny live mode is implemented and policy-gated.
4. Kill switch tested.
5. Crypto sandbox/paper arbitrage monitor implemented.
6. API monetization endpoints implemented behind auth.
7. Docker deploy works.
8. Test suite passes.
9. All live-related config is explicit and off by default.
10. Daily owner report produced automatically.
```

