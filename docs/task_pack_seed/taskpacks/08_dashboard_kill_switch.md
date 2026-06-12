# Task Pack 08 — Dashboard and Kill Switch UI

## Goal

Build the owner control dashboard.

This is the owner's only routine interface.

## Files to Inspect

```text
apps/web/
apps/api/app/routes/
```

## Files to Create / Modify

```text
apps/web/app/dashboard/page.tsx
apps/web/app/strategies/page.tsx
apps/web/app/backtests/page.tsx
apps/web/app/paper/page.tsx
apps/web/app/risk/page.tsx
apps/web/app/broker/page.tsx
apps/web/app/audit/page.tsx
apps/web/app/settings/policy/page.tsx
apps/web/components/StatusCard.tsx
apps/web/components/KillSwitchButton.tsx
apps/web/components/RiskTable.tsx
apps/web/lib/api.ts

tests/web/dashboard.test.tsx
```

## Dashboard Sections

```text
1. System mode
2. Live trading enabled/disabled
3. Kill switch status
4. Paper strategies active
5. Tiny-live readiness checklist
6. Latest paper PnL
7. Latest risk warnings
8. Latest audit events
9. Broker read-only status
10. API revenue sandbox status
```

## Required Behavior

```text
1. Kill switch button must be visible on dashboard.
2. Live trading status must be impossible to miss.
3. Missing backend data should show "unavailable", not fake values.
4. Dashboard must not expose secrets.
5. Dashboard must not enable live trading directly in MVP.
```

## Tests

```bash
npm run lint
npm run typecheck
npm test
```

If frontend test tooling does not exist yet, add minimal test setup or document why it is deferred.

## Acceptance Criteria

```text
1. Owner can see system mode.
2. Owner can see live trading is disabled by default.
3. Owner can trigger kill switch API.
4. Owner can inspect strategies, backtests, paper trades, risk reports, audit logs.
5. UI displays safe fallback state if API unavailable.
```

## Rollback

Revert dashboard files.
