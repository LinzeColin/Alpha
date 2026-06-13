from __future__ import annotations

import argparse
import copy
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.paper_readiness import collect_paper_trading_readiness
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, PaperTradingLoop
from backend.app.services.policy import GovernorPolicy


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CYCLES = 3
DEFAULT_OUTPUT_PATH = DEFAULT_ROOT / "outputs" / "paper_maturity" / "paper_trading_maturity_latest.json"


def run_paper_trading_maturity_check(
    *,
    root: str | Path = DEFAULT_ROOT,
    cycles: int = DEFAULT_CYCLES,
    refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
) -> dict:
    root = Path(root)
    cycles = max(1, int(cycles))
    with tempfile.TemporaryDirectory(prefix="alpha-paper-maturity-") as temp_root_raw:
        temp_root = Path(temp_root_raw)
        normal = _run_normal_cycles(root=root, temp_root=temp_root / "normal", cycles=cycles, interval_seconds=refresh_interval_seconds)
        rebalance = _run_rebalance_cycle(root=root, temp_root=temp_root / "rebalance", interval_seconds=refresh_interval_seconds)
        cash_rebalance = _run_cash_rebalance_cycle(
            root=root,
            temp_root=temp_root / "cash-rebalance",
            interval_seconds=refresh_interval_seconds,
        )

    checks = [
        _check_normal_cycles(normal, cycles=cycles),
        _check_normal_readiness(normal),
        _check_rebalance_sell(rebalance),
        _check_cash_rebalance_sell(cash_rebalance),
        _check_ticket_contract(normal, scenario_id="normal"),
        _check_ticket_contract(rebalance, scenario_id="target_rebalance"),
        _check_ticket_contract(cash_rebalance, scenario_id="cash_rebalance"),
        _check_refresh_interval(normal, refresh_interval_seconds=refresh_interval_seconds),
        _check_no_live_order_path(normal, rebalance, cash_rebalance),
    ]
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    status = "pass" if fail_count == 0 else "fail"
    return {
        "status": status,
        "status_zh": "通过" if status == "pass" else "失败",
        "overall_status": "mature" if status == "pass" and warn_count == 0 else ("needs_attention" if status == "pass" else "blocked"),
        "overall_status_zh": "成熟可用" if status == "pass" and warn_count == 0 else ("需关注" if status == "pass" else "不可用"),
        "generated_at": _utc_now_iso(),
        "cycle_count": cycles,
        "refresh_interval_seconds": refresh_interval_seconds,
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "normal_cycles": _sanitize_scenario(normal),
        "target_rebalance": _sanitize_scenario(rebalance),
        "rebalance": _sanitize_scenario(rebalance),
        "cash_rebalance": _sanitize_scenario(cash_rebalance),
        "summary_zh": _summary_zh(checks),
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "supports_real_broker_place_order": False,
            "message_zh": "该成熟度验收只运行本地临时模拟交易状态，不读取真实交易凭据、不创建真实交易上下文、不触发真实下单、不提交真实资金订单。",
        },
    }


