from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_TARGET_DAYS = 30
DEFAULT_MAX_SOAK_HISTORY_ROWS = 10_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def append_soak_readiness_history(
    report: dict,
    *,
    history_path: str | Path,
    max_rows: int = DEFAULT_MAX_SOAK_HISTORY_ROWS,
    target_days: int = DEFAULT_TARGET_DAYS,
) -> dict:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = _history_record(report)
    rows = _read_jsonl(path)
    rows.append(record)
    if max_rows > 0:
        rows = rows[-max_rows:]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "status_zh": "已写入",
        "path": str(path),
        "row_count": len(rows),
        "run_count": len(rows),
        "latest_record": record,
        "summary": summarize_soak_readiness_history(path, target_days=target_days),
    }


def summarize_soak_readiness_history(
    history_path: str | Path,
    *,
    limit: int = 20,
    target_days: int = DEFAULT_TARGET_DAYS,
) -> dict:
    path = Path(history_path)
    rows = _read_jsonl(path)
    recent = rows[-limit:] if limit > 0 else rows
    latest = rows[-1] if rows else {}
    first_at = _parse_iso(rows[0].get("generated_at")) if rows else None
    latest_at = _parse_iso(latest.get("generated_at")) if latest else None
    observed_span_seconds = max(0, int((latest_at - first_at).total_seconds())) if first_at and latest_at else 0
    target_seconds = max(1, int(target_days) * 86_400)
    consecutive_no_fail = _consecutive_count(rows, lambda row: int(row.get("fail_count") or 0) == 0)
    consecutive_healthy = _consecutive_count(rows, lambda row: row.get("overall_status") == "healthy")
    latest_fail_count = int(latest.get("fail_count") or 0) if latest else 0
    latest_warn_count = int(latest.get("warn_count") or 0) if latest else 0
    last_failure = next((row for row in reversed(rows) if int(row.get("fail_count") or 0) > 0), {})
    last_no_fail = next((row for row in reversed(rows) if int(row.get("fail_count") or 0) == 0), {})
    completion_status = _history_completion_status(
        rows=rows,
        observed_span_seconds=observed_span_seconds,
        target_seconds=target_seconds,
        consecutive_no_fail=consecutive_no_fail,
        latest_fail_count=latest_fail_count,
    )
    return {
        "status": "ready" if rows else "empty",
        "status_zh": "就绪" if rows else "暂无记录",
        "path": str(path),
        "exists": path.exists(),
        "target_days": target_days,
        "target_days_zh": f"{target_days} 天",
        "row_count": len(rows),
        "run_count": len(rows),
        "recent_count": len(recent),
        "latest_record": latest if rows else None,
        "latest_generated_at": latest.get("generated_at"),
        "first_generated_at": rows[0].get("generated_at") if rows else None,
        "latest_sample_at": latest.get("generated_at"),
        "first_sample_at": rows[0].get("generated_at") if rows else None,
        "last_failure_at": last_failure.get("generated_at"),
        "last_no_fail_at": last_no_fail.get("generated_at"),
        "latest_overall_status": latest.get("overall_status"),
        "latest_overall_status_zh": latest.get("overall_status_zh"),
        "latest_pass_count": latest.get("pass_count", 0),
        "latest_warn_count": latest_warn_count,
        "latest_fail_count": latest_fail_count,
        "latest_fresh_ticket_id": latest.get("latest_fresh_ticket_id"),
        "latest_maintenance_run_count": latest.get("maintenance_run_count", 0),
        "latest_ops_health_status_zh": latest.get("ops_health_status_zh"),
        "latest_paper_status_zh": latest.get("paper_readiness_status_zh"),
        "no_fail_sample_count": sum(1 for row in rows if int(row.get("fail_count") or 0) == 0),
        "failed_sample_count": sum(1 for row in rows if int(row.get("fail_count") or 0) > 0),
        "healthy_sample_count": sum(1 for row in rows if row.get("overall_status") == "healthy"),
        "degraded_sample_count": sum(1 for row in rows if row.get("overall_status") == "degraded"),
        "consecutive_no_fail_count": consecutive_no_fail,
        "consecutive_healthy_count": consecutive_healthy,
        "observed_span_seconds": observed_span_seconds,
        "observed_seconds": observed_span_seconds,
        "observed_days": round(observed_span_seconds / 86_400, 6),
        "observed_days_zh": f"{observed_span_seconds / 86_400:.2f} 天",
        "target_coverage_ratio": round(min(1.0, observed_span_seconds / target_seconds), 6),
        "target_coverage": round(min(1.0, observed_span_seconds / target_seconds), 6),
        "target_coverage_zh": f"{min(1.0, observed_span_seconds / target_seconds) * 100:.2f}%",
        "completion_status": completion_status,
        "completion_status_zh": _completion_status_zh(completion_status),
        "summary_zh": _history_summary_zh(
            run_count=len(rows),
            consecutive_no_fail=consecutive_no_fail,
            latest_fail_count=latest_fail_count,
            latest_warn_count=latest_warn_count,
            observed_span_seconds=observed_span_seconds,
            target_days=target_days,
            completion_status=completion_status,
        ),
        "recent": recent,
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "message_zh": "长运行历史只记录本地模拟交易和预检状态，不提交真实资金订单。",
        },
    }


