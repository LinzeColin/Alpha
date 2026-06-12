# Task Pack 01 — Policy and Audit Core

## Goal

Implement fail-closed policy evaluation and immutable audit logging before any trading logic exists.

## Scope

Create a policy engine that loads `packages/policies/risk_policy.yaml` and returns explicit allow/reject decisions.

Create audit event models and logging service.

## Files to Inspect

```text
packages/policies/risk_policy.yaml
apps/api/app/core/config.py
apps/api/app/main.py
```

## Files to Create / Modify

```text
apps/api/app/core/policy_engine.py
apps/api/app/core/audit_logger.py
apps/api/app/models/audit_event.py
apps/api/app/schemas/policy.py
apps/api/app/routes/policy.py
apps/api/app/routes/audit.py
tests/unit/test_policy_engine.py
tests/unit/test_audit_logger.py
```

## Policy Decision Model

Use structured output similar to:

```python
class PolicyDecision(BaseModel):
    allowed: bool
    decision: Literal["allow", "reject", "require_approval"]
    reason: str
    triggered_rules: list[str]
    fail_closed: bool = True
```

## Required Behavior

```text
1. Missing policy file -> reject.
2. Invalid YAML -> reject.
3. Unknown action type -> reject.
4. live_order action while live_trading.enabled=false -> reject.
5. prohibited asset/action -> reject.
6. Any exception in policy evaluation -> reject.
```

## AuditEvent Fields

```text
id
created_at
actor_type
actor_id
event_type
entity_type
entity_id
payload
policy_decision
```

## API Endpoints

```text
GET /policy/status
POST /policy/evaluate
GET /audit/events
```

## Tests

```bash
pytest tests/unit/test_policy_engine.py
pytest tests/unit/test_audit_logger.py
```

## Acceptance Criteria

```text
1. Policy engine fail-closes.
2. live_order is rejected by default.
3. crypto_live is rejected by default.
4. leverage/short/options/margin are rejected.
5. Audit logger can persist or mock-persist structured events.
6. Every policy evaluation can be audit logged.
```

## Out of Scope

```text
- Broker integration
- Strategy generation
- Backtesting
- Agents
- Live trading
```

## Rollback

Revert files above.