def format_paper_trading_maturity_summary_zh(report: dict) -> str:
    lines = [
        "Alpha 模拟交易成熟度验收",
        f"总体状态：{report.get('overall_status_zh', '未知')}",
        f"生成时间：{report.get('generated_at', '无')}",
        f"验收周期数：{report.get('cycle_count', 0)}",
        f"通过/关注/失败：{report.get('pass_count', 0)} / {report.get('warn_count', 0)} / {report.get('fail_count', 0)}",
        f"结论：{report.get('summary_zh', '无')}",
        "检查项：",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知检查')}：{check.get('status_zh', '未知')} - {check.get('message_zh', '')}")
    lines.append("安全边界：不触发真实下单，不提交真实资金订单。")
    return "\n".join(lines)


def write_paper_trading_maturity_report(report: dict, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "status": "written",
        "status_zh": "已写入",
        "path": str(path),
        "file_size_bytes": path.stat().st_size,
    }


def _run_normal_cycles(*, root: Path, temp_root: Path, cycles: int, interval_seconds: int) -> dict:
    paths = _scenario_paths(temp_root)
    app_path = paths["app_path"]
    app_path.mkdir(parents=True, exist_ok=True)
    loop = PaperTradingLoop(
        policy=GovernorPolicy.load(root / "configs" / "trading_governor_policy.yaml"),
        price_path=root / "data" / "sample_prices.csv",
        approval_queue=ApprovalQueue(paths["queue_path"]),
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        refresh_interval_seconds=interval_seconds,
    )
    results = [loop.run_once() for _ in range(cycles)]
    readiness = collect_paper_trading_readiness(
        root=temp_root,
        queue_path=paths["queue_path"],
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        loop_snapshot=_loop_snapshot(interval_seconds=interval_seconds, run_count=cycles),
        app_paths=[app_path],
        max_refresh_interval_seconds=interval_seconds,
    )
    return {"scenario_id": "normal_cycles", "results": results, "readiness": readiness, "paths": _redacted_paths(paths)}


def _run_rebalance_cycle(*, root: Path, temp_root: Path, interval_seconds: int) -> dict:
    paths = _scenario_paths(temp_root)
    app_path = paths["app_path"]
    app_path.mkdir(parents=True, exist_ok=True)
    broker = PaperBroker(cash=5000.0, positions={"TLT": 50.0})
    loop = PaperTradingLoop(
        policy=GovernorPolicy.load(root / "configs" / "trading_governor_policy.yaml"),
        price_path=root / "data" / "sample_prices.csv",
        approval_queue=ApprovalQueue(paths["queue_path"]),
        paper_broker=broker,
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        refresh_interval_seconds=interval_seconds,
    )
    result = loop.run_once()
    readiness = collect_paper_trading_readiness(
        root=temp_root,
        queue_path=paths["queue_path"],
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        loop_snapshot=_loop_snapshot(interval_seconds=interval_seconds, run_count=1),
        app_paths=[app_path],
        max_refresh_interval_seconds=interval_seconds,
    )
    return {"scenario_id": "rebalance", "results": [result], "readiness": readiness, "paths": _redacted_paths(paths)}


def _run_cash_rebalance_cycle(*, root: Path, temp_root: Path, interval_seconds: int) -> dict:
    paths = _scenario_paths(temp_root)
    app_path = paths["app_path"]
    app_path.mkdir(parents=True, exist_ok=True)
    policy = _cash_rebalance_policy(root / "configs" / "trading_governor_policy.yaml")
    broker = PaperBroker(cash=1.0, positions={"TLT": 2.0})
    loop = PaperTradingLoop(
        policy=policy,
        price_path=root / "data" / "sample_prices.csv",
        approval_queue=ApprovalQueue(paths["queue_path"]),
        paper_broker=broker,
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        refresh_interval_seconds=interval_seconds,
    )
    result = loop.run_once()
    readiness = collect_paper_trading_readiness(
        root=temp_root,
        queue_path=paths["queue_path"],
        paper_state_path=paths["paper_state_path"],
        strategy_history_path=paths["strategy_history_path"],
        performance_history_path=paths["performance_history_path"],
        loop_snapshot=_loop_snapshot(interval_seconds=interval_seconds, run_count=1),
        app_paths=[app_path],
        max_refresh_interval_seconds=interval_seconds,
    )
    return {
        "scenario_id": "cash_rebalance",
        "results": [result],
        "readiness": readiness,
        "paths": _redacted_paths(paths),
        "policy_override_zh": "该场景临时关闭仓位/总敞口上限，仅隔离验证现金不足减仓分支，不修改默认提交配置。",
    }


def _cash_rebalance_policy(path: Path) -> GovernorPolicy:
    base = GovernorPolicy.load(path)
    data = copy.deepcopy(base.data)
    limits = data.setdefault("risk_limits", {})
    limits["max_position_weight_pct"] = 0
    limits["max_total_gross_exposure_pct"] = 0
    data["policy_version"] = f"{base.version}.cash_rebalance_isolation"
    return GovernorPolicy(data)


def _loop_snapshot(*, interval_seconds: int, run_count: int) -> dict:
    completed_at = datetime.now(timezone.utc).replace(microsecond=0)
    next_run_at = completed_at + timedelta(seconds=interval_seconds)
    return {
        "enabled": True,
        "task_running": True,
        "interval_seconds": interval_seconds,
        "run_count": run_count,
        "status": "sleeping",
        "last_run_completed_at": completed_at.isoformat(),
        "next_run_at": next_run_at.isoformat(),
    }


def _scenario_paths(temp_root: Path) -> dict[str, Path]:
    return {
        "queue_path": temp_root / "runtime" / "approval_queue.sqlite3",
        "paper_state_path": temp_root / "runtime" / "paper_portfolio.json",
        "strategy_history_path": temp_root / "runtime" / "strategy_tournament_history.jsonl",
        "performance_history_path": temp_root / "runtime" / "paper_performance_history.jsonl",
        "app_path": temp_root / "Alpha.app",
    }


def _redacted_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {key: f"<temporary>/{value.name}" for key, value in paths.items()}


def _sanitize_scenario(scenario: dict) -> dict:
    results = scenario.get("results") or []
    return {
        "scenario_id": scenario.get("scenario_id"),
        "cycle_count": len(results),
        "sides": [((result.get("intent") or {}).get("side")) for result in results],
        "symbols": [((result.get("intent") or {}).get("symbol")) for result in results],
        "run_ids": [result.get("run_id") for result in results],
        "risk_allowed_count": sum(1 for result in results if (result.get("risk_check") or {}).get("allowed") is True),
        "queued_count": sum(1 for result in results if (result.get("approval_queue") or {}).get("status") == "queued"),
        "filled_count": sum(1 for result in results if (result.get("paper_order") or {}).get("status") == "filled"),
        "broker_ready_ticket_count": sum(1 for result in results if _broker_ticket_is_ready(result)),
        "latest_portfolio": (results[-1].get("paper_portfolio") if results else {}),
        "readiness_overall_status": (scenario.get("readiness") or {}).get("overall_status"),
        "readiness_overall_status_zh": (scenario.get("readiness") or {}).get("overall_status_zh"),
        "policy_override_zh": scenario.get("policy_override_zh"),
        "paths": scenario.get("paths", {}),
    }


def _check_normal_cycles(scenario: dict, *, cycles: int) -> dict:
    results = scenario.get("results") or []
    evidence = _sanitize_scenario(scenario)
    if len(results) != cycles:
        return _check("normal_cycle_count", "连续模拟交易周期", "fail", "连续模拟交易周期数量不符合预期。", evidence)
    if any(result.get("status") != "completed" for result in results):
        return _check("normal_cycle_count", "连续模拟交易周期", "fail", "至少一个模拟交易周期未完成。", evidence)
    if evidence["risk_allowed_count"] != cycles or evidence["queued_count"] != cycles or evidence["filled_count"] != cycles:
        return _check("normal_cycle_count", "连续模拟交易周期", "fail", "连续周期没有全部完成风控、入队和模拟成交。", evidence)
    return _check("normal_cycle_count", "连续模拟交易周期", "pass", "连续模拟交易周期均完成风控、入队和本地模拟成交。", evidence)


def _check_normal_readiness(scenario: dict) -> dict:
    readiness = scenario.get("readiness") or {}
    evidence = {
        "overall_status": readiness.get("overall_status"),
        "pass_count": readiness.get("pass_count"),
        "fail_count": readiness.get("fail_count"),
        "warn_count": readiness.get("warn_count"),
        "latest_fresh_ticket_id": readiness.get("latest_fresh_ticket_id"),
    }
    if readiness.get("overall_status") != "healthy":
        return _check("paper_readiness_gate", "模拟交易就绪门槛", "fail", "连续周期后的模拟交易就绪报告未达到健康状态。", evidence)
    return _check("paper_readiness_gate", "模拟交易就绪门槛", "pass", "连续周期后的模拟交易就绪报告达到健康状态。", evidence)


def _check_rebalance_sell(scenario: dict) -> dict:
    result = (scenario.get("results") or [{}])[0]
    intent = result.get("intent") or {}
    portfolio = result.get("paper_portfolio") or {}
    evidence = {
        "side": intent.get("side"),
        "side_zh": intent.get("side_zh"),
        "symbol": intent.get("symbol"),
        "strategy_id_zh": intent.get("strategy_id_zh"),
        "cash": portfolio.get("cash"),
        "positions": portfolio.get("positions"),
        "paper_order_status": (result.get("paper_order") or {}).get("status"),
        "risk_allowed": (result.get("risk_check") or {}).get("allowed"),
    }
    if intent.get("side") != "sell":
        return _check("rebalance_sell", "目标仓位再平衡卖单", "fail", "目标仓位或现金约束场景没有生成减仓卖出候选单。", evidence)
    if (result.get("risk_check") or {}).get("allowed") is not True or (result.get("paper_order") or {}).get("status") != "filled":
        return _check("rebalance_sell", "目标仓位再平衡卖单", "fail", "减仓卖单未通过风控或未完成模拟成交。", evidence)
    return _check("rebalance_sell", "目标仓位再平衡卖单", "pass", "目标仓位超限场景会生成减仓卖单并完成本地模拟成交。", evidence)


def _check_cash_rebalance_sell(scenario: dict) -> dict:
    result = (scenario.get("results") or [{}])[0]
    intent = result.get("intent") or {}
    portfolio = result.get("paper_portfolio") or {}
    evidence = {
        "side": intent.get("side"),
        "side_zh": intent.get("side_zh"),
        "symbol": intent.get("symbol"),
        "strategy_id": intent.get("strategy_id"),
        "strategy_id_zh": intent.get("strategy_id_zh"),
        "cash": portfolio.get("cash"),
        "positions": portfolio.get("positions"),
        "paper_order_status": (result.get("paper_order") or {}).get("status"),
        "risk_allowed": (result.get("risk_check") or {}).get("allowed"),
        "policy_override_zh": scenario.get("policy_override_zh"),
    }
    if intent.get("side") != "sell" or not str(intent.get("strategy_id", "")).startswith("cash_rebalance_"):
        return _check("cash_rebalance_sell", "现金回收减仓卖单", "fail", "低现金隔离场景没有生成现金回收减仓卖出候选单。", evidence)
    if (result.get("risk_check") or {}).get("allowed") is not True or (result.get("paper_order") or {}).get("status") != "filled":
        return _check("cash_rebalance_sell", "现金回收减仓卖单", "fail", "现金回收减仓卖单未通过风控或未完成模拟成交。", evidence)
    return _check("cash_rebalance_sell", "现金回收减仓卖单", "pass", "低现金隔离场景会生成现金回收减仓卖单并完成本地模拟成交。", evidence)


def _check_ticket_contract(scenario: dict, *, scenario_id: str) -> dict:
    results = scenario.get("results") or []
    missing: list[dict] = []
    for result in results:
        ticket = (result.get("approval_queue") or {}).get("ticket") or {}
        payload = ticket.get("broker_payload") or {}
        intent = result.get("intent") or {}
        required_payload = ["symbol", "side", "quantity", "order_type", "time_in_force", "client_order_id"]
        missing_fields = [field for field in required_payload if not payload.get(field)]
        ttl_seconds = _ttl_seconds(intent)
        if missing_fields or ttl_seconds != result.get("refresh_interval_seconds"):
            missing.append({"run_id": result.get("run_id"), "missing_fields": missing_fields, "ttl_seconds": ttl_seconds})
    evidence = {"scenario_id": scenario_id, "bad_ticket_count": len(missing), "bad_tickets": missing[:5]}
    if missing:
        return _check(f"{scenario_id}_ticket_contract", "经纪商就绪工单结构", "fail", "存在缺字段或 TTL 不等于刷新间隔的工单。", evidence)
    return _check(f"{scenario_id}_ticket_contract", "经纪商就绪工单结构", "pass", "工单包含人工经纪商录入字段，TTL 与 5 分钟刷新间隔一致。", evidence)


def _check_refresh_interval(scenario: dict, *, refresh_interval_seconds: int) -> dict:
    intervals = [result.get("refresh_interval_seconds") for result in scenario.get("results", [])]
    evidence = {"intervals": intervals, "expected": refresh_interval_seconds}
    if any(interval != refresh_interval_seconds for interval in intervals):
        return _check("refresh_interval_contract", "5 分钟刷新契约", "fail", "至少一个周期的刷新间隔不是 300 秒。", evidence)
    return _check("refresh_interval_contract", "5 分钟刷新契约", "pass", "所有周期均保持 300 秒刷新契约。", evidence)


def _check_no_live_order_path(*scenarios: dict) -> dict:
    violations = []
    for scenario in scenarios:
        for result in scenario.get("results", []):
            adapter = result.get("paper_broker_adapter") or {}
            broker_order = result.get("broker_paper_order") or {}
            if adapter.get("live_order_submission_enabled") or adapter.get("supports_real_broker_place_order"):
                violations.append({"run_id": result.get("run_id"), "source": "adapter"})
            if broker_order.get("live_order_submission_enabled") or broker_order.get("supports_real_broker_place_order"):
                violations.append({"run_id": result.get("run_id"), "source": "broker_order"})
    evidence = {"violation_count": len(violations), "violations": violations[:5]}
    if violations:
        return _check("real_order_boundary", "真实下单禁用边界", "fail", "成熟度验收发现真实下单能力。", evidence)
    return _check("real_order_boundary", "真实下单禁用边界", "pass", "所有成熟度验收周期均保持真实下单禁用。", evidence)


def _broker_ticket_is_ready(result: dict) -> bool:
    ticket = (result.get("approval_queue") or {}).get("ticket") or {}
    payload = ticket.get("broker_payload") or {}
    return bool(ticket.get("ticket_id") and ticket.get("human_action_required") and payload.get("client_order_id"))


def _ttl_seconds(intent: dict) -> int | None:
    try:
        created_at = datetime.fromisoformat(str(intent.get("created_at")))
        expires_at = datetime.fromisoformat(str(intent.get("expires_at")))
    except ValueError:
        return None
    return int((expires_at - created_at).total_seconds())


def _check(check_id: str, title_zh: str, status: str, message_zh: str, evidence: dict | None = None) -> dict:
    return {
        "id": check_id,
        "title_zh": title_zh,
        "status": status,
        "status_zh": {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(status, "未知"),
        "message_zh": message_zh,
        "evidence": evidence or {},
    }


def _summary_zh(checks: list[dict]) -> str:
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    if fail_count:
        return f"模拟交易成熟度验收失败：{fail_count} 个失败项需要先修复。"
    if warn_count:
        return f"模拟交易主链路通过，但仍有 {warn_count} 个关注项。"
    return "连续模拟交易、目标仓位再平衡、现金回收减仓、风控、审批队列、经纪商就绪工单、5分钟时效和真实下单禁用边界均通过。"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Alpha 模拟交易成熟度验收。")
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES, help="连续正常模拟交易周期数。")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="JSON 报告输出路径。")
    parser.add_argument("--json", action="store_true", help="打印完整 JSON；默认打印中文摘要。")
    args = parser.parse_args()
    report = run_paper_trading_maturity_check(cycles=args.cycles)
    write_result = write_paper_trading_maturity_report(report, args.output)
    report["write_result"] = write_result
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_paper_trading_maturity_summary_zh(report))
        print(f"报告路径：{write_result['path']}")


if __name__ == "__main__":
    main()
