# Task Pack 11 — API Revenue Layer Sandbox

## Goal

Create a system-facing API revenue sandbox.

This API sells non-advisory tooling:
- strategy DSL validation
- backtest report generation
- portfolio risk scoring

It must not sell personalized financial advice or buy/sell recommendations.

## Files to Inspect

```text
quant/strategies/
quant/backtest/
quant/risk/
apps/api/app/core/policy_engine.py
```

## Files to Create / Modify

```text
apps/api/app/routes/public_api.py
apps/api/app/routes/payments.py
apps/api/app/services/stripe_service.py
apps/api/app/services/x402_stub.py
apps/api/app/core/api_auth.py
apps/api/app/core/rate_limits.py

tests/unit/test_public_api_policy.py
tests/integration/test_stripe_sandbox_payment.py
tests/integration/test_public_api_non_advisory.py
```

## Public Endpoints

```text
POST /public/strategy-dsl/validate
POST /public/backtest-report
POST /public/portfolio-risk-score
POST /payments/stripe/create-test-checkout
GET /payments/status/{id}
```

## Restrictions

```text
1. Do not return "buy/sell/hold this asset" recommendations.
2. Do not accept user-specific financial situation fields.
3. Do not optimize portfolio for a named external person's circumstances.
4. Do not store payment secrets.
5. Use Stripe test/sandbox mode only.
6. x402 is stub only in MVP.
```

## Tests

```bash
pytest tests/unit/test_public_api_policy.py
pytest tests/integration/test_stripe_sandbox_payment.py
pytest tests/integration/test_public_api_non_advisory.py
```

## Acceptance Criteria

```text
1. Public API can validate DSL.
2. Public API can generate generic backtest report.
3. Public API can score generic portfolio risk.
4. Attempts to request personalized advice are rejected.
5. Stripe test checkout can be created if test key configured.
6. x402 stub returns not_enabled status.
```

## Rollback

Revert public API/payment files.