def _history_record(report: dict) -> dict:
    paper = report.get("paper_readiness") or {}
    ops = report.get("ops_health") or {}
    maintenance = report.get("maintenance") or {}
    return {
        "generated_at": report.get("generated_at") or utc_now_iso(),
        "overall_status": report.get("overall_status"),
        "overall_status_zh": report.get("overall_status_zh"),
        "pass_count": int(report.get("pass_count") or 0),
        "warn_count": int(report.get("warn_count") or 0),
        "fail_count": int(report.get("fail_count") or 0),
        "summary_zh": report.get("summary_zh"),
        "target_days": int(report.get("target_days") or DEFAULT_TARGET_DAYS),
        "latest_fresh_ticket_id": paper.get("latest_fresh_ticket_id"),
        "paper_readiness_status": paper.get("overall_status"),
        "paper_readiness_status_zh": paper.get("overall_status_zh"),
        "paper_fail_count": int(paper.get("fail_count") or 0),
        "ops_health_status": ops.get("overall_status"),
        "ops_health_status_zh": ops.get("overall_status_zh"),
        "ops_health_fail_count": int(ops.get("fail_count") or 0),
        "ops_health_warn_count": int(ops.get("warn_count") or 0),
        "maintenance_status": maintenance.get("status"),
        "maintenance_status_zh": maintenance.get("status_zh"),
        "maintenance_run_count": int(maintenance.get("run_count") or 0),
        "maintenance_error_count": int(maintenance.get("error_count") or 0),
        "live_order_submission_enabled": bool((report.get("safety_boundary") or {}).get("live_order_submission_enabled")),
        "checks": {
            check.get("id", "unknown"): check.get("status", "unknown")
            for check in report.get("checks", [])
        },
    }


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _consecutive_count(rows: list[dict], predicate: Callable[[dict], bool]) -> int:
    count = 0
    for row in reversed(rows):
        if not predicate(row):
            break
        count += 1
    return count


def _history_completion_status(
    *,
    rows: list[dict],
    observed_span_seconds: int,
    target_seconds: int,
    consecutive_no_fail: int,
    latest_fail_count: int,
) -> str:
    if not rows:
        return "not_started"
    if latest_fail_count > 0:
        return "latest_failed"
    if observed_span_seconds >= target_seconds and consecutive_no_fail == len(rows):
        return "completed_no_fail_observation"
    return "observing"


def _completion_status_zh(status: str) -> str:
    return {
        "not_started": "尚未开始",
        "latest_failed": "最近采样失败",
        "observing": "观察运行中",
        "completed_no_fail_observation": "已完成无失败观察",
    }.get(status, "未知")


def _history_summary_zh(
    *,
    run_count: int,
    consecutive_no_fail: int,
    latest_fail_count: int,
    latest_warn_count: int,
    observed_span_seconds: int,
    target_days: int,
    completion_status: str,
) -> str:
    if run_count <= 0:
        return "尚无长运行采样历史。"
    observed_days = observed_span_seconds / 86_400
    if latest_fail_count > 0:
        return f"最近长运行采样仍有 {latest_fail_count} 个失败项，连续无失败采样已中断。"
    if completion_status == "completed_no_fail_observation":
        return f"已完成 {target_days} 天无失败观察，连续无失败采样 {consecutive_no_fail} 次。"
    if latest_warn_count > 0:
        return f"连续 {consecutive_no_fail} 次采样无失败，已覆盖 {observed_days:.2f} 天；最近仍有 {latest_warn_count} 个关注项，继续观察。"
    return f"连续 {consecutive_no_fail} 次采样无失败，已覆盖 {observed_days:.2f} 天，继续累计至 {target_days} 天。"
