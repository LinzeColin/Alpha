# Task Pack 10 — Crypto Scanner and Paper Arbitrage Simulator

## Goal

Add crypto opportunity scanner and paper arbitrage simulator.

No live crypto trading. No withdrawals. No CEX/DEX execution.

## Files to Inspect

```text
packages/policies/risk_policy.yaml
quant/execution/
quant/data/
```

## Files to Create / Modify

```text
quant/crypto/models.py
quant/crypto/exchange_data_adapter.py
quant/crypto/fixture_crypto_adapter.py
quant/crypto/spread_scanner.py
quant/crypto/funding_rate_scanner.py
quant/crypto/paper_arb_simulator.py

apps/api/app/routes/crypto.py

tests/fixtures/crypto_prices_sample.json
tests/unit/test_crypto_spread_scanner.py
tests/unit/test_crypto_paper_arb_simulator.py
tests/integration/test_crypto_live_rejected.py
```

## Required Behavior

```text
1. Read-only price/funding data only.
2. Live crypto orders rejected by policy.
3. Withdrawals are not implemented.
4. Scanner reports opportunity estimate with fees and slippage assumptions.
5. Paper simulator records hypothetical fills only.
6. Every scanner run is audit logged.
```

## API Endpoints

```text
GET /crypto/scanner/status
POST /crypto/scanner/run-once
GET /crypto/opportunities
POST /crypto/paper-arb/simulate
```

## Tests

```bash
pytest tests/unit/test_crypto_spread_scanner.py
pytest tests/unit/test_crypto_paper_arb_simulator.py
pytest tests/integration/test_crypto_live_rejected.py
```

## Acceptance Criteria

```text
1. Crypto scanner works from fixtures.
2. Live crypto trading is rejected.
3. Withdrawal functions do not exist.
4. Paper arb simulation includes fees/slippage.
5. Results are clearly labeled hypothetical.
```

## Rollback

Revert crypto files and routes.
