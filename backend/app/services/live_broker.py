from __future__ import annotations

from dataclasses import dataclass
from .display_locale import zh_reason, zh_status
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
            return _localized_rejection(decision.reason, decision.policy_version)
        return _localized_rejection("FailClosedLiveBroker never submits real orders", decision.policy_version)


def _localized_rejection(reason: str, policy_version: str | None) -> dict:
    return {
        "status": "rejected",
        "status_zh": zh_status("rejected"),
        "reason": reason,
        "reason_zh": zh_reason(reason),
        "policy_version": policy_version,
        "message_zh": "真实资金下单被拒绝；Alpha 当前只允许模拟交易和人工确认工单。",
    }
