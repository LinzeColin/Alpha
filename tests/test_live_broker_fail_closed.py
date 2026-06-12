from pathlib import Path
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent


def test_live_broker_rejects_by_default():
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    broker = FailClosedLiveBroker()
    intent = LiveOrderIntent(idempotency_key="abc", symbol="SPY", side="buy", quantity=1, notional_aud=10)
    result = broker.submit_order_intent(intent, policy, broker_health_ok=True)
    assert result["status"] == "rejected"
    assert "disabled" in result["reason"]
