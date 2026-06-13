from __future__ import annotations

from pathlib import Path

from backend.app.services.soak_readiness import collect_soak_readiness, format_soak_readiness_summary_zh


def _paper_report(*, fresh_ticket: bool = True, live_order_submission_enabled: bool = False) -> dict:
    return {
        "overall_status": "healthy",
        "overall_status_zh": "就绪",
        "pass_count": 10,
        "warn_count": 0,
        "fail_count": 0,
        "checks": [
            {
                "id": "automatic_paper_loop",
                "title_zh": "全自动模拟交易循环",
                "status": "pass",
                "status_zh": "通过",
                "message_zh": "自动循环正在运行，刷新间隔不超过 300 秒。",
                "evidence": {"interval_seconds": 300, "run_count": 2},
            },
            {
                "id": "five_minute_freshness",
                "title_zh": "5 分钟及时性",
                "status": "pass",
                "status_zh": "通过",
                "message_zh": "当前存在有效候选单，且自动循环间隔不超过 300 秒。",
                "evidence": {"interval_seconds": 300, "ticket_id": "ticket_fresh"},
            },
        ],
        "queue_summary": {
            "fresh_pending_count": 1 if fresh_ticket else 0,
            "expired_pending_count": 0 if fresh_ticket else 1,
        },
        "latest_fresh_ticket_id": "ticket_fresh" if fresh_ticket else None,
        "safety_boundary": {"live_order_submission_enabled": live_order_submission_enabled},
    }


def _ops_report(*, warn_count: int = 0, fail_count: int = 0, live_order_submission_enabled: bool = False) -> dict:
    return {
        "overall_status": "healthy" if not warn_count and not fail_count else ("unhealthy" if fail_count else "degraded"),
        "overall_status_zh": "健康",
        "pass_count": 9 - warn_count - fail_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": [
            {
                "id": "runtime_backup",
                "title_zh": "运行状态备份",
                "status": "pass",
                "status_zh": "通过",
                "message_zh": "最近运行状态备份可用。",
            }
        ],
        "latest_backup": {"backup_path": "runtime/backups/alpha_state_001", "created_at": "2026-06-13T00:00:00+00:00"},
        "safety_boundary": {"live_order_submission_enabled": live_order_submission_enabled},
    }


def _maintenance_snapshot() -> dict:
    return {
        "status": "maintenance_sleeping",
        "status_zh": "等待下次维护",
        "task_running": True,
        "task_running_zh": "是",
        "interval_seconds": 300,
        "backup_interval_seconds": 86400,
        "run_count": 2,
        "backup_count": 1,
        "error_count": 0,
    }


def test_soak_readiness_passes_when_runtime_evidence_is_complete(tmp_path):
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()

    report = collect_soak_readiness(
        root=tmp_path,
        ops_health_report=_ops_report(),
        paper_readiness_report=_paper_report(),
        maintenance_snapshot=_maintenance_snapshot(),
        app_paths=[app_path],
    )
    summary = format_soak_readiness_summary_zh(report)

    assert report["overall_status"] == "healthy"
    assert report["overall_status_zh"] == "可开始长运行"
    assert report["pass_count"] == report["check_count"]
    assert report["fail_count"] == 0
    assert report["target_days"] == 30
    assert report["safety_boundary"]["live_order_submission_enabled"] is False
    assert "可开始 30 天本地长运行" in report["summary_zh"]
    assert "Alpha 长运行预检报告" in summary
    assert "不会提交真实资金订单" in summary


def test_soak_readiness_fails_without_fresh_broker_ticket(tmp_path):
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()

    report = collect_soak_readiness(
        root=tmp_path,
        ops_health_report=_ops_report(),
        paper_readiness_report=_paper_report(fresh_ticket=False),
        maintenance_snapshot=_maintenance_snapshot(),
        app_paths=[app_path],
    )
    checks = {item["id"]: item for item in report["checks"]}

    assert report["overall_status"] == "unhealthy"
    assert checks["fresh_broker_ticket"]["status"] == "fail"
    assert "不能开始 30 天本地长运行" in report["summary_zh"]


def test_soak_readiness_fails_closed_if_any_boundary_enables_live_orders(tmp_path):
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()

    report = collect_soak_readiness(
        root=tmp_path,
        ops_health_report=_ops_report(live_order_submission_enabled=True),
        paper_readiness_report=_paper_report(),
        maintenance_snapshot=_maintenance_snapshot(),
        app_paths=[app_path],
    )
    checks = {item["id"]: item for item in report["checks"]}

    assert report["overall_status"] == "unhealthy"
    assert checks["safety_boundary"]["status"] == "fail"
    assert checks["safety_boundary"]["message_zh"] == "运行路径出现真实下单能力，必须停止。"
