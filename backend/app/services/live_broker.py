from __future__ import annotations

from dataclasses import dataclass
from .policy import GovernorPolicy, PolicyDecision


@dataclass
class LiveOrderIntent:
    idempotency_key: str
    symbol: str
    side: str
    quantity: float
    notional_aud: float


class FailClosedLiveBroker:
    """A broker adapter that never places real orders. Replace only after tests and policy gates pass."""

    def submit_order_intent(self, intent: LiveOrderIntent, policy: GovernorPolicy, *, kill_switch_active: bool = False, audit_sink_ok: bool = True, broker_health_ok: bool = False) -> dict:
        decision: PolicyDecision = policy.live_order_decision(
            notional_aud=intent.notional_aud,
            kill_switch_active=kill_switch_active,
            audit_sink_ok=audit_sink_ok,
            broker_health_ok=broker_health_ok,
            idempotency_key=intent.idempotency_key,
        )
        if not decision.allowed:
            return {"status": "rejected", "reason": decision.reason, "policy_version": decision.policy_version}
        return {"status": "rejected", "reason": "FailClosedLiveBroker never submits real orders", "policy_version": decision.policy_version}
