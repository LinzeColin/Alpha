from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.ops_health import collect_ops_health
from backend.app.services.paper_readiness import collect_paper_trading_readiness
from backend.app.services.runtime_status import read_persisted_runtime_snapshot


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REFRESH_INTERVAL_SECONDS = 300
DEFAULT_TARGET_DAYS = 30


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def collect_soak_readiness(
    *,
    root: str | Path = DEFAULT_ROOT,
    ops_health_report: dict | None = None,
    paper_readiness_report: dict | None = None,
    maintenance_snapshot: dict | None = None,
    maintenance_snapshot_path: str | Path | None = None,
    app_paths: list[str | Path] | None = None,
    target_days: int = DEFAULT_TARGET_DAYS,
) -> dict:
    root = Path(root)
    ops_report = ops_health_report if ops_health_report is not None else collect_ops_health(root=root)
    paper_report = (
        paper_readiness_report if paper_readiness_report is not None else collect_paper_trading_readiness(root=root)
    )
    maintenance_evidence = None
    maintenance = maintenance_snapshot
    if maintenance is None:
        maintenance, maintenance_evidence = read_persisted_runtime_snapshot(
            maintenance_snapshot_path or root / "runtime" / "ops_maintenance_status.json",
            expected_kind="ops_maintenance",
            max_age_seconds=DEFAULT_REFRESH_INTERVAL_SECONDS * 2,
        )
    maintenance = maintenance or {"persisted_runtime_evidence": maintenance_evidence}
    app_entries = [Path(path) for path in (app_paths or _default_app_paths(root))]

    checks = [
        _check_app_entries(app_entries),
        _check_paper_delivery(paper_report),
        _check_loop_and_freshness(paper_report),
        _check_fresh_ticket(paper_report),
        _check_ops_report(ops_report),
        _check_maintenance(maintenance),
        _check_recovery_backup(ops_report),
        _check_safety_boundaries(ops_report, paper_report),
    ]
    overall_status = _overall_status(checks)
    return {
        "status": "ready" if overall_status == "healthy" else "not_ready",
        "status_zh": _status_zh(overall_status),
        "overall_status": overall_status,
        "overall_status_zh": _status_zh(overall_status),
        "generated_at": utc_now_iso(),
        "target_days": target_days,
        "target_days_zh": f"{target_days} 天",
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": sum(1 for item in checks if item["status"] == "warn"),
        "fail_count": sum(1 for item in checks if item["status"] == "fail"),
        "checks": checks,
        "summary_zh": _summary_zh(checks, target_days=target_days),
        "paper_readiness": {
            "overall_status": paper_report.get("overall_status"),
            "overall_status_zh": paper_report.get("overall_status_zh"),
            "pass_count": paper_report.get("pass_count", 0),
            "warn_count": paper_report.get("warn_count", 0),
            "fail_count": paper_report.get("fail_count", 0),
            "latest_fresh_ticket_id": paper_report.get("latest_fresh_ticket_id"),
        },
        "ops_health": {
            "overall_status": ops_report.get("overall_status"),
            "overall_status_zh": ops_report.get("overall_status_zh"),
            "pass_count": ops_report.get("pass_count", 0),
            "warn_count": ops_report.get("warn_count", 0),
            "fail_count": ops_report.get("fail_count", 0),
        },
        "maintenance": {
            "status": maintenance.get("status"),
            "status_zh": maintenance.get("status_zh"),
            "task_running": maintenance.get("task_running"),
            "task_running_zh": maintenance.get("task_running_zh"),
            "run_count": maintenance.get("run_count", 0),
            "backup_count": maintenance.get("backup_count", 0),
            "interval_seconds": maintenance.get("interval_seconds"),
            "backup_interval_seconds": maintenance.get("backup_interval_seconds"),
            "error_count": maintenance.get("error_count", 0),
            "persisted_runtime_evidence": maintenance.get("persisted_runtime_evidence"),
        },
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "message_zh": "长运行预检只验证本地 App、模拟交易循环、审批队列、备份和安全边界；不会提交真实资金订单。",
        },
    }


