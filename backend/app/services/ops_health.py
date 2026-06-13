from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter
from backend.app.services.market_data_gateway import MarketDataGateway
from backend.app.services.moomoo_broker_probe import probe_moomoo_opend
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.runtime_status import read_persisted_runtime_snapshot


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MAX_LOOP_LAG_SECONDS = 420
DEFAULT_MAX_BACKUP_AGE_SECONDS = 86_400
DEFAULT_MAX_BACKUP_COUNT = 30
DEFAULT_MAX_HISTORY_ROWS = 10_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def collect_ops_health(
    *,
    root: str | Path = DEFAULT_ROOT,
    queue_path: str | Path | None = None,
    paper_state_path: str | Path | None = None,
    pid_path: str | Path | None = None,
    log_path: str | Path | None = None,
    market_data_gateway: MarketDataGateway | None = None,
    loop_snapshot: dict | None = None,
    loop_snapshot_path: str | Path | None = None,
    moomoo_probe_status: dict | None = None,
    max_loop_lag_seconds: int = DEFAULT_MAX_LOOP_LAG_SECONDS,
    max_backup_age_seconds: int = DEFAULT_MAX_BACKUP_AGE_SECONDS,
) -> dict:
    root = Path(root)
    queue_path = Path(queue_path) if queue_path else root / "runtime" / "approval_queue.sqlite3"
    paper_state_path = Path(paper_state_path) if paper_state_path else root / "runtime" / "paper_portfolio.json"
    pid_path = Path(pid_path) if pid_path else root / "runtime" / "alpha_dashboard.pid"
    log_path = Path(log_path) if log_path else root / "runtime" / "alpha_dashboard.log"
    gateway = market_data_gateway or MarketDataGateway(root=root)
    loop_snapshot_evidence = None
    if loop_snapshot is None:
        loop_snapshot, loop_snapshot_evidence = read_persisted_runtime_snapshot(
            loop_snapshot_path or root / "runtime" / "agent_loop_status.json",
            expected_kind="agent_loop",
            max_age_seconds=max_loop_lag_seconds,
        )

    checks = [
        _check_agent_loop(
            loop_snapshot,
            max_loop_lag_seconds=max_loop_lag_seconds,
            persisted_evidence=loop_snapshot_evidence,
        ),
        _check_approval_queue(queue_path),
        _check_paper_portfolio(paper_state_path),
        _check_paper_broker_boundary(paper_state_path),
        _check_moomoo_read_only_probe(moomoo_probe_status if moomoo_probe_status is not None else probe_moomoo_opend()),
        _check_market_data(gateway),
        _check_dashboard_process(pid_path, loop_snapshot=loop_snapshot),
        _check_log_tail(log_path),
        _check_backup_freshness(root / "runtime" / "backups", max_backup_age_seconds=max_backup_age_seconds),
    ]
    overall_status = _overall_status(checks)
    return {
        "overall_status": overall_status,
        "overall_status_zh": _overall_status_zh(overall_status),
        "generated_at": utc_now_iso(),
        "checks": checks,
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": sum(1 for item in checks if item["status"] == "warn"),
        "fail_count": sum(1 for item in checks if item["status"] == "fail"),
        "runtime_paths": {
            "queue_path": str(queue_path),
            "paper_state_path": str(paper_state_path),
            "pid_path": str(pid_path),
            "log_path": str(log_path),
            "backup_dir": str(root / "runtime" / "backups"),
        },
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "message_zh": "运行健康检查只覆盖模拟交易、审批队列和工单生成；不会提交真实资金订单。",
        },
        "latest_backup": _latest_backup_manifest(root / "runtime" / "backups"),
    }


