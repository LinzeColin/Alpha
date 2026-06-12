# Agent Workspace 与相似项目市场调研 + 反向开源分析

## 1. 市场分层

Agent workspace 市场正在分化成五类，而你的项目属于第五类。

| 类型 | 代表项目 | 核心价值 | 与本项目关系 |
|---|---|---|---|
| 企业 Agent Hub | Google Agentspace / Gemini Enterprise | 企业搜索、权限、agent 管理、工作流 | 借鉴治理、权限、agent registry，不做企业知识库 |
| Agent Marketplace | Google Cloud Marketplace、Agent.ai | 发现、购买、部署 agent | 后期 API/agent 分发渠道，不作为第一收入主线 |
| Agent App Runtime | OpenAI Apps SDK、MCP Apps | 在 ChatGPT/host 中运行工具和 UI | 后期可把 API 能力包装成 app |
| 开发者 Agent Framework | OpenAI Agents SDK、LangGraph、AutoGen、CrewAI | 多 agent 编排、工具调用、guardrails、trace | 本项目核心编排参考 |
| System-facing Autonomous Workspace | QuantConnect、OpenBB、Freqtrade、Lean、内部交易系统 | 与市场/API/数据/交易系统交互产生收益 | 本项目主线 |

## 2. Enterprise Agent Workspace 观察

### 2.1 Google Agentspace / Gemini Enterprise

官方定位：Gemini Enterprise app 是一个安全平台，员工可以 discover/create/share/run AI agents。Agentspace/Gemini Enterprise 强调企业知识、权限感知搜索、agent 工作流、企业 connector 和治理。

可借鉴能力：

```text
- Agent registry：所有 agent 有 ID、描述、能力边界、权限
- Permission-aware access：agent 不能越权访问数据
- Inbox / task visibility：所有 agent 活动在一个工作台可见
- Agent gateway：敏感系统调用经过网关
- Observability：生产运行需要日志、trace、质量评估
```

对本项目的反向结论：

```text
不要先做企业知识搜索。
应该做一个个人 Owner Console + Agent Registry + Governor Gateway。
所有交易、报价、API 计费动作都必须经过 Gateway。
```

参考：
- https://cloud.google.com/gemini-enterprise
- https://cloud.google.com/blog/products/ai-machine-learning/google-agentspace-enables-the-agent-driven-enterprise
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview

### 2.2 Google Cloud AI Agent Marketplace / Agent.ai

Google Cloud Marketplace 支持 AI agents 上架，agent 可以由任意框架构建，使用任意通信协议，运行在 Google Cloud 或其他 runtime。Agent.ai 面向个人和专业 agent 的发现、构建、激活。

反向结论：

```text
Marketplace 是分发渠道，不是早期产品形态。
你的系统应先通过自有资金/系统 API 验证价值，再考虑上架。
```

参考：
- https://docs.cloud.google.com/marketplace/docs/partners/ai-agents
- https://cloud.google.com/blog/topics/partners/google-cloud-ai-agent-marketplace
- https://agent.ai/

## 3. Agent Framework 反向分析

### 3.1 OpenAI Agents SDK

核心能力：agent definitions、tools、handoffs、guardrails、structured outputs、tracing。官方 tracing 会记录 LLM generations、tool calls、handoffs、guardrails、自定义事件。

可借鉴：

```text
- Research Agent / Risk Agent / Governor Agent / Console Agent 拆分
- 每个 agent 输出 structured JSON，不允许自由文本直接驱动交易
- handoff 用于从 Research -> Backtest -> Risk -> Governor
- tracing 用于生产审计
- guardrails 用于禁止越权动作
```

参考：
- https://developers.openai.com/api/docs/guides/agents
- https://openai.github.io/openai-agents-python/tracing/
- https://openai.github.io/openai-agents-python/guardrails/

### 3.2 LangGraph

LangGraph 强调 durable execution、streaming、human-in-the-loop、persistence。官方文档称其是 orchestration runtime，适合持久运行、可暂停、可恢复的 agent 工作流。

可借鉴：

```text
- 策略晋级流程适合 graph/state machine
- 交易前 gate 可以用 interrupt/human-in-loop 模式
- 长流程需要持久化 state，避免进程失败导致重复下单
```

反向取舍：

```text
30 天 MVP 可先用简单状态机 + RQ/Prefect。
如果后续进入多 agent 长流程和实盘资本扩大，再迁移到 LangGraph/Temporal。
```

