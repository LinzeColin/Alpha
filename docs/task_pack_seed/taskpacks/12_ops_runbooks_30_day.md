# Task Pack 12 — Ops Runbooks and 30-Day Execution System

## Goal

Create operational runbooks for daily execution, failure handling, live readiness, and Codex development cadence.

## Files to Create / Modify

```text
runbooks/daily_ops.md
runbooks/e_safe_live_readiness.md
runbooks/kill_switch.md
runbooks/reconciliation.md
runbooks/codex_dev_cadence.md
runbooks/incident_response.md
runbooks/tax_audit_exports.md
```

## Required Runbooks

### daily_ops.md

Must include:

```text
- morning system check
- paper trading check
- risk warning check
- audit anomaly check
- live status check
- daily summary review
```

### e_safe_live_readiness.md

Must include the complete E-Safe checklist.

### kill_switch.md

Must include:

```text
- how to trigger kill switch
- what it blocks
- how to verify it is active
- how to safely reset
```

### reconciliation.md

Must include:

```text
- paper portfolio reconciliation
- broker read-only reconciliation
- mismatch response
- pause rules
```

### codex_dev_cadence.md

Must include:

```text
- one task pack at a time
- plan-first
- listed files only
- tests required
- diff summary
- rollback plan
```

### incident_response.md

Must include:

```text
- broker API error
- duplicate order
- unexpected position
- missing market data
- policy engine failure
- high drawdown
- failed payment sandbox
```

### tax_audit_exports.md

Must include:

```text
- order journal
- fills
- fees
- PnL
- strategy attribution
- audit event export
```

## Acceptance Criteria

```text
1. Runbooks are clear enough to operate the system without extra explanation.
2. E-Safe checklist matches code policy.
3. Incident response defaults to pause/fail-closed.
4. Codex cadence prevents uncontrolled broad changes.
```

## Rollback

Revert runbook files.