def create_runtime_backup(
    *,
    root: str | Path = DEFAULT_ROOT,
    queue_path: str | Path | None = None,
    paper_state_path: str | Path | None = None,
    market_data_cache_path: str | Path | None = None,
    pid_path: str | Path | None = None,
    log_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict:
    root = Path(root)
    queue_path = Path(queue_path) if queue_path else root / "runtime" / "approval_queue.sqlite3"
    paper_state_path = Path(paper_state_path) if paper_state_path else root / "runtime" / "paper_portfolio.json"
    market_data_cache_path = (
        Path(market_data_cache_path) if market_data_cache_path else root / "runtime" / "market_data" / "latest_prices.csv"
    )
    pid_path = Path(pid_path) if pid_path else root / "runtime" / "alpha_dashboard.pid"
    log_path = Path(log_path) if log_path else root / "runtime" / "alpha_dashboard.log"
    backup_root = Path(output_dir) if output_dir else root / "runtime" / "backups"
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup_dir = _unique_backup_dir(backup_root / f"alpha_state_{stamp}")
    backup_dir.mkdir(parents=True, exist_ok=False)

    copied_files: list[dict] = []
    missing_files: list[str] = []

    _copy_runtime_file(queue_path, backup_dir / queue_path.name, copied_files=copied_files, missing_files=missing_files)
    _copy_runtime_file(
        paper_state_path,
        backup_dir / paper_state_path.name,
        copied_files=copied_files,
        missing_files=missing_files,
    )
    _copy_runtime_file(
        market_data_cache_path,
        backup_dir / "latest_prices.csv",
        copied_files=copied_files,
        missing_files=missing_files,
    )
    _copy_runtime_file(pid_path, backup_dir / pid_path.name, copied_files=copied_files, missing_files=missing_files)
    _write_log_tail(log_path, backup_dir / "alpha_dashboard.log.tail", copied_files=copied_files, missing_files=missing_files)

    manifest = {
        "status": "completed",
        "status_zh": "已完成",
        "backup_id": backup_dir.name,
        "created_at": utc_now_iso(),
        "backup_path": str(backup_dir),
        "copied_files": copied_files,
        "missing_files": missing_files,
        "live_order_submission_enabled": False,
        "message_zh": "已生成本地运行状态备份；该备份只包含模拟交易运行状态、审批队列、行情缓存和日志片段。",
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def append_ops_health_history(
    health: dict,
    *,
    history_path: str | Path,
    maintenance: dict | None = None,
    max_rows: int = DEFAULT_MAX_HISTORY_ROWS,
) -> dict:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "generated_at": health.get("generated_at") or utc_now_iso(),
        "overall_status": health.get("overall_status"),
        "overall_status_zh": health.get("overall_status_zh"),
        "pass_count": health.get("pass_count", 0),
        "warn_count": health.get("warn_count", 0),
        "fail_count": health.get("fail_count", 0),
        "checks": {
            check.get("id", "unknown"): check.get("status", "unknown")
            for check in health.get("checks", [])
        },
        "latest_backup_path": (health.get("latest_backup") or {}).get("backup_path"),
        "maintenance": maintenance or {},
    }
    rows = []
    if path.exists():
        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    if max_rows > 0:
        rows = rows[-max_rows:]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "path": str(path),
        "row_count": len(rows),
        "latest_record": record,
    }


