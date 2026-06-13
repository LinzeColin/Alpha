from pathlib import Path

from backend.app.api import routes


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
