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
    assert result["paper_broker_adapter"]["adapter_id"] == "local_sandbox_paper_broker"
    assert result["paper_broker_adapter"]["live_order_submission_enabled"] is False
    assert result["broker_paper_order"]["status"] == "filled"
    assert result["broker_paper_order"]["mode"] == "paper"
    assert result["broker_paper_order"]["broker_order_id"].startswith("paper_")
    assert result["broker_paper_order"]["client_order_id"] == result["intent"]["idempotency_key"]
    assert result["broker_paper_order"]["ticket_id"] == result["approval_queue"]["ticket"]["ticket_id"]
    assert result["approval_queue"]["status"] == "queued"
    assert result["approval_queue"]["ticket"]["status"] == "pending_owner_approval"
    assert result["approval_queue"]["ticket"]["human_action_required"] is True
    assert result["approval_queue"]["ticket"]["expires_at"] == result["intent"]["expires_at"]
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


def test_paper_loop_persists_portfolio_across_loop_instances(tmp_path):
    policy = GovernorPolicy.load(Path("configs/trading_governor_policy.yaml"))
    state_path = tmp_path / "portfolio.json"
    queue_path = tmp_path / "queue.json"

    first_loop = PaperTradingLoop(
        policy=policy,
        price_path=Path("data/sample_prices.csv"),
        approval_queue=ApprovalQueue(queue_path),
        paper_state_path=state_path,
    )
    first = first_loop.run_once()

    second_loop = PaperTradingLoop(
        policy=policy,
        price_path=Path("data/sample_prices.csv"),
        approval_queue=ApprovalQueue(queue_path),
        paper_state_path=state_path,
    )
    second = second_loop.run_once()

    assert first["paper_portfolio"]["trade_count"] == 1
    assert second["paper_portfolio"]["trade_count"] == 2
    assert second["paper_portfolio"]["total_equity"] > 0
