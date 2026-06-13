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
scripts/check_alpha_ops.sh
scripts/check_alpha_ops.sh --backup
```

控制台启动后，FastAPI 应用生命周期会启动自动模拟交易智能体运行时：立即运行一次模拟交易周期，然后每 300 秒刷新一次。

默认运行状态写入本地 `runtime/` 目录：

```text
runtime/approval_queue.sqlite3
runtime/paper_portfolio.json
runtime/paper_performance_history.jsonl
runtime/market_data/latest_prices.csv
runtime/strategy_tournament_history.jsonl
runtime/backups/
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
GET  /paper/performance/history
GET  /paper/broker/status
GET  /broker/moomoo/status
POST /strategy/tournament/run
GET  /strategy/tournament/history
GET  /agent/loop/status
GET  /market-data/status
POST /market-data/refresh
GET  /ops/health
POST /ops/backup
GET  /ops/maintenance/status
GET  /orders/approval-queue
GET  /orders/approval-queue/{ticket_id}/broker-ticket
GET  /orders/approval-queue/{ticket_id}/broker-ticket/view
GET  /orders/approval-queue/{ticket_id}/broker-ticket.csv
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
- 当前模拟交易执行层使用 `LocalSandboxPaperBrokerAdapter`；它返回类经纪商模拟回执，但不需要凭据，也不允许真实下单。
- Moomoo OpenD 集成当前只做只读连接探测：检测当前 Python 环境是否可导入 `moomoo`/`futu` API 包，并检测本机 OpenD 端口；不会解锁交易、不会读取或提交交易凭据、不会调用真实下单接口。
- 审批队列默认使用 SQLite 持久化，支持在网页/API 中标记“已人工复核”“已拒绝”“工单已导出”；这些动作只更新本地审计状态，不会调用真实 broker 下单接口。
- 已人工复核且仍在有效期内的工单可导出为 JSON 或 CSV 人工录入包；过期工单不能复核或导出。

## 运行健康与备份

- `GET /ops/health` 汇总自动循环、SQLite 审批队列、模拟组合、模拟执行层边界、Moomoo OpenD 只读探测、行情数据、控制台进程、日志和最近备份状态。
- `POST /ops/backup` 会在 `runtime/backups/` 下生成一次本地运行状态备份，包含审批队列快照、模拟组合、行情缓存、PID 和日志尾部。
- `GET /ops/maintenance/status` 显示应用托管自动运行维护：健康采样次数、自动备份次数、下次维护时间、健康历史文件和备份轮转配置。
- `scripts/check_alpha_ops.sh` 输出中文健康检查摘要；加 `--json` 可输出机器 JSON。
- `scripts/check_alpha_ops.sh --backup` 可在终端生成一次本地运行状态备份。
- 控制台启动后会自动启动运行维护：默认每 300 秒采样一次健康状态，默认每天自动备份一次，并保留最近 30 份备份。
- 健康检查和备份只覆盖模拟交易与工单状态，不会提交真实资金订单。

## 行情数据

- 默认配置在 `configs/market_data.yaml`。
- 默认模式为 `cache_or_fixture`：优先读取本地行情缓存；缓存缺失时回退到 `data/sample_prices.csv`，并在控制台标记为“样例数据”。
- `POST /market-data/refresh` 会尝试刷新 Stooq 公共延迟行情缓存；外部网络或数据源失败时不阻塞系统，会回退到本地数据并在控制台显示刷新失败。
- Stooq 数据源用于研究和模拟交易，不是券商级实时行情源。

## 中文显示

- 控制台页面、按钮、表格、状态、风险原因、执行层名称、策略名称、行情状态、模拟绩效和本地命令摘要默认中文显示。
- 策略迭代历史、模拟绩效历史、自动循环状态、运行健康、维护状态、风控原因和工单导出包会提供中文展示字段，例如 `status_zh`、`reason_zh`、`winner_strategy_id_zh`、`winner_decision_zh`。
- API 字段名、内部枚举、工单号、文件路径和股票代码保持机器可读格式，供测试、MCP、后续券商适配器和自动化流程稳定使用；面向 owner 的界面必须优先展示中文字段。
- 新增界面或命令输出时必须补充中文展示映射；如确需展示 raw enum，必须同时给出中文标签或中文解释。

## 策略迭代历史

- `PaperTradingLoop` 每次自动模拟交易周期会把策略锦标赛结果追加写入 `runtime/strategy_tournament_history.jsonl`。
- `GET /strategy/tournament/history` 汇总记录次数、最近胜出策略、连续胜出次数、最近稳定度和最近运行明细。
- Dashboard 的“策略迭代历史”面板显示最近胜出策略、样本外收益、命中率、决策和行情质量，默认使用中文展示字段。

## 模拟绩效历史

- `PaperTradingLoop` 每次自动模拟交易周期会把组合权益快照追加写入 `runtime/paper_performance_history.jsonl`。
- `GET /paper/performance/history` 汇总记录次数、最新总权益、累计收益率、最新权益变化、权益高水位、最大回撤、当前回撤、累计佣金和执行模型。
- Dashboard 的“模拟绩效”面板显示权益历史、收益率、回撤、最新策略、标的、方向、佣金、执行模型和交易次数，默认使用中文展示字段。

## 模拟执行成本

- `LocalSandboxPaperBrokerAdapter` 默认使用“固定佣金与滑点模型”：买入按参考价上浮 5.00 基点成交，并计入每笔 1.00 AUD 模拟佣金。
- Paper broker 会把模拟成交价、参考价、佣金、滑点和累计佣金写入组合状态与绩效历史。
- Dashboard 的“模拟交易执行层”和“模拟绩效”会显示执行模型、模拟滑点、单笔佣金、累计佣金和最近成交成本。
- 该模型只影响本地 paper trading 绩效，不调用真实经纪商下单接口。

## Moomoo OpenD 只读探测

- `GET /broker/moomoo/status` 显示 Moomoo OpenD 只读探测状态。
- 默认连接地址为 `127.0.0.1:11111`；可用 `MOOMOO_OPEND_HOST`、`MOOMOO_OPEND_PORT`、`MOOMOO_OPEND_TIMEOUT_SECONDS` 调整。
- Dashboard 的“Moomoo OpenD”面板会显示 API 包、OpenD 连接、只读就绪、交易解锁、允许真实下单和禁止操作。
- 该探测层只用于确认本机环境是否准备好接入后续 read-only quote/account 能力；当前不会提交真实资金订单。
