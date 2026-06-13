import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.paper_readiness import (
    collect_paper_trading_readiness,
    format_paper_trading_readiness_summary_zh,
)
from backend.app.services.paper_trading_loop import PaperTradingLoop
from backend.app.services.policy import GovernorPolicy
from backend.app.services.runtime_status import atomic_write_runtime_snapshot, utc_now_iso


def _loop_snapshot(*, interval_seconds: int = 300, run_count: int = 1, scheduled_delay_seconds: int = 300) -> dict:
    completed_at = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "enabled": True,
        "task_running": True,
        "interval_seconds": interval_seconds,
        "run_count": run_count,
        "status": "sleeping",
        "last_run_completed_at": completed_at.isoformat(),
        "next_run_at": (completed_at + timedelta(seconds=scheduled_delay_seconds)).isoformat(),
    }


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
    loop_snapshot = _loop_snapshot()
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
    assert report["deadline"] == "2026-06-15"
    assert report["dashboard_app_deadline"] == "2026-06-17"
    assert report["pass_count"] == report["check_count"]
    assert report["fail_count"] == 0
    assert report["latest_fresh_ticket_id"]
    assert "自动模拟交易、候选订单、风控、审批队列、工单、5分钟时效和本地 App 入口均通过就绪检查。" in report["summary_zh"]
    check_titles = {item["id"]: item["title_zh"] for item in report["checks"]}
    assert check_titles["broker_ready_ticket"] == "经纪商就绪工单"
    assert "Broker-ready" not in summary
    assert "broker-ready" not in summary
    assert "不会提交真实资金订单" in summary


def test_paper_readiness_can_use_fresh_persisted_loop_heartbeat(tmp_path):
    queue_path = tmp_path / "approval_queue.sqlite3"
    paper_state_path = tmp_path / "paper_portfolio.json"
    strategy_history_path = tmp_path / "strategy_history.jsonl"
    performance_history_path = tmp_path / "performance_history.jsonl"
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()
    loop_status_path = tmp_path / "runtime" / "agent_loop_status.json"
    atomic_write_runtime_snapshot(
        loop_status_path,
        _loop_snapshot(),
        snapshot_kind="agent_loop",
    )
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
        loop_snapshot_path=loop_status_path,
        app_paths=[app_path],
    )

    loop_check = {item["id"]: item for item in report["checks"]}["automatic_paper_loop"]
    assert report["overall_status"] == "healthy"
    assert loop_check["status"] == "pass"
    assert loop_check["evidence"]["persisted_runtime_evidence"]["valid"] is True
    assert loop_check["evidence"]["persisted_runtime_evidence"]["process_id"] == os.getpid()


def test_paper_readiness_rejects_dead_persisted_loop_heartbeat(tmp_path):
    queue_path = tmp_path / "approval_queue.sqlite3"
    paper_state_path = tmp_path / "paper_portfolio.json"
    strategy_history_path = tmp_path / "strategy_history.jsonl"
    performance_history_path = tmp_path / "performance_history.jsonl"
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()
    loop_status_path = tmp_path / "runtime" / "agent_loop_status.json"
    loop_status_path.parent.mkdir(parents=True)
    loop_status_path.write_text(
        json.dumps(
            {
                "snapshot_kind": "agent_loop",
                "persisted_at": utc_now_iso(),
                "process_id": -1,
                **_loop_snapshot(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
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
        loop_snapshot_path=loop_status_path,
        app_paths=[app_path],
    )

    loop_check = {item["id"]: item for item in report["checks"]}["automatic_paper_loop"]
    assert report["overall_status"] == "unhealthy"
    assert loop_check["status"] == "fail"
    assert loop_check["evidence"]["persisted_runtime_evidence"]["reason"] == "process_not_alive"


def test_paper_readiness_rejects_loop_with_wrong_next_run_schedule(tmp_path):
    queue_path = tmp_path / "approval_queue.sqlite3"
    paper_state_path = tmp_path / "paper_portfolio.json"
    strategy_history_path = tmp_path / "strategy_history.jsonl"
    performance_history_path = tmp_path / "performance_history.jsonl"
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()
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
        loop_snapshot=_loop_snapshot(scheduled_delay_seconds=600),
        app_paths=[app_path],
    )

    loop_check = {item["id"]: item for item in report["checks"]}["automatic_paper_loop"]
    assert report["overall_status"] == "unhealthy"
    assert loop_check["status"] == "fail"
    assert loop_check["evidence"]["scheduled_delay_seconds"] == 600
    assert "300 秒刷新契约" in loop_check["message_zh"]
