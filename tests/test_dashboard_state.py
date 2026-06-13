from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.api import routes
from backend.app.services.approval_queue import ApprovalQueue


def test_dashboard_state_exposes_agent_portfolio_strategy_and_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.json")
    monkeypatch.setattr(routes, "PAPER_STATE_PATH", tmp_path / "paper_portfolio.json")
    monkeypatch.setattr(routes, "DATA_PATH", Path("data/sample_prices.csv"))

    run_result = routes.paper_run_once()
    state = routes.dashboard_state()

    assert run_result["status"] == "completed"
    assert state["health"]["refresh_interval_seconds"] == 300
    assert state["agent_status"]["status"] == "ready"
    assert state["paper_portfolio"]["trade_count"] == 1
    assert state["strategy_tournament"]["candidate_count"] > 0
    assert state["strategy_tournament"]["validation_summary"]["validated_count"] > 0
    assert "hit_rate" in state["strategy_tournament"]["winner"]
    assert state["approval_queue"]["count"] == 1


def test_agent_status_reports_app_runtime_loop_state(tmp_path, monkeypatch):
    loop_state = {
        "enabled": True,
        "status": "sleeping",
        "task_running": True,
        "interval_seconds": 300,
        "run_count": 1,
        "error_count": 0,
    }
    monkeypatch.setattr(routes.AUTO_PAPER_AGENT, "snapshot", lambda: loop_state)
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.json")

    status = routes.agent_status()

    assert status["loop"] == loop_state
    assert status["loop"]["task_running"] is True
    assert status["pending_tickets"] == 0


def test_owner_summary_counts_only_fresh_pending_tickets(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    queue_path = tmp_path / "approval_queue.json"
    queue = ApprovalQueue(queue_path)
    queue.enqueue(
        {
            "ticket_id": "ticket_expired",
            "status": "pending_owner_approval",
            "created_at": now.isoformat(),
            "intent": {"expires_at": (now - timedelta(seconds=1)).isoformat()},
            "broker_payload": {},
            "risk_check": {},
        }
    )
    monkeypatch.setattr(routes, "QUEUE_PATH", queue_path)

    summary = routes.owner_summary()
    api_queue = routes.approval_queue()

    assert summary["pending_order_tickets"] == 0
    assert summary["expired_order_tickets"] == 1
    assert api_queue["count"] == 0
    assert api_queue["summary"]["total_count"] == 1
    assert api_queue["summary"]["expired_pending_count"] == 1
