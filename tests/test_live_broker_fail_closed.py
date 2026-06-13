from pathlib import Path
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent


def test_live_broker_rejects_by_default():
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    broker = FailClosedLiveBroker()
    intent = LiveOrderIntent(idempotency_key="abc", symbol="SPY", side="buy", quantity=1, notional_aud=10)
    result = broker.submit_order_intent(intent, policy, broker_health_ok=True)
    assert result["status"] == "rejected"
    assert result["status_zh"] == "已拒绝"
    assert "disabled" in result["reason"]
    assert result["reason_zh"] == "策略已禁用真实资金交易"
    assert result["message_zh"] == "真实资金下单被拒绝；Alpha 当前只允许模拟交易和人工确认工单。"
