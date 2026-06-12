# Personal Alpha Agent Workspace 执行报告

日期：2026-06-12  
版本：v0.3 Codex-ready Delivery Pack

## 1. 默认推荐方案

你的目标不是普通 agent 客服/接单系统，而是一个 **System-facing Personal Agent Workspace**：

```text
你只和 AI 控制台、系统配置、异常审批、风险日报交互。
Agent 主要和市场数据、回测引擎、paper broker、live broker、交易所 API、数据库、支付/API 系统交互。
```

根据你的选择，最终产品应同时支持四条收益引擎：

| 引擎 | 目标 | 30 天 MVP 定位 |
|---|---|---|
| E1 股票/ETF 量化 Agent | 自有资金系统化 alpha | 股票/ETF 策略 DSL、回测、纸面交易、小额实盘能力 |
| E2 组合再平衡 Agent | 降低人工决策与风险暴露偏差 | 资产配置、风险目标、再平衡建议与可执行订单 |
| E3 Crypto 套利 Agent | 高风险高收益机会 | 先做价差监控、sandbox/paper execution，不做提款和跨链 MEV |
| E4 System-facing API | 把内部能力变成 API 收费 | 风险评分、策略验证、回测报告、市场状态摘要 API |

30 天目标定义为：

> 交付一个能上线运行的 Agent Workspace，具备从数据采集、策略生成、回测、纸面交易、小额实盘、全自动执行、审计、kill switch 到 API 收费原型的闭环能力。实盘 E-mode 可以开发到位，但默认 fail-closed，必须通过 Governor Policy、限额、凭证、审计和 kill switch 后才能执行。

## 2. 为什么不建议直接做“Agent 自主赚钱服务市场”

调研显示，Google Agentspace / Gemini Enterprise、Google Cloud AI Agent Marketplace、OpenAI Apps SDK、Agent.ai 等都在把 agent 变成可发现、可部署、可采购、可嵌入工作流的生态。Google Gemini Enterprise 官方定位是“discover, create, share, and run AI agents”；Google Cloud Marketplace 已经支持用多种框架、协议、runtime 出售 AI agents；OpenAI Apps SDK 通过 MCP server 和 widget runtime 把 app 嵌入 ChatGPT。

但这些更适合 **分发和企业采购**，不适合作为你第一阶段收入主线。你的约束是尽量不和外人互动，因此更优路径是：

```text
先构建个人内部赚钱机器
  -> 验证策略、风控、执行、日志
  -> 将可复用能力抽象成 API
  -> 再考虑 Apps SDK / Google Marketplace / x402 / Stripe usage-based monetization
```

## 3. 技术结论

最适合你的 v0.1 架构不是低代码 agent builder，而是：

```text
FastAPI control plane
+ Postgres audit state
+ Redis/RQ or Prefect workflow runner
+ OpenAI Agents SDK for research/governor/report agents
+ Strategy DSL
+ vectorbt/backtest adapter for fast research
+ paper broker adapter
+ live broker adapter fail-closed
+ CCXT/Freqtrade-compatible crypto adapter later
+ owner console dashboard
```

反向分析结论：

| 来源 | 可借鉴点 | 不直接采用原因 |
|---|---|---|
| LangGraph | durable execution、HITL、状态持久化 | 对 30 天 MVP 可作为后续升级，先不增加复杂度 |
| Dify | visual workflow、RAG、model management、observability | 适合应用平台，不适合高风险交易执行核心 |
| OpenAI Agents SDK | tools、handoffs、guardrails、tracing | 适合作为 agent 编排层 |
| n8n / Flowise / Langflow | 快速搭工具流和可视化 | 面向公网部署时安全面大；交易执行核心不宜依赖低代码节点 |
| QuantConnect Lean | 完整研究-回测-实盘平台 | 可作为参考/可选外部平台，但自有 workspace 更可控 |
| vectorbt | 大规模向量化回测快 | 适合策略筛选与参数扫描 |
| Backtrader | 事件驱动、成熟易懂 | 适合小规模回测和 broker 思路参考 |
| Freqtrade | crypto bot、回测、资金管理、Web UI | Crypto 模块可借鉴，但不要第一版直接 live crypto |
| OpenBB | 金融数据工作区、REST/API/MCP | 适合作为金融数据接入层参考 |
| Temporal/Prefect | workflow resilience | Prefect 适合 30 天，Temporal 可用于后续 durable execution 升级 |

## 4. 30 天里程碑

| 周期 | 目标 | 验收标准 |
|---|---|---|
| Day 1-7 | 控制平面 + 数据 + 策略 DSL + 回测 | 可导入样例数据、验证 DSL、跑 deterministic backtest、生成风险报告 |
| Day 8-14 | 多策略锦标赛 + paper trading + Owner Console | Agent 自动回测、paper portfolio 更新、日报生成、风险 gate 生效 |
| Day 15-21 | 小额实盘能力 + crypto sandbox + API beta | live adapter 默认关闭但代码就绪；小额限额、重复下单检测、kill switch 测试通过 |
| Day 22-30 | E-mode 能力 + 稳定性 + 部署 | 系统可无人值守运行；实盘 E-mode 受限额和政策控制；所有关键动作有审计记录 |

## 5. 硬性质量标准

上线前必须通过：

```text
1. policy fail-closed 测试
2. strategy DSL 禁止杠杆/期权/卖空/外部资金测试
3. backtest deterministic fixture 测试
4. slippage / cost model 测试
5. paper broker 与 live broker 隔离测试
6. duplicate order 防护测试
7. kill switch 测试
8. audit log completeness 测试
9. broker disconnected 测试
10. daily loss limit 测试
```

## 6. 最重要的产品判断

你要做的不是一个“会聊天的 agent space”，而是一个 **资本与系统交互的自治控制平面**。核心竞争力不在 prompt，而在：

```text
数据质量
策略晋级机制
回测防泄漏
执行一致性
风控硬闸门
审计可追溯
小额实盘迭代速度
失败时 fail closed
```

