# Paper Broker Provider Notes

时间：2026-06-13，Australia/Sydney

## Alpaca Paper API

官方依据：

- Alpaca Paper Trading 文档说明 paper trading 是模拟环境；paper 账户使用不同于 live 账户的 API key，常见 base URL 为 `https://paper-api.alpaca.markets`。
- Alpaca Orders 文档说明新订单通过 `POST /v2/orders` 创建。
- Alpaca API reference 显示 paper orders endpoint 为 `https://paper-api.alpaca.markets/v2/orders`。

当前实现：

- `AlpacaPaperBrokerAdapter` 只允许 `https://paper-api.alpaca.markets`。
- 凭据只从环境变量读取：`ALPACA_PAPER_KEY_ID`、`ALPACA_PAPER_SECRET_KEY`。
- 默认配置不启用 Alpaca paper 下单；必须同时满足：
  - `paper_broker.provider: alpaca_paper`
  - `paper_broker.allow_external_paper_api: true`
  - `paper_broker.external_paper_api.order_submission_enabled: true`
  - paper base URL allowlist 通过
  - 两个 paper 环境变量都存在
- 当前只允许 `market/day` 纸面订单。
- 回执不暴露 API key 或 secret。
- `live_order_submission_enabled` 固定为 `false`，不支持 live host。

未完成：

- 尚未接入真实 Alpaca account/position 同步。
- 尚未把 Alpaca paper fill 回写成本地 portfolio source of truth。
- 尚未在用户本机真实 Alpaca paper account 上做 E2E 下单验证。