def format_soak_readiness_summary_zh(report: dict) -> str:
    lines = [
        "Alpha 长运行预检报告",
        f"总体状态：{report.get('overall_status_zh', '未知')}",
        f"目标周期：{report.get('target_days_zh', '30 天')}",
        f"生成时间：{report.get('generated_at', '无')}",
        f"通过/关注/失败：{report.get('pass_count', 0)} / {report.get('warn_count', 0)} / {report.get('fail_count', 0)}",
        f"结论：{report.get('summary_zh', '无')}",
        "预检项：",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知预检')}：{check.get('status_zh', '未知')} - {check.get('message_zh', '')}")
    lines.append("安全边界：不会提交真实资金订单。")
    return "\n".join(lines)


def _check_app_entries(app_paths: list[Path]) -> dict:
    evidence = {
        "paths": [{"path": str(path), "exists": path.exists(), "is_app": path.suffix == ".app"} for path in app_paths]
    }
    bad_suffix = [item["path"] for item in evidence["paths"] if item["exists"] and not item["is_app"]]
    missing = [item["path"] for item in evidence["paths"] if not item["exists"]]
    if bad_suffix:
        evidence["bad_suffix_paths"] = bad_suffix
        return _check("app_entries", "本地 App 入口", "fail", "检测到非 .app 格式入口，不能作为标准 App 入口交付。", evidence)
    if missing:
        evidence["missing_paths"] = missing
        return _check("app_entries", "本地 App 入口", "warn", "部分 Downloads/Applications App 入口缺失。", evidence)
    return _check("app_entries", "本地 App 入口", "pass", "仓库、Downloads、用户 Applications 和系统 Applications 的 Alpha.app 均可见。", evidence)


def _check_paper_delivery(report: dict) -> dict:
    evidence = {
        "overall_status": report.get("overall_status"),
        "pass_count": report.get("pass_count", 0),
        "warn_count": report.get("warn_count", 0),
        "fail_count": report.get("fail_count", 0),
    }
    if int(report.get("fail_count") or 0) > 0:
        return _check("paper_delivery", "模拟交易交付就绪", "fail", "模拟交易交付就绪报告仍有失败项。", evidence)
    if int(report.get("warn_count") or 0) > 0:
        return _check("paper_delivery", "模拟交易交付就绪", "warn", "模拟交易交付就绪报告仍有关注项。", evidence)
    return _check("paper_delivery", "模拟交易交付就绪", "pass", "模拟交易交付就绪报告全部通过。", evidence)


def _check_loop_and_freshness(report: dict) -> dict:
    checks = _checks_by_id(report)
    loop_check = checks.get("automatic_paper_loop") or {}
    freshness_check = checks.get("five_minute_freshness") or {}
    evidence = {
        "automatic_paper_loop": loop_check.get("status"),
        "five_minute_freshness": freshness_check.get("status"),
        "loop_evidence": loop_check.get("evidence", {}),
        "freshness_evidence": freshness_check.get("evidence", {}),
    }
    statuses = {loop_check.get("status"), freshness_check.get("status")}
    if "fail" in statuses or not loop_check or not freshness_check:
        return _check("five_minute_loop", "5 分钟自动循环", "fail", "自动循环或 5 分钟时效检查未通过。", evidence)
    if "warn" in statuses:
        return _check("five_minute_loop", "5 分钟自动循环", "warn", "自动循环可用但仍有时效关注项。", evidence)
    return _check("five_minute_loop", "5 分钟自动循环", "pass", "自动循环和候选单时效均满足 300 秒要求。", evidence)


def _check_fresh_ticket(report: dict) -> dict:
    queue_summary = report.get("queue_summary") or {}
    evidence = {
        "latest_fresh_ticket_id": report.get("latest_fresh_ticket_id"),
        "fresh_pending_count": queue_summary.get("fresh_pending_count", 0),
        "expired_pending_count": queue_summary.get("expired_pending_count", 0),
    }
    if not report.get("latest_fresh_ticket_id") or int(queue_summary.get("fresh_pending_count") or 0) <= 0:
        return _check("fresh_broker_ticket", "有效经纪商就绪工单", "fail", "当前没有有效待人工确认经纪商就绪工单。", evidence)
    return _check("fresh_broker_ticket", "有效经纪商就绪工单", "pass", "当前存在有效待人工确认经纪商就绪工单。", evidence)


def _check_ops_report(report: dict) -> dict:
    evidence = {
        "overall_status": report.get("overall_status"),
        "pass_count": report.get("pass_count", 0),
        "warn_count": report.get("warn_count", 0),
        "fail_count": report.get("fail_count", 0),
    }
    if int(report.get("fail_count") or 0) > 0:
        return _check("ops_health", "运行健康", "fail", "运行健康检查存在失败项。", evidence)
    if int(report.get("warn_count") or 0) > 0:
        return _check("ops_health", "运行健康", "warn", "运行健康检查有关注项，允许进入观察型 soak，但不能声称 30 天已验证。", evidence)
    return _check("ops_health", "运行健康", "pass", "运行健康检查全部通过。", evidence)


def _check_maintenance(snapshot: dict) -> dict:
    evidence = {
        "status": snapshot.get("status"),
        "task_running": snapshot.get("task_running"),
        "run_count": snapshot.get("run_count", 0),
        "backup_count": snapshot.get("backup_count", 0),
        "interval_seconds": snapshot.get("interval_seconds"),
        "backup_interval_seconds": snapshot.get("backup_interval_seconds"),
        "error_count": snapshot.get("error_count", 0),
        "persisted_runtime_evidence": snapshot.get("persisted_runtime_evidence"),
    }
    if not snapshot:
        return _check("automatic_maintenance", "自动维护", "fail", "缺少自动维护快照，无法证明健康采样和备份任务已启动。", evidence)
    if snapshot.get("error_count"):
        return _check("automatic_maintenance", "自动维护", "fail", "自动维护存在错误。", evidence)
    if not snapshot.get("task_running"):
        return _check("automatic_maintenance", "自动维护", "fail", "自动维护任务未运行。", evidence)
    if int(snapshot.get("interval_seconds") or 0) <= 0 or int(snapshot.get("interval_seconds") or 0) > DEFAULT_REFRESH_INTERVAL_SECONDS:
        return _check("automatic_maintenance", "自动维护", "fail", "自动维护采样间隔超过 300 秒。", evidence)
    if int(snapshot.get("run_count") or 0) <= 0:
        return _check("automatic_maintenance", "自动维护", "warn", "自动维护已启动但尚未完成首轮采样。", evidence)
    return _check("automatic_maintenance", "自动维护", "pass", "自动维护正在运行，并已完成健康采样。", evidence)


def _check_recovery_backup(report: dict) -> dict:
    checks = _checks_by_id(report)
    backup_check = checks.get("runtime_backup") or {}
    evidence = {
        "runtime_backup_status": backup_check.get("status"),
        "latest_backup": report.get("latest_backup"),
    }
    if backup_check.get("status") == "fail":
        return _check("recovery_backup", "恢复备份", "fail", "运行备份检查失败。", evidence)
    if backup_check.get("status") != "pass":
        return _check("recovery_backup", "恢复备份", "warn", "最近运行备份不足，需要在 soak 前生成或等待自动备份。", evidence)
    return _check("recovery_backup", "恢复备份", "pass", "最近运行状态备份可用。", evidence)


def _check_safety_boundaries(ops_report: dict, paper_report: dict) -> dict:
    ops_boundary = ops_report.get("safety_boundary") or {}
    paper_boundary = paper_report.get("safety_boundary") or {}
    evidence = {
        "ops_live_order_submission_enabled": ops_boundary.get("live_order_submission_enabled"),
        "paper_live_order_submission_enabled": paper_boundary.get("live_order_submission_enabled"),
    }
    if ops_boundary.get("live_order_submission_enabled") or paper_boundary.get("live_order_submission_enabled"):
        return _check("safety_boundary", "真实下单边界", "fail", "运行路径出现真实下单能力，必须停止。", evidence)
    return _check("safety_boundary", "真实下单边界", "pass", "长运行预检保持模拟交易和人工工单边界，不提交真实资金订单。", evidence)


def _checks_by_id(report: dict) -> dict[str, dict]:
    return {str(item.get("id")): item for item in report.get("checks", [])}


def _check(check_id: str, title_zh: str, status: str, message_zh: str, evidence: dict | None = None) -> dict:
    return {
        "id": check_id,
        "title_zh": title_zh,
        "status": status,
        "status_zh": _check_status_zh(status),
        "message_zh": message_zh,
        "evidence": evidence or {},
    }


def _overall_status(checks: list[dict]) -> str:
    if any(item["status"] == "fail" for item in checks):
        return "unhealthy"
    if any(item["status"] == "warn" for item in checks):
        return "degraded"
    return "healthy"


def _status_zh(status: str) -> str:
    return {"healthy": "可开始长运行", "degraded": "可观察运行", "unhealthy": "不可开始长运行"}.get(status, "未知")


def _check_status_zh(status: object) -> str:
    return {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(str(status), "未知")


def _summary_zh(checks: list[dict], *, target_days: int) -> str:
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    if fail_count:
        return f"仍有 {fail_count} 个失败项，不能开始 {target_days} 天本地长运行。"
    if warn_count:
        return f"没有失败项，但仍有 {warn_count} 个关注项；可以观察运行，不能声称已完成 {target_days} 天验证。"
    return f"App 入口、自动模拟交易、5分钟候选单、运行健康、自动维护、备份和安全边界均通过，可开始 {target_days} 天本地长运行。"


def _default_app_paths(root: Path) -> list[Path]:
    return [
        root / "outputs" / "applications" / "Alpha.app",
        Path.home() / "Downloads" / "Alpha.app",
        Path.home() / "Applications" / "Alpha.app",
        Path("/Applications/Alpha.app"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="输出原始机器 JSON；默认输出中文长运行预检摘要")
    parser.add_argument("--api-url", help="从正在运行的 Alpha API 读取长运行预检，例如 http://127.0.0.1:8000/readiness/soak")
    args = parser.parse_args()
    report = _load_api_report(args.api_url) if args.api_url else collect_soak_readiness()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(format_soak_readiness_summary_zh(report))


def _load_api_report(api_url: str) -> dict:
    with urllib.request.urlopen(api_url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
