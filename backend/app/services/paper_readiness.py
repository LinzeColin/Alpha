from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.paper_performance import summarize_paper_performance_history
from backend.app.services.strategy_journal import summarize_strategy_tournament_history


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REFRESH_INTERVAL_SECONDS = 300
PAPER_DELIVERY_DEADLINE = "2026-06-15"
PAPER_DELIVERY_DEADLINE_ZH = "2026年6月15日"
DASHBOARD_APP_DEADLINE = "2026-06-17"
DASHBOARD_APP_DEADLINE_ZH = "2026年6月17日"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def collect_paper_trading_readiness(
    *,
    root: str | Path = DEFAULT_ROOT,
    queue_path: str | Path | None = None,
    paper_state_path: str | Path | None = None,
    strategy_history_path: str | Path | None = None,
    performance_history_path: str | Path | None = None,
    loop_snapshot: dict | None = None,
    app_paths: list[str | Path] | None = None,
    max_refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
) -> dict:
    root = Path(root)
    queue_path = Path(queue_path) if queue_path else root / "runtime" / "approval_queue.sqlite3"
    paper_state_path = Path(paper_state_path) if paper_state_path else root / "runtime" / "paper_portfolio.json"
    strategy_history_path = (
        Path(strategy_history_path) if strategy_history_path else root / "runtime" / "strategy_tournament_history.jsonl"
    )
    performance_history_path = (
        Path(performance_history_path) if performance_history_path else root / "runtime" / "paper_performance_history.jsonl"
    )
    app_paths = [Path(path) for path in (app_paths or _default_app_paths(root))]

    queue = ApprovalQueue(queue_path)
    queue_summary = queue.summary()
    latest_tickets = queue.latest_with_freshness(limit=20)
    latest_ticket = latest_tickets[-1] if latest_tickets else {}
    latest_fresh_ticket = next(
        (ticket for ticket in reversed(latest_tickets) if ticket.get("actionability") == "fresh_pending_owner_approval"),
        None,
    )
    paper_broker = PaperBroker.load(paper_state_path) if paper_state_path.exists() else PaperBroker()
    paper_broker_status = LocalSandboxPaperBrokerAdapter(paper_broker).status()
    strategy_summary = summarize_strategy_tournament_history(strategy_history_path)
    performance_summary = summarize_paper_performance_history(performance_history_path)

    checks = [
        _check_automatic_loop(loop_snapshot, max_refresh_interval_seconds=max_refresh_interval_seconds),
        _check_strategy_iteration(strategy_summary),
        _check_paper_execution(performance_summary, paper_broker_status),
        _check_order_intent(latest_ticket),
        _check_risk_check(latest_ticket),
        _check_approval_queue(queue_summary),
        _check_broker_ready_ticket(latest_fresh_ticket or latest_ticket),
        _check_freshness(latest_fresh_ticket, loop_snapshot, max_refresh_interval_seconds=max_refresh_interval_seconds),
        _check_dashboard_app(app_paths),
        _check_real_order_boundary(paper_broker_status),
    ]
    overall_status = _overall_status(checks)
    ready = overall_status == "healthy"
    return {
        "status": "ready" if ready else "not_ready",
        "status_zh": "已就绪" if ready else "未完全就绪",
        "overall_status": overall_status,
        "overall_status_zh": _overall_status_zh(overall_status),
        "generated_at": utc_now_iso(),
        "deadline": PAPER_DELIVERY_DEADLINE,
        "deadline_zh": PAPER_DELIVERY_DEADLINE_ZH,
        "dashboard_app_deadline": DASHBOARD_APP_DEADLINE,
        "dashboard_app_deadline_zh": DASHBOARD_APP_DEADLINE_ZH,
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": sum(1 for item in checks if item["status"] == "warn"),
        "fail_count": sum(1 for item in checks if item["status"] == "fail"),
        "checks": checks,
        "summary_zh": _summary_zh(checks),
        "queue_summary": queue_summary,
        "strategy_summary": strategy_summary,
        "performance_summary": performance_summary,
        "latest_ticket": latest_ticket,
        "latest_fresh_ticket_id": latest_fresh_ticket.get("ticket_id") if latest_fresh_ticket else None,
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "message_zh": "该就绪报告只验证自动模拟交易、候选订单、风控、审批队列和人工工单；不会提交真实资金订单。",
        },
    }