参考：
- https://docs.langchain.com/oss/python/langgraph/overview
- https://github.com/langchain-ai/langgraph

### 3.3 Dify

Dify 是开源 LLM app development platform，组合 AI workflow、RAG pipeline、agent capabilities、model management、observability。

可借鉴：

```text
- Workflow builder 思维：每个流程可视化、可审计、可重放
- Model provider abstraction：模型可替换
- Observability：agent 运行质量和成本要被观测
```

不直接采用：

```text
交易执行核心需要可测试、代码优先、强类型、fail-closed。
低代码/通用 LLM workflow 不适合直接控制真钱交易。
```

参考：
- https://github.com/langgenius/dify
- https://dify.ai/

### 3.4 AutoGen / AutoGen Studio

AutoGen Studio 是低代码 UI，可快速原型化 agent、工具、团队。AutoGen AgentChat 是高层 API，适合 multi-agent 应用。GitHub 页面显示旧 AutoGen repo 已进入 maintenance mode，需要谨慎选型。

反向结论：

```text
可借鉴 team/agent declarative spec。
不建议作为新项目的核心生产 runtime。
```

参考：
- https://microsoft.github.io/autogen/stable//index.html
- https://github.com/microsoft/autogen

### 3.5 CrewAI

CrewAI 定位为多 agent 自动化框架，官方强调 agents、crews、flows、guardrails、memory、knowledge、observability。Flows 提供结构化、event-driven workflow。

可借鉴：

```text
- Agent role separation
- Flows for event-driven process
- Guardrails and observability as first-class concerns
```

参考：
- https://docs.crewai.com/
- https://github.com/crewaiinc/crewai

### 3.6 Flowise / Langflow / n8n

Flowise 和 Langflow 都提供可视化 AI workflow/agent 构建能力。Langflow 支持构建 AI agents 和 MCP servers。n8n 是 workflow automation 工具，结合 AI capabilities 与业务流程自动化，并有大量 integrations。

反向结论：

```text
适合做外围自动化，如日报推送、数据同步、Webhook、API 收费流程。
不适合作为交易执行核心。
公网暴露的低代码工作流平台安全面较大，应避免直接暴露 broker credentials。
```

参考：
- https://github.com/flowiseai/flowise
- https://docs.langflow.org/
- https://docs.n8n.io/

## 4. Quant / Trading 项目反向分析

### 4.1 QuantConnect Lean

QuantConnect 提供研究、回测和 live trading。Lean 是开源算法交易引擎，支持命令行管理项目、运行回测、部署 live algorithms。

可借鉴：

```text
- Research -> Backtest -> Live 的一体化生命周期
- Brokerage adapter abstraction
- Algorithm project structure
- Backtest artifacts and metrics
```

取舍：

```text
Lean 很完整但重。
本项目 30 天内应先自建轻量策略 DSL + backtest adapter；后续可接 Lean。
```

参考：
- https://www.quantconnect.com/
- https://github.com/quantconnect/lean

### 4.2 Backtrader

Backtrader 是 Python backtesting/trading 框架，强调 reusable strategy、indicators、analyzers，并有 live trading/broker 概念。

可借鉴：

```text
- Strategy/Analyzer/Broker separation
- Event-driven backtest mental model
- Broker abstraction
```

参考：
- https://www.backtrader.com/
- https://github.com/mementum/backtrader

### 4.3 vectorbt

vectorbt 是向量化 backtesting/quant analysis 包，基于 pandas/NumPy/Numba/Rust，能快速测试大量策略。

可借鉴：

```text
- 第一阶段策略筛选、参数扫描、组合回测应该用 vectorized engine
- Agent 提出多个策略假设后，用 vectorized sweep 快速淘汰
```

参考：
- https://vectorbt.dev/
- https://github.com/polakowo/vectorbt

### 4.4 Freqtrade

Freqtrade 是开源 crypto trading bot，支持回测、plotting、money management、ML strategy optimization、Web UI/Telegram 控制，支持多交易所。

可借鉴：

```text
- Crypto 交易 bot 的资金管理、dry-run、Web UI
- Exchange adapter 基于 CCXT 的思路
- 不同交易所特殊配置要隔离
```

限制：

```text
Crypto 高风险，不应第一版直接做自动提款、杠杆、跨链 MEV。
```

参考：
- https://www.freqtrade.io/en/stable/
- https://github.com/freqtrade/freqtrade

