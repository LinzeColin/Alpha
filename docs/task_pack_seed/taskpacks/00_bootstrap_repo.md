# Task Pack 00 — Bootstrap Repo Skeleton

## Goal

Create the initial monorepo skeleton for `personal-quant-agent-space`.

Do not implement trading logic yet.

## Scope

Create:

```text
apps/api/
apps/web/
agents/
quant/
packages/policies/
packages/schemas/
tests/
docker-compose.yml
Makefile
README.md
.env.example
.gitignore
```

## Assumptions

- Empty or nearly empty repo.
- Backend is Python + FastAPI.
- Frontend is Next.js + TypeScript.
- Database is Postgres.
- Queue is Redis.
- Tests must run without live API credentials.

## Files to Create

```text
README.md
.env.example
.gitignore
docker-compose.yml
Makefile

apps/api/pyproject.toml
apps/api/app/__init__.py
apps/api/app/main.py
apps/api/app/core/config.py
apps/api/app/routes/health.py

apps/web/package.json
apps/web/tsconfig.json
apps/web/next.config.js
apps/web/app/page.tsx
apps/web/app/dashboard/page.tsx

agents/__init__.py
quant/__init__.py
packages/policies/risk_policy.yaml
packages/schemas/strategy_dsl.schema.json

tests/unit/test_health.py
```

## API Requirements

`GET /health` returns:

```json
{
  "status": "ok",
  "service": "personal-quant-agent-space",
  "live_trading_enabled": false
}
```

## Environment Variables

Create `.env.example`:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agent_space
REDIS_URL=redis://localhost:6379/0

OPENAI_API_KEY=

BROKER_PROVIDER=none
LIVE_TRADING_ENABLED=false
RING_FENCED_ACCOUNT_ID=
OWNER_E_SAFE_ACK=false

ALPACA_PAPER_KEY_ID=
ALPACA_PAPER_SECRET_KEY=
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=101

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

## Initial Risk Policy

Create `packages/policies/risk_policy.yaml` with:

```yaml
system_mode: "research_only"

live_trading:
  enabled: false
  require_manual_enablement: true
  require_ring_fenced_account: true
  fail_closed_on_policy_error: true

asset_permissions:
  allow_stocks: true
  allow_etfs: true
  allow_options: false
  allow_short: false
  allow_leverage: false
  allow_margin: false
  allow_crypto_live: false

order_limits:
  max_order_value_aud: 0
  max_orders_per_day: 0
  max_position_weight_pct: 0
  max_daily_loss_pct: 0

kill_switch:
  enabled: true
  force_paused: true
```

## Commands

Suggested:

```bash
make install
make test
make lint
make typecheck
```

If full install is not possible, run the subset available in the environment and report honestly.

## Acceptance Criteria

```text
1. Repo skeleton exists.
2. FastAPI app starts.
3. /health returns live_trading_enabled=false.
4. Frontend dashboard page renders placeholder status.
5. Docker Compose defines Postgres and Redis.
6. Makefile has install/test/lint/typecheck targets.
7. No real credentials are present.
8. No broker or trading logic is implemented.
```

## Rollback

Delete created skeleton files/directories or revert the commit.
