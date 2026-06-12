from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    status: str
    reason: str
    policy_version: Optional[str] = None


class GovernorPolicy:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.version = str(data.get("policy_version", "unknown"))

    @classmethod
    def load(cls, path: str | Path) -> "GovernorPolicy":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Policy file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Policy YAML must be a mapping")
        return cls(data)

    @classmethod
    def fail_closed(cls, reason: str) -> PolicyDecision:
        return PolicyDecision(False, "rejected", reason)

    def live_order_decision(self, *, notional_aud: float, kill_switch_active: bool, audit_sink_ok: bool, broker_health_ok: bool, idempotency_key: str | None) -> PolicyDecision:
        live = self.data.get("live_trading", {})
        limits = self.data.get("risk_limits", {})
        if not live.get("enabled", False):
            return PolicyDecision(False, "rejected", "live trading disabled by policy", self.version)
        env_name = live.get("environment_flag_name", "LIVE_TRADING_ENABLED")
        if live.get("require_environment_flag", True) and os.getenv(env_name, "false").lower() != "true":
            return PolicyDecision(False, "rejected", f"{env_name} is not true", self.version)
        if kill_switch_active:
            return PolicyDecision(False, "rejected", "kill switch active", self.version)
        if live.get("require_audit_sink", True) and not audit_sink_ok:
            return PolicyDecision(False, "rejected", "audit sink unavailable", self.version)
        if live.get("require_broker_health_check", True) and not broker_health_ok:
            return PolicyDecision(False, "rejected", "broker health check failed", self.version)
        if live.get("require_idempotency_key", True) and not idempotency_key:
            return PolicyDecision(False, "rejected", "missing idempotency key", self.version)
        max_notional = float(limits.get("max_order_value_aud", 0))
        if max_notional <= 0 or notional_aud > max_notional:
            return PolicyDecision(False, "rejected", "max order value exceeded", self.version)
        return PolicyDecision(True, "allowed", "policy checks passed", self.version)
