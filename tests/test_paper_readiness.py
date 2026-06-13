from pathlib import Path

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.paper_readiness import (
    collect_paper_trading_readiness,
    format_paper_trading_readiness_summary_zh,
)
from backend.app.services.paper_trading_loop import PaperTradingLoop
from backend.app.services.policy import GovernorPolicy


def test_paper_readiness_fails_closed_without_loop_snapshot(tmp_path):
    report = collect_paper_trading_readiness(
        root=tmp_path,
        queue_path=tmp_path / "approval_queue.sqlite3",
        paper_state_path=tmp_path / "paper_portfolio.json",
        strategy_history_path=tmp_path / "strategy_history.jsonl",
        performance_history_path=tmp_path / "performance_history.jsonl",
        app_paths=[tmp_path / "Alpha.app"],
    )

    assert report["status"] == "not_ready"
    assert report["overall_status"] == "unhealthy"
    assert report["fail_count"] >= 1
    assert report["safety_boundary"]["live_order_submission_enabled"] is False
    assert any(item["id"] == "automatic_paper_loop" and item["status"] == "fail" for item in report["checks"])


def test_paper_readiness_passes_with_paper_cycle_loop_snapshot_and_app_entry(tmp_path):
    queue_path = tmp_path / "approval_queue.sqlite3"
    paper_state_path = tmp_path / "paper_portfolio.json"
    strategy_history_path = tmp_path / "strategy_history.jsonl"
    performance_history_path = tmp_path / "performance_history.jsonl"
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()
    loop_snapshot = {
        "enabled": True,
        "task_running": True,
        "interval_seconds": 300,
        "run_count": 1,
        "status": "sleeping",
    }
    loop = PaperTradingLoop(
        policy=GovernorPolicy.load(Path("configs/trading_governor_policy.yaml")),
        price_path=Path("data/sample_prices.csv"),
        approval_queue=ApprovalQueue(queue_path),
        paper_state_path=paper_state_path,
        strategy_history_path=strategy_history_path,
        performance_history_path=performance_history_path,
    )

    loop.run_once()
    report = collect_paper_trading_readiness(
        root=tmp_path,
        queue_path=queue_path,
        paper_state_path=paper_state_path,
        strategy_history_path=strategy_history_path,
        performance_history_path=performance_history_path,
        loop_snapshot=loop_snapshot,
        app_paths=[app_path],
    )
    summary = format_paper_trading_readiness_summary_zh(report)

    assert report["status"] == "ready"
    assert report["overall_status_zh"] == "就绪"
    assert report["pass_count"] == report["check_count"]
    assert report["fail_count"] == 0
    assert report["latest_fresh_ticket_id"]
    assert "自动模拟交易、候选订单、风控、审批队列、工单、5分钟时效和本地 App 入口均通过就绪检查。" in report["summary_zh"]
    assert "不会提交真实资金订单" in summary