def prune_runtime_backups(
    *,
    backup_root: str | Path,
    max_backup_count: int = DEFAULT_MAX_BACKUP_COUNT,
) -> dict:
    root = Path(backup_root)
    if max_backup_count <= 0:
        max_backup_count = DEFAULT_MAX_BACKUP_COUNT
    if not root.exists():
        return {"status": "unchanged", "backup_root": str(root), "kept_count": 0, "deleted_count": 0, "deleted_paths": []}
    backups = sorted(
        [path for path in root.glob("alpha_state_*") if path.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    stale = backups[max_backup_count:]
    deleted_paths = []
    for path in stale:
        shutil.rmtree(path)
        deleted_paths.append(str(path))
    return {
        "status": "pruned" if deleted_paths else "unchanged",
        "backup_root": str(root),
        "kept_count": min(len(backups), max_backup_count),
        "deleted_count": len(deleted_paths),
        "deleted_paths": deleted_paths,
        "max_backup_count": max_backup_count,
    }


def format_ops_health_summary_zh(health: dict) -> str:
    lines = [
        "Alpha 运行健康检查",
        f"总体状态：{health.get('overall_status_zh', '未知')}",
        f"生成时间：{health.get('generated_at', '无')}",
        f"通过/关注/失败：{health.get('pass_count', 0)} / {health.get('warn_count', 0)} / {health.get('fail_count', 0)}",
        "检查项：",
    ]
    for check in health.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知检查')}：{_check_status_zh(check.get('status'))} - {check.get('message_zh', '')}")
    latest_backup = health.get("latest_backup") or {}
    lines.append(f"最近备份：{latest_backup.get('backup_path') or '暂无'}")
    lines.append("安全边界：不会提交真实资金订单。")
    return "\n".join(lines)


def _check_agent_loop(
    loop_snapshot: dict | None,
    *,
    max_loop_lag_seconds: int,
    persisted_evidence: dict | None = None,
) -> dict:
    if not loop_snapshot:
        return _check(
            "agent_loop",
            "自动模拟交易循环",
            "warn",
            "当前上下文没有有效自动循环心跳；请通过控制台 /agent/loop/status 验证。",
            {"has_snapshot": False, "persisted_runtime_evidence": persisted_evidence},
        )
    interval = int(loop_snapshot.get("interval_seconds") or 0)
    task_running = bool(loop_snapshot.get("task_running"))
    enabled = bool(loop_snapshot.get("enabled"))
    run_count = int(loop_snapshot.get("run_count") or 0)
    last_completed_at = _parse_iso(loop_snapshot.get("last_run_completed_at"))
    age_seconds = int((utc_now() - last_completed_at).total_seconds()) if last_completed_at else None
    evidence = {
        "enabled": enabled,
        "task_running": task_running,
        "interval_seconds": interval,
        "run_count": run_count,
        "status": loop_snapshot.get("status"),
        "last_run_age_seconds": age_seconds,
        "persisted_runtime_evidence": loop_snapshot.get("persisted_runtime_evidence") or persisted_evidence,
    }
    if not enabled or not task_running:
        return _check("agent_loop", "自动模拟交易循环", "fail", "自动循环未运行，无法满足 5 分钟候选单更新要求。", evidence)
    if interval <= 0 or interval > 300:
        return _check("agent_loop", "自动模拟交易循环", "fail", "自动循环间隔超过 300 秒。", evidence)
    if age_seconds is not None and age_seconds > max_loop_lag_seconds:
        return _check("agent_loop", "自动模拟交易循环", "warn", "上次循环完成时间偏久，请确认后台没有卡住。", evidence)
    if run_count <= 0 and loop_snapshot.get("status") not in {"starting", "running_cycle"}:
        return _check("agent_loop", "自动模拟交易循环", "warn", "自动循环尚未完成首轮运行。", evidence)
    return _check("agent_loop", "自动模拟交易循环", "pass", "自动循环正在运行，刷新间隔不超过 300 秒。", evidence)


def _check_approval_queue(queue_path: Path) -> dict:
    queue = ApprovalQueue(queue_path)
    summary = queue.summary()
    storage = queue.storage_status()
    evidence = {"summary": summary, "storage": storage}
    if storage["backend"] != "sqlite" or not storage["durable"]:
        return _check("approval_queue", "审批队列", "fail", "审批队列不是 SQLite 持久化存储。", evidence)
    if not storage["exists"]:
        return _check("approval_queue", "审批队列", "warn", "审批队列文件尚未生成；首轮模拟交易后应出现。", evidence)
    if summary["fresh_pending_count"] <= 0:
        return _check("approval_queue", "审批队列", "warn", "当前没有有效待确认候选单；下一周期应自动生成新工单。", evidence)
    return _check("approval_queue", "审批队列", "pass", "SQLite 审批队列可用，且存在有效待确认候选单。", evidence)


def _check_paper_portfolio(paper_state_path: Path) -> dict:
    if not paper_state_path.exists():
        return _check(
            "paper_portfolio",
            "模拟组合状态",
            "warn",
            "模拟组合状态文件尚未生成；首轮模拟交易后应出现。",
            {"path": str(paper_state_path), "exists": False},
        )
    try:
        broker = PaperBroker.load(paper_state_path)
    except Exception as exc:
        return _check(
            "paper_portfolio",
            "模拟组合状态",
            "fail",
            "模拟组合状态文件无法读取。",
            {"path": str(paper_state_path), "error": str(exc)},
        )
    snapshot = broker.snapshot()
    if snapshot["trade_count"] <= 0:
        return _check("paper_portfolio", "模拟组合状态", "warn", "模拟组合存在但暂无模拟成交。", snapshot)
    return _check("paper_portfolio", "模拟组合状态", "pass", "模拟组合可读取，且已有模拟成交记录。", snapshot)


def _check_paper_broker_boundary(paper_state_path: Path) -> dict:
    broker = PaperBroker.load(paper_state_path) if paper_state_path.exists() else PaperBroker()
    status = LocalSandboxPaperBrokerAdapter(broker).status()
    if status.get("live_order_submission_enabled"):
        return _check("live_order_boundary", "真实下单边界", "fail", "模拟执行层错误地允许真实下单。", status)
    return _check("live_order_boundary", "真实下单边界", "pass", "执行层保持模拟模式，真实下单禁用。", status)


def _check_moomoo_read_only_probe(status: dict) -> dict:
    if status.get("live_order_submission_enabled") or status.get("trade_context_enabled") or status.get("supports_real_broker_place_order"):
        return _check("moomoo_read_only_probe", "富途牛牛开放网关只读探测", "fail", "富途牛牛探测层出现真实交易能力，必须立即停用。", status)
    if status.get("read_only_ready"):
        return _check("moomoo_read_only_probe", "富途牛牛开放网关只读探测", "pass", "富途牛牛接口包和本机开放网关端口可用，且保持只读。", status)
    return _check(
        "moomoo_read_only_probe",
        "富途牛牛开放网关只读探测",
        "warn",
        status.get("message_zh") or "富途牛牛开放网关只读探测未就绪；本地模拟交易仍可继续。",
        status,
    )


def _check_market_data(gateway: MarketDataGateway) -> dict:
    try:
        status = gateway.resolve_price_path().status
    except Exception as exc:
        return _check("market_data", "行情数据", "fail", "行情数据无法解析。", {"error": str(exc)})
    if int(status.get("row_count") or 0) <= 0:
        return _check("market_data", "行情数据", "fail", "行情数据为空，策略和模拟交易无法可靠运行。", status)
    if not status.get("real_market_data"):
        return _check("market_data", "行情数据", "warn", "当前使用本地样例或缓存回退行情，不是实时券商级行情。", status)
    return _check("market_data", "行情数据", "pass", "行情数据可用，且来自公共延迟行情缓存。", status)


def _check_dashboard_process(pid_path: Path, *, loop_snapshot: dict | None) -> dict:
    if pid_path.exists():
        raw_pid = pid_path.read_text(encoding="utf-8").strip()
        try:
            pid = int(raw_pid)
        except ValueError:
            return _check("dashboard_process", "控制台进程", "fail", "PID 文件内容无效。", {"path": str(pid_path), "raw_pid": raw_pid})
        if _pid_is_running(pid):
            return _check("dashboard_process", "控制台进程", "pass", "控制台进程正在运行。", {"path": str(pid_path), "pid": pid})
        if loop_snapshot and loop_snapshot.get("task_running"):
            return _check(
                "dashboard_process",
                "控制台进程",
                "warn",
                "PID 文件已过期，但当前应用内自动循环正在运行；建议用启动脚本重启以刷新 PID。",
                {"path": str(pid_path), "pid": pid},
            )
        return _check("dashboard_process", "控制台进程", "fail", "PID 文件存在，但对应进程未运行。", {"path": str(pid_path), "pid": pid})
    if loop_snapshot and loop_snapshot.get("task_running"):
        return _check("dashboard_process", "控制台进程", "warn", "当前 API 内循环在运行，但未找到启动脚本 PID 文件。", {"path": str(pid_path)})
    return _check("dashboard_process", "控制台进程", "warn", "未找到控制台 PID 文件；请用本地 App 或启动脚本启动。", {"path": str(pid_path)})


def _check_log_tail(log_path: Path) -> dict:
    if not log_path.exists():
        return _check("dashboard_log", "控制台日志", "warn", "控制台日志文件尚未生成。", {"path": str(log_path), "exists": False})
    tail = _tail_lines(log_path, max_lines=200)
    has_error = any(("Traceback" in line or "ERROR" in line) for line in tail)
    evidence = {"path": str(log_path), "line_count_checked": len(tail), "has_error_markers": has_error}
    if has_error:
        return _check("dashboard_log", "控制台日志", "warn", "最近日志包含错误标记，请打开日志确认。", evidence)
    return _check("dashboard_log", "控制台日志", "pass", "最近日志未发现 Traceback 或 ERROR 标记。", evidence)


def _check_backup_freshness(backup_root: Path, *, max_backup_age_seconds: int) -> dict:
    latest = _latest_backup_manifest(backup_root)
    if not latest:
        return _check("runtime_backup", "运行状态备份", "warn", "尚未生成运行状态备份。", {"backup_dir": str(backup_root)})
    created_at = _parse_iso(latest.get("created_at"))
    age_seconds = int((utc_now() - created_at).total_seconds()) if created_at else None
    evidence = {"latest_backup": latest, "age_seconds": age_seconds}
    if age_seconds is None:
        return _check("runtime_backup", "运行状态备份", "warn", "最近备份缺少有效创建时间。", evidence)
    if age_seconds > max_backup_age_seconds:
        return _check("runtime_backup", "运行状态备份", "warn", "最近备份超过 24 小时，建议重新生成。", evidence)
    return _check("runtime_backup", "运行状态备份", "pass", "最近 24 小时内已有运行状态备份。", evidence)


def _copy_runtime_file(source: Path, target: Path, *, copied_files: list[dict], missing_files: list[str]) -> None:
    if not source.exists():
        missing_files.append(str(source))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
        with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
    else:
        shutil.copy2(source, target)
    copied_files.append({"source": str(source), "target": str(target), "size_bytes": target.stat().st_size})


def _unique_backup_dir(base: Path) -> Path:
    if not base.exists():
        return base
    for index in range(1, 1000):
        candidate = base.with_name(f"{base.name}_{index:03d}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not allocate unique backup directory under {base.parent}")


def _write_log_tail(source: Path, target: Path, *, copied_files: list[dict], missing_files: list[str], max_lines: int = 500) -> None:
    if not source.exists():
        missing_files.append(str(source))
        return
    target.write_text("".join(_tail_lines(source, max_lines=max_lines)), encoding="utf-8")
    copied_files.append({"source": str(source), "target": str(target), "size_bytes": target.stat().st_size})


def _tail_lines(path: Path, *, max_lines: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError:
        return []
    return lines[-max_lines:]


def _latest_backup_manifest(backup_root: Path) -> dict | None:
    if not backup_root.exists():
        return None
    manifests = sorted(backup_root.glob("alpha_state_*/manifest.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not manifests:
        return None
    try:
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    manifest["manifest_path"] = str(manifests[0])
    return manifest


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
    return {"healthy": "健康", "degraded": "需关注", "unhealthy": "不可用"}.get(status, "未知")


def _check_status_zh(status: object) -> str:
    return {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(str(status), "未知")


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="输出原始机器 JSON；默认输出中文健康摘要")
    parser.add_argument("--backup", action="store_true", help="生成一次本地运行状态备份")
    args = parser.parse_args()

    if args.backup:
        result = create_runtime_backup()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Alpha 运行状态备份已生成：{result['backup_path']}")
            print("安全边界：备份不会提交真实资金订单。")
        return

    health = collect_ops_health()
    if args.json:
        print(json.dumps(health, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(format_ops_health_summary_zh(health))


if __name__ == "__main__":
    main()