def format_paper_trading_readiness_summary_zh(report: dict) -> str:
    lines = [
        "Alpha 模拟交易交付就绪报告",
        f"总体状态：{report.get('overall_status_zh', '未知')}",
        f"生成时间：{report.get('generated_at', '无')}",
        f"通过/关注/失败：{report.get('pass_count', 0)} / {report.get('warn_count', 0)} / {report.get('fail_count', 0)}",
        f"结论：{report.get('summary_zh', '无')}",
        "检查项：",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知检查')}：{check.get('status_zh', '未知')} - {check.get('message_zh', '')}")
    lines.append("安全边界：不会提交真实资金订单。")
    return "\n".join(lines)


def _check_automatic_loop(loop_snapshot: dict | None, *, max_refresh_interval_seconds: int) -> dict:
    if not loop_snapshot:
        return _check("automatic_paper_loop", "全自动模拟交易循环", "fail", "缺少自动循环快照，无法证明 5 分钟自动运行。")
    enabled = bool(loop_snapshot.get("enabled"))
    task_running = bool(loop_snapshot.get("task_running"))
    interval = int(loop_snapshot.get("interval_seconds") or 0)
    run_count = int(loop_snapshot.get("run_count") or 0)
    evidence = {
        "enabled": enabled,
        "task_running": task_running,
        "interval_seconds": interval,
        "run_count": run_count,
        "status": loop_snapshot.get("status"),
    }
    if not enabled or not task_running:
        return _check("automatic_paper_loop", "全自动模拟交易循环", "fail", "自动模拟交易循环未运行。", evidence)
    if interval <= 0 or interval > max_refresh_interval_seconds:
        return _check("automatic_paper_loop", "全自动模拟交易循环", "fail", "自动循环间隔超过 300 秒。", evidence)
    if run_count <= 0 and loop_snapshot.get("status") not in {"starting", "running_cycle"}:
        return _check("automatic_paper_loop", "全自动模拟交易循环", "warn", "自动循环已启动但尚未完成首轮。", evidence)
    return _check("automatic_paper_loop", "全自动模拟交易循环", "pass", "自动循环正在运行，刷新间隔不超过 300 秒。", evidence)


def _check_strategy_iteration(strategy_summary: dict) -> dict:
    evidence = {
        "run_count": strategy_summary.get("run_count", 0),
        "latest_winner_strategy_id": strategy_summary.get("latest_winner_strategy_id"),
        "latest_winner_strategy_id_zh": strategy_summary.get("latest_winner_strategy_id_zh"),
        "latest_winner_decision": strategy_summary.get("latest_winner_decision"),
        "latest_winner_validation_windows": strategy_summary.get("latest_winner_validation_windows", 0),
        "stability_ratio_zh": strategy_summary.get("stability_ratio_zh"),
    }
    if int(strategy_summary.get("run_count") or 0) <= 0:
        return _check("strategy_iteration", "策略迭代证据", "warn", "尚无策略迭代历史；首轮模拟交易后应写入。", evidence)
    if int(strategy_summary.get("latest_winner_validation_windows") or 0) <= 0:
        return _check("strategy_iteration", "策略迭代证据", "warn", "最近胜出策略缺少样本外验证窗口。", evidence)
    if strategy_summary.get("latest_winner_decision") != "promote_to_paper":
        return _check("strategy_iteration", "策略迭代证据", "warn", "最近胜出策略尚未达到模拟交易候选标准。", evidence)
    return _check("strategy_iteration", "策略迭代证据", "pass", "策略迭代已写入历史，并有样本外验证和可进入模拟交易的胜出策略。", evidence)


def _check_paper_execution(performance_summary: dict, paper_broker_status: dict) -> dict:
    evidence = {
        "performance_run_count": performance_summary.get("run_count", 0),
        "latest_trade_count": performance_summary.get("latest_trade_count", 0),
        "latest_execution_model_zh": performance_summary.get("latest_execution_model_zh"),
        "paper_trade_count": paper_broker_status.get("paper_trade_count", 0),
        "live_order_submission_enabled": paper_broker_status.get("live_order_submission_enabled"),
    }
    if paper_broker_status.get("live_order_submission_enabled"):
        return _check("paper_execution", "模拟交易执行", "fail", "模拟执行层错误地允许真实下单。", evidence)
    if int(performance_summary.get("run_count") or 0) <= 0:
        return _check("paper_execution", "模拟交易执行", "warn", "尚无模拟绩效历史。", evidence)
    if int(performance_summary.get("latest_trade_count") or 0) <= 0:
        return _check("paper_execution", "模拟交易执行", "warn", "已有绩效历史，但尚无模拟成交。", evidence)
    return _check("paper_execution", "模拟交易执行", "pass", "模拟成交、绩效历史和成本模型均可见。", evidence)


def _check_order_intent(ticket: dict) -> dict:
    intent = ticket.get("intent") or {}
    evidence = {
        "ticket_id": ticket.get("ticket_id"),
        "intent_id": intent.get("intent_id"),
        "strategy_id": intent.get("strategy_id"),
        "symbol": intent.get("symbol"),
        "estimated_notional_aud": intent.get("estimated_notional_aud"),
        "expires_at": intent.get("expires_at"),
    }
    required = ["intent_id", "strategy_id", "symbol", "side", "quantity", "estimated_price", "idempotency_key", "expires_at"]
    missing = [key for key in required if not intent.get(key)]
    if not ticket:
        return _check("order_intent_generation", "真实交易候选订单意图", "warn", "审批队列里尚无候选订单。", evidence)
    if missing:
        evidence["missing_fields"] = missing
        return _check("order_intent_generation", "真实交易候选订单意图", "fail", "最新候选单缺少结构化 OrderIntent 字段。", evidence)
    return _check("order_intent_generation", "真实交易候选订单意图", "pass", "最新候选单包含结构化 OrderIntent，可作为真实交易候选订单意图进入人工流程。", evidence)


def _check_risk_check(ticket: dict) -> dict:
    risk = ticket.get("risk_check") or {}
    evidence = {
        "ticket_id": ticket.get("ticket_id"),
        "risk_status": risk.get("status"),
        "allowed": risk.get("allowed"),
        "reason": risk.get("reason"),
    }
    if not ticket:
        return _check("risk_check", "自动风控检查", "warn", "尚无候选单可验证风控结果。", evidence)
    if "allowed" not in risk or not risk.get("status") or not risk.get("reason"):
        return _check("risk_check", "自动风控检查", "fail", "候选单缺少完整风控结果。", evidence)
    if not risk.get("allowed"):
        return _check("risk_check", "自动风控检查", "warn", "风控已运行，但最近候选单被阻止。", evidence)
    return _check("risk_check", "自动风控检查", "pass", "候选单已自动完成风控并通过人工复核前置检查。", evidence)


def _check_approval_queue(queue_summary: dict) -> dict:
    storage = queue_summary.get("storage") or {}
    evidence = {
        "total_count": queue_summary.get("total_count", 0),
        "fresh_pending_count": queue_summary.get("fresh_pending_count", 0),
        "expired_pending_count": queue_summary.get("expired_pending_count", 0),
        "backend": storage.get("backend"),
        "durable": storage.get("durable"),
    }
    if storage.get("backend") != "sqlite" or not storage.get("durable"):
        return _check("approval_queue", "自动审批队列", "fail", "审批队列不是 SQLite 持久化存储。", evidence)
    if int(queue_summary.get("fresh_pending_count") or 0) <= 0:
        return _check("approval_queue", "自动审批队列", "warn", "当前没有有效待人工确认候选单。", evidence)
    return _check("approval_queue", "自动审批队列", "pass", "候选单已自动进入 SQLite 审批队列，且存在有效待确认工单。", evidence)


def _check_broker_ready_ticket(ticket: dict) -> dict:
    payload = ticket.get("broker_payload") or {}
    evidence = {
        "ticket_id": ticket.get("ticket_id"),
        "status": ticket.get("status"),
        "actionability": ticket.get("actionability"),
        "human_action_required": ticket.get("human_action_required"),
        "symbol": payload.get("symbol"),
        "side": payload.get("side"),
        "quantity": payload.get("quantity"),
        "order_type": payload.get("order_type"),
        "time_in_force": payload.get("time_in_force"),
        "client_order_id": payload.get("client_order_id"),
    }
    if not ticket:
        return _check("broker_ready_ticket", "Broker-ready 工单", "warn", "尚无候选单可生成 broker-ready 工单。", evidence)
    required = ["symbol", "side", "quantity", "order_type", "time_in_force", "client_order_id"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        evidence["missing_fields"] = missing
        return _check("broker_ready_ticket", "Broker-ready 工单", "fail", "最新候选单缺少经纪商人工录入字段。", evidence)
    if ticket.get("status") == "blocked_by_risk":
        return _check("broker_ready_ticket", "Broker-ready 工单", "warn", "最近候选单被风控阻止，不能进入人工录入。", evidence)
    return _check("broker_ready_ticket", "Broker-ready 工单", "pass", "最新候选单已包含经纪商人工录入所需字段。", evidence)


def _check_freshness(ticket: dict | None, loop_snapshot: dict | None, *, max_refresh_interval_seconds: int) -> dict:
    freshness = (ticket or {}).get("freshness") or {}
    interval = int((loop_snapshot or {}).get("interval_seconds") or 0)
    evidence = {
        "ticket_id": (ticket or {}).get("ticket_id"),
        "freshness_status": freshness.get("status"),
        "seconds_until_expiry": freshness.get("seconds_until_expiry"),
        "interval_seconds": interval,
        "max_refresh_interval_seconds": max_refresh_interval_seconds,
    }
    if interval <= 0 or interval > max_refresh_interval_seconds:
        return _check("five_minute_freshness", "5 分钟及时性", "fail", "自动循环间隔未满足 300 秒要求。", evidence)
    if not ticket:
        return _check("five_minute_freshness", "5 分钟及时性", "warn", "当前没有有效候选单可验证时效性。", evidence)
    if freshness.get("status") != "fresh":
        return _check("five_minute_freshness", "5 分钟及时性", "warn", "最新可操作候选单不是有效状态。", evidence)
    return _check("five_minute_freshness", "5 分钟及时性", "pass", "当前存在有效候选单，且自动循环间隔不超过 300 秒。", evidence)


def _check_dashboard_app(app_paths: list[Path]) -> dict:
    evidence = {
        "paths": [{"path": str(path), "exists": path.exists(), "is_app": path.suffix == ".app"} for path in app_paths],
    }
    missing = [item["path"] for item in evidence["paths"] if not item["exists"]]
    non_app = [item["path"] for item in evidence["paths"] if item["exists"] and not item["is_app"]]
    if non_app:
        evidence["non_app_paths"] = non_app
        return _check("dashboard_app_entry", "本地 App 入口", "fail", "存在入口路径但不是 .app 格式。", evidence)
    if missing:
        evidence["missing_paths"] = missing
        return _check("dashboard_app_entry", "本地 App 入口", "warn", "部分 Downloads/Applications App 入口未检测到。", evidence)
    return _check("dashboard_app_entry", "本地 App 入口", "pass", "Downloads、用户 Applications、系统 Applications 和仓库入口均检测到 Alpha.app。", evidence)


def _check_real_order_boundary(paper_broker_status: dict) -> dict:
    evidence = {
        "mode": paper_broker_status.get("mode"),
        "live_order_submission_enabled": paper_broker_status.get("live_order_submission_enabled"),
        "supports_real_broker_place_order": paper_broker_status.get("supports_real_broker_place_order"),
    }
    if paper_broker_status.get("live_order_submission_enabled") or paper_broker_status.get("supports_real_broker_place_order"):
        return _check("real_order_boundary", "真实下单边界", "fail", "模拟交易路径出现真实下单能力，必须停止。", evidence)
    return _check("real_order_boundary", "真实下单边界", "pass", "自动路径保持模拟交易和人工工单模式，不提交真实资金订单。", evidence)


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


def _overall_status_zh(status: str) -> str:
    return {"healthy": "就绪", "degraded": "需补强", "unhealthy": "不可交付"}.get(status, "未知")


def _check_status_zh(status: object) -> str:
    return {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(str(status), "未知")


def _summary_zh(checks: list[dict]) -> str:
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    if fail_count:
        return f"仍有 {fail_count} 个失败项，不能声明 6月15日模拟交易交付就绪。"
    if warn_count:
        return f"核心自动链路可运行，但仍有 {warn_count} 个关注项需要补强后再声明成熟交付。"
    return "自动模拟交易、候选订单、风控、审批队列、工单、5分钟时效和本地 App 入口均通过就绪检查。"


def _default_app_paths(root: Path) -> list[Path]:
    return [
        root / "outputs" / "applications" / "Alpha.app",
        Path.home() / "Downloads" / "Alpha.app",
        Path.home() / "Applications" / "Alpha.app",
        Path("/Applications/Alpha.app"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="输出原始机器 JSON；默认输出中文就绪摘要")
    args = parser.parse_args()
    report = collect_paper_trading_readiness()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(format_paper_trading_readiness_summary_zh(report))


if __name__ == "__main__":
    main()