### 4.5 FinRL

FinRL 是金融强化学习框架，按 market environments、DRL agents、financial applications 组织，适合教育、实验、研究原型。

取舍：

```text
RL 可作为后期研究，不作为 30 天收益主线。
30 天内优先规则/因子/组合策略，因为可解释、可回测、易风控。
```

参考：
- https://github.com/AI4Finance-Foundation/FinRL
- https://finrl.readthedocs.io/en/latest/index.html

### 4.6 OpenBB

OpenBB 提供金融数据平台，连接 proprietary、licensed、public data 到 Python、Workspace、Excel、MCP servers、REST APIs。

可借鉴：

```text
- Data connector layer
- Financial workspace + AI agent 同时使用数据
- MCP/REST API 暴露内部数据能力
```

参考：
- https://github.com/OpenBB-finance/OpenBB
- https://docs.openbb.co/

## 5. Broker / Trading API 观察

### 5.1 IBKR

IBKR TWS API 是基于 TWS 或 IB Gateway 的 TCP Socket Protocol API，可自主获取和发送数据到 Interactive Brokers。IBKR 提供 Web API、TWS API、Excel API、FIX 等文档。

结论：

```text
IBKR 适合做股票/ETF 实盘 adapter，但接入复杂度高。
30 天 MVP 应先完成 PaperBroker + LiveBroker interface；IBKR adapter 作为 day 15-30 的可选实现。
```

参考：
- https://www.interactivebrokers.com/campus/ibkr-api-page/trader-workstation-api/
- https://www.interactivebrokers.com/campus/ibkr-api-page/ibkr-api-home/

### 5.2 Alpaca

Alpaca 提供股票、期权、crypto trading API，并有 paper trading。官方说明 Paper Trading API 不需要真钱，也不代表真实证券交易。

结论：

```text
Alpaca paper API 适合快速开发和验证 execution flow。
是否能用于你的实际地区/账户，需要在上线前单独核验。
```

参考：
- https://docs.alpaca.markets/us/docs/paper-trading
- https://docs.alpaca.markets/us/docs/trading-api

## 6. API 收费 / Agentic Commerce 观察

Stripe Agent Toolkit 可以把 Stripe 接入 agentic workflows，并建议使用 sandbox 和 restricted keys。x402 是 HTTP 402 Payment Required 方向的机器支付协议，用 stablecoin 支持 API/digital content 的程序化按次付费。

对本项目的结论：

```text
第一阶段不要靠外部客户变现 API。
先把内部 risk-score/backtest/regime API 做成可调用服务。
稳定后用 Stripe usage-based 或 x402 做 system-facing monetization。
```

参考：
- https://docs.stripe.com/agents
- https://docs.stripe.com/payments/machine/x402
- https://docs.cdp.coinbase.com/x402/welcome

## 7. 监管与税务边界

本项目只应处理自有账户、自有资金、自有研究。澳洲监管环境中，向客户提供金融产品建议通常涉及 AFS licence 问题；ATO 对 share investing 和 share trading 有不同税务处理，也有 crypto asset investments 指引。ASIC 对 automated trading / AI risks 也强调算法交易风险控制。

工程结论：

```text
- 不向第三方提供个性化买卖建议
- 不管理外部资金
- 不发布自动买卖信号
- 所有交易、订单、持仓、盈亏、费用、税务事件必须记录
- 不承诺收益
```

参考：
- https://www.asic.gov.au/regulatory-resources/financial-services/giving-financial-product-advice/
- https://www.asic.gov.au/about-asic/news-centre/news-items/asic-moves-to-modernise-trading-system-rules-to-keep-pace-with-technology-and-ai/
- https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/share-investing-versus-share-trading
- https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments

## 8. 对本项目的最终反向设计结论

### 必须复制的能力

```text
1. Agent registry
2. Permissioned tool gateway
3. Structured output only
4. Durable state / resumable jobs
5. Full audit log
6. Workflow trace
7. Strategy lifecycle gates
8. Broker adapter abstraction
9. Paper/live isolation
10. Kill switch
```

### 必须避免的能力

```text
1. 让 LLM 直接决定订单 without structured validation
2. 自由文本驱动真钱交易
3. 低代码公网 workflow 直接持有 broker key
4. 未回测策略直接 live
5. 未记录税务事件
6. 无法复现的 backtest
7. 依赖单一市场数据源
8. 用 agent 幻觉解释替代 quantitative metrics
```

