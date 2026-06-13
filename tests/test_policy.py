from pathlib import Path
from backend.app.services.policy import GovernorPolicy


def test_live_disabled_rejects():
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    decision = policy.live_order_decision(notional_aud=10, kill_switch_active=False, audit_sink_ok=True, broker_health_ok=True, idempotency_key="k")
    assert not decision.allowed
    assert "disabled" in decision.reason


def test_missing_policy_fails_by_exception():
    try:
        GovernorPolicy.load("/tmp/does-not-exist.yaml")
    except FileNotFoundError:
        assert True
    else:
        raise AssertionError("missing policy should fail")
