from backend.app.services.soak_readiness import append_soak_readiness_history, summarize_soak_readiness_history


def _report(*, status: str = "healthy", warn_count: int = 0, fail_count: int = 0, ticket_id: str = "ticket_1") -> dict:
    return {
        "generated_at": f"2026-06-13T00:00:0{warn_count + fail_count}+00:00",
        "overall_status": status,
        "overall_status_zh": {"healthy": "可开始长运行", "degraded": "可观察运行", "unhealthy": "不可开始长运行"}[status],
        "status": "ready" if status == "healthy" else "not_ready",
        "status_zh": "已就绪" if status == "healthy" else "未完全就绪",
        "pass_count": 8 - warn_count - fail_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "check_count": 8,
        "summary_zh": "测试采样摘要",
        "paper_readiness": {"latest_fresh_ticket_id": ticket_id},
        "maintenance": {"status": "maintenance_sleeping", "status_zh": "等待下次维护", "run_count": 1, "backup_count": 1},
        "checks": [
            {"id": "safety_boundary", "status": "pass", "status_zh": "通过", "message_zh": "不会提交真实资金订单。"}
        ],
    }


def test_soak_history_records_consecutive_no_fail_samples(tmp_path):
    history_path = tmp_path / "runtime" / "soak_readiness_history.jsonl"

    append_soak_readiness_history(_report(status="healthy", ticket_id="ticket_a"), history_path=history_path)
    append_soak_readiness_history(
        _report(status="degraded", warn_count=1, ticket_id="ticket_b"),
        history_path=history_path,
    )
    summary = append_soak_readiness_history(
        _report(status="unhealthy", fail_count=1, ticket_id="ticket_c"),
        history_path=history_path,
    )["summary"]
    append_soak_readiness_history(_report(status="healthy", ticket_id="ticket_d"), history_path=history_path)
    final_summary = summarize_soak_readiness_history(history_path)

    assert summary["latest_fail_count"] == 1
    assert summary["consecutive_no_fail_count"] == 0
    assert final_summary["status_zh"] == "就绪"
    assert final_summary["run_count"] == 4
    assert final_summary["row_count"] == 4
    assert final_summary["consecutive_no_fail_count"] == 1
    assert final_summary["consecutive_healthy_count"] == 1
    assert final_summary["last_failure_at"] == "2026-06-13T00:00:01+00:00"
    assert final_summary["latest_fresh_ticket_id"] == "ticket_d"
    assert "连续 1 次采样无失败" in final_summary["summary_zh"]


def test_soak_history_empty_summary_is_chinese(tmp_path):
    summary = summarize_soak_readiness_history(tmp_path / "runtime" / "missing.jsonl")

    assert summary["status"] == "empty"
    assert summary["status_zh"] == "暂无记录"
    assert summary["consecutive_no_fail_count"] == 0
    assert summary["run_count"] == 0
    assert "尚无长运行采样历史" in summary["summary_zh"]
