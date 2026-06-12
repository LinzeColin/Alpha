from pathlib import Path

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, PaperTradingLoop
from backend.app.services.policy import GovernorPolicy


def test_paper_loop_generates_ticket_and_fills_paper_order(tmp_path):
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    queue = ApprovalQueue(tmp_path / "queue.json")
    state_path = tmp_path / "portfolio.json"
    loop = PaperTradingLoop(policy=policy, price_path=Path("data/sample_prices.csv"), approval_queue=queue, paper_state_path=state_path)

    result = loop.run_once()

    assert result["refresh_interval_seconds"] == DEFAULT_REFRESH_INTERVAL_SECONDS
    assert result["risk_check"]["allowed"] is True
    assert result["paper_order"]["status"] == "filled"
    assert result["approval_queue"]["status"] == "queued"
    assert result["approval_queue"]["ticket"]["status"] == "pending_owner_approval"
    assert result["approval_queue"]["ticket"]["human_action_required"] is True
    assert result["approval_queue"]["ticket"]["broker_payload"]["client_order_id"] == result["intent"]["idempotency_key"]
    assert any(candidate["strategy_id"] == result["intent"]["strategy_id"] for candidate in result["strategy_tournament"]["candidates"])
    assert result["paper_portfolio"]["trade_count"] == 1
    assert state_path.exists()
    assert len(queue.list_tickets()) == 1


def test_paper_loop_uses_five_minute_default_refresh():
    assert DEFAULT_REFRESH_INTERVAL_SECONDS == 300


def test_order_intent_strategy_matches_tradable_symbol_under_notional_limit(tmp_path):
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    loop = PaperTradingLoop(
        policy=policy,
        price_path=Path("data/sample_prices.csv"),
        approval_queue=ApprovalQueue(tmp_path / "queue.json"),
        paper_state_path=tmp_path / "portfolio.json",
    )

    result = loop.run_once()

    assert result["intent"]["symbol"] in result["intent"]["strategy_id"]
    assert result["intent"]["estimated_notional_aud"] <= policy.data["risk_limits"]["max_order_value_aud"]
