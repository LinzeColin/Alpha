# Paper Broker Provider Notes

时间：2026-06-13，Australia/Sydney

## Moomoo OpenD 本机只读状态

官方依据：

- Moomoo API 官方介绍说明 Moomoo API 由 OpenD 网关和 API SDK 组成；OpenD 通过 TCP 暴露接口，SDK 负责封装 Python 等语言接口。
  来源：https://openapi.moomoo.com/moomoo-api-doc/en/intro/intro.html
- Moomoo 官方示例中，行情快照使用 `OpenQuoteContext(...).get_market_snapshot(...)`，模拟下单示例需要创建 `OpenSecTradeContext` 并调用 `place_order(..., trd_env=TrdEnv.SIMULATE)`。
  来源：https://openapi.moomoo.com/moomoo-api-doc/en/quick/demo.html
- Moomoo/Futu 交易 FAQ 说明模拟交易下单必须把交易环境设置为 `TrdEnv.SIMULATE`，交易对象和订单接口仍属于交易 API。
  来源：https://openapi.futunn.com/futu-api-doc/en/qa/trade.html
- 交易对象文档说明 `OpenSecTradeContext`、`OpenFutureTradeContext` 和 `OpenCryptoTradeContext` 是交易连接对象；因此 Alpha 当前只读层不得创建这些对象。
  来源：https://openapi.moomoo.com/moomoo-api-doc/en/trade/base.html

本机验收：

- `moomoo-api` 当前 Python 环境可导入，版本 `10.7.6708`。
- 提权只读探测确认本机 OpenD `127.0.0.1:11111` 已连通，状态为“只读探测就绪”。
- 只读行情快照已通过 `OpenQuoteContext` 获取 `US.SPY`、`US.QQQ`、`US.TLT` 共 3 行快照。
- 证据文件：`outputs/moomoo_opend_readiness_20260613.json`。

当前实现：

- Alpha 只使用 Moomoo OpenD 做接口包检测、本机 TCP 探测和只读行情快照。
- Moomoo 只读行情可通过 `ALPHA_MARKET_DATA_PROVIDER=moomoo_opend` 写入本地价格缓存，用于策略迭代和本地模拟交易。
- 当前不会创建 `OpenSecTradeContext`、`OpenFutureTradeContext` 或 `OpenCryptoTradeContext`。
- 当前不会调用 `unlock_trade`、`place_order`、改单、撤单或任何真实账户状态变更接口。
- `moomoo_paper` 在 `configs/paper_broker.yaml` 中仍保持 fail-closed；安装了 Moomoo/OpenD/API 不等于 Alpha 可以自动提交 Moomoo paper 订单。

未完成：

- 尚未实现 Moomoo paper-only 交易适配器。
- 若后续实现，必须单独设计安全 run contract：只允许 `TrdEnv.SIMULATE`、禁用 live trading environment、禁用 unlock trade、禁止真实交易上下文默认启用、增加 mock 回归测试和本机人工确认 E2E。
- 由于项目规则禁止提交可直接触发真实 broker `place_order` 的路径，Moomoo paper 适配器在实现前必须重新审查安全规则与扫描门槛。

## Alpaca Paper API

官方依据：

- Alpaca Paper Trading 文档说明 paper trading 是模拟环境；paper 账户使用不同于 live 账户的 API key，常见 base URL 为 `https://paper-api.alpaca.markets`。
- Alpaca account 文档说明账户读取使用 `GET /v2/account`。
- Alpaca positions 文档说明当前持仓读取使用 `GET /v2/positions`。
- Alpaca orders reference 显示 paper 订单列表 endpoint 为 `https://paper-api.alpaca.markets/v2/orders`。
- Alpaca Orders 文档说明新订单通过 `POST /v2/orders` 创建。
- Alpaca API reference 显示 paper orders endpoint 为 `https://paper-api.alpaca.markets/v2/orders`。

当前实现：

- `AlpacaPaperBrokerAdapter` 只允许 `https://paper-api.alpaca.markets`。
- 凭据只从环境变量读取：`ALPACA_PAPER_KEY_ID`、`ALPACA_PAPER_SECRET_KEY`。
- 默认配置不启用 Alpaca paper 只读同步或纸面下单；只读同步必须同时满足：
  - `paper_broker.provider: alpaca_paper`
  - `paper_broker.allow_external_paper_api: true`
  - `paper_broker.external_paper_api.read_only_sync_enabled: true`
  - paper base URL allowlist 通过
  - 两个 paper 环境变量都存在
- 纸面订单提交还必须同时满足：
  - `paper_broker.provider: alpaca_paper`
  - `paper_broker.allow_external_paper_api: true`
  - `paper_broker.external_paper_api.order_submission_enabled: true`
  - paper base URL allowlist 通过
  - 两个 paper 环境变量都存在
- `/paper/broker/external-snapshot` 读取 paper account、positions 和最近 50 条 orders；返回前会隐藏账户原始 ID、account number 和 API secret。
- 当前只允许 `market/day` 纸面订单。
- 回执不暴露 API key 或 secret。
- `live_order_submission_enabled` 固定为 `false`，不支持 live host。

未完成：

- 尚未把 Alpaca paper fill 回写成本地 portfolio source of truth。
- 尚未在用户本机真实 Alpaca paper account 上做只读同步或 E2E 下单验证。
