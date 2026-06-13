from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.ops_health import collect_ops_health, create_runtime_backup, format_ops_health_summary_zh, prune_runtime_backups
from backend.app.services.paper_broker import PaperBroker, PaperOrder


class FakeMarketDataGateway:
    def __init__(self, status: dict) -> None:
        self._status = status

    def resolve_price_path(self):
        return type("Snapshot", (), {"status": self._status})()


def _fresh_ticket(now: datetime) -> dict:
    return {
        "ticket_id": "ticket_fresh",
        "status": "pending_owner_approval",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=300)).isoformat(),
        "intent": {"expires_at": (now + timedelta(seconds=300)).isoformat()},
        "broker_payload": {"symbol": "SPY"},
        "risk_check": {"status": "approved_for_owner_review"},
    }


def _healthy_loop_snapshot(now: datetime) -> dict:
    return {
        "enabled": True,
        "status": "sleeping",
        "task_running": True,
        "interval_seconds": 300,
        "run_count": 3,
        "error_count": 0,
        "last_run_completed_at": (now - timedelta(seconds=60)).isoformat(),
    }


def _market_data_status(tmp_path: Path) -> dict:
    return {
        "provider": "cache_or_fixture",
        "source_kind": "fixture",
        "data_quality": "sample",
        "real_market_data": False,
        "price_path": str(tmp_path / "sample_prices.csv"),
        "row_count": 9,
        "latest_date": "2024-02-09",
        "latest_prices": {"SPY": 500.0},
    }


def test_collect_ops_health_reports_e_safe_runtime_checks(tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    queue_path = tmp_path / "runtime" / "approval_queue.sqlite3"
    paper_state_path = tmp_path / "runtime" / "paper_portfolio.json"
    log_path = tmp_path / "runtime" / "alpha_dashboard.log"
    pid_path = tmp_path / "runtime" / "alpha_dashboard.pid"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("INFO: Alpha dashboard ready\n", encoding="utf-8")
    pid_path.write_text(str(99999999), encoding="utf-8")

    ApprovalQueue(queue_path).enqueue(_fresh_ticket(now))
    broker = PaperBroker()
    broker.submit_order(PaperOrder(idempotency_key="paper_1", symbol="SPY", side="buy", quantity=1, price=100))
    broker.save(paper_state_path)

    health = collect_ops_health(
        root=tmp_path,
        queue_path=queue_path,
        paper_state_path=paper_state_path,
        pid_path=pid_path,
        log_path=log_path,
        market_data_gateway=FakeMarketDataGateway(_market_data_status(tmp_path)),
        loop_snapshot=_healthy_loop_snapshot(now),
    )

    checks = {item["id"]: item for item in health["checks"]}
    assert checks["agent_loop"]["status"] == "pass"
    assert checks["approval_queue"]["status"] == "pass"
    assert checks["paper_portfolio"]["status"] == "pass"
    assert checks["live_order_boundary"]["status"] == "pass"
    assert checks["market_data"]["status"] == "warn"
    assert checks["dashboard_process"]["status"] == "warn"
    assert health["overall_status"] == "degraded"

    summary = format_ops_health_summary_zh(health)
    assert "Alpha 运行健康检查" in summary
    assert "自动模拟交易循环：通过" in summary
    assert "安全边界：不会提交真实资金订单。" in summary


def test_create_runtime_backup_copies_durable_state(tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    runtime = tmp_path / "runtime"
    queue_path = runtime / "approval_queue.sqlite3"
    paper_state_path = runtime / "paper_portfolio.json"
    market_data_cache_path = runtime / "market_data" / "latest_prices.csv"
    log_path = runtime / "alpha_dashboard.log"
    pid_path = runtime / "alpha_dashboard.pid"

    ApprovalQueue(queue_path).enqueue(_fresh_ticket(now))
    broker = PaperBroker()
    broker.submit_order(PaperOrder(idempotency_key="paper_1", symbol="SPY", side="buy", quantity=1, price=100))
    broker.save(paper_state_path)
    market_data_cache_path.parent.mkdir(parents=True, exist_ok=True)
    market_data_cache_path.write_text("date,symbol,close\n2024-02-09,SPY,500\n", encoding="utf-8")
    log_path.write_text("INFO: ready\n", encoding="utf-8")
    pid_path.write_text("12345", encoding="utf-8")

    backup = create_runtime_backup(
        root=tmp_path,
        queue_path=queue_path,
        paper_state_path=paper_state_path,
        market_data_cache_path=market_data_cache_path,
        pid_path=pid_path,
        log_path=log_path,
    )

    backup_dir = Path(backup["backup_path"])
    manifest = json.loads(Path(backup["manifest_path"]).read_text(encoding="utf-8"))

    assert backup_dir.exists()
    assert (backup_dir / "approval_queue.sqlite3").exists()
    assert (backup_dir / "paper_portfolio.json").exists()
    assert (backup_dir / "latest_prices.csv").exists()
    assert (backup_dir / "alpha_dashboard.log.tail").exists()
    assert ApprovalQueue(backup_dir / "approval_queue.sqlite3").summary()["total_count"] == 1
    assert manifest["live_order_submission_enabled"] is False
    assert manifest["missing_files"] == []


def test_prune_runtime_backups_keeps_latest_count(tmp_path):
    backup_root = tmp_path / "runtime" / "backups"
    for _ in range(4):
        create_runtime_backup(root=tmp_path, output_dir=backup_root)

    result = prune_runtime_backups(backup_root=backup_root, max_backup_count=2)
    remaining = list(backup_root.glob("alpha_state_*"))

    assert result["status"] == "pruned"
    assert result["deleted_count"] == 2
    assert len(remaining) == 2
