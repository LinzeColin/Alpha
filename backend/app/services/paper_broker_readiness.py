from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.broker_paper_adapter import build_paper_broker_adapter, load_paper_broker_config
from backend.app.services.paper_broker import PaperBroker


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = DEFAULT_ROOT / "configs" / "paper_broker.yaml"
DEFAULT_PAPER_STATE_PATH = DEFAULT_ROOT / "runtime" / "paper_portfolio.json"
DEFAULT_OUTPUT_PATH = DEFAULT_ROOT / "outputs" / "paper_broker_readiness" / "paper_broker_readiness_latest.json"


def collect_paper_broker_readiness(
    *,
    root: str | Path = DEFAULT_ROOT,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    paper_state_path: str | Path = DEFAULT_PAPER_STATE_PATH,
    paper_broker_status: dict | None = None,
    external_snapshot: dict | None = None,
) -> dict:
    root = Path(root)
    config_path = Path(config_path)
    paper_state_path = Path(paper_state_path)
    config_error = None
    try:
        config_data = load_paper_broker_config(config_path)
    except Exception as exc:
        config_data = {"paper_broker": {}}
        config_error = f"{exc.__class__.__name__}: {exc}"
    section = config_data.get("paper_broker") or {}
    provider = str(section.get("provider", "local_sandbox"))
    adapter_status = paper_broker_status
    snapshot = external_snapshot
    if adapter_status is None or snapshot is None:
        adapter = build_paper_broker_adapter(PaperBroker.load(paper_state_path), config=config_data)
        adapter_status = adapter_status or adapter.status()
        snapshot = snapshot or adapter.external_snapshot()

    checks = [
        _check_config_safety(config_path=config_path, provider=provider, section=section, config_error=config_error),
        _check_adapter_safety(adapter_status),
        _check_active_paper_execution(adapter_status),
        _check_external_account_sync(provider, adapter_status, snapshot),
        _check_external_order_submission(provider, adapter_status),
    ]
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    status = "fail" if fail_count else ("warn" if warn_count else "pass")
    external_e2e_ready = _external_paper_e2e_ready(provider, adapter_status, snapshot)
    local_sandbox_ready = provider == "local_sandbox" and _bool(adapter_status.get("paper_order_submission_enabled"))
    return {
        "status": status,
        "status_zh": _status_zh(status),
        "overall_status": _overall_status(provider, fail_count=fail_count, warn_count=warn_count, external_e2e_ready=external_e2e_ready),
        "overall_status_zh": _overall_status_zh(provider, fail_count=fail_count, warn_count=warn_count, external_e2e_ready=external_e2e_ready),
        "generated_at": _utc_now_iso(),
        "provider": provider,
        "provider_zh": adapter_status.get("provider_zh") or _provider_zh(provider),
        "local_sandbox_ready": local_sandbox_ready,
        "local_sandbox_ready_zh": "是" if local_sandbox_ready else "否",
        "external_paper_e2e_ready": external_e2e_ready,
        "external_paper_e2e_ready_zh": "是" if external_e2e_ready else "否",
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": warn_count,
        "fail_count": fail_count,
        "checks": checks,
        "paper_broker_status": _public_status(adapter_status),
        "external_snapshot_summary": _external_snapshot_summary(snapshot),
        "safety_boundary": {
            "live_order_submission_enabled": False,
            "supports_real_broker_place_order": False,
            "message_zh": "纸面交易提供方预检不会启用真实资金下单；外部提供方也必须保持纸面交易端点、纸面模式和凭据隔离。",
        },
        "summary_zh": _summary_zh(provider, fail_count=fail_count, warn_count=warn_count, external_e2e_ready=external_e2e_ready),
    }


def format_paper_broker_readiness_summary_zh(report: dict) -> str:
    lines = [
        "Alpha 纸面交易提供方预检",
        f"总体状态：{report.get('overall_status_zh', '未知')}",
        f"生成时间：{report.get('generated_at', '无')}",
        f"当前提供方：{report.get('provider_zh', '未知')}",
        f"本地沙盒可用：{report.get('local_sandbox_ready_zh', '否')}",
        f"外部纸面账户端到端验证：{report.get('external_paper_e2e_ready_zh', '否')}",
        f"通过/关注/失败：{report.get('pass_count', 0)} / {report.get('warn_count', 0)} / {report.get('fail_count', 0)}",
        f"结论：{report.get('summary_zh', '无')}",
        "检查项：",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知检查')}：{check.get('status_zh', '未知')} - {check.get('message_zh', '')}")
    return "\n".join(lines)


def write_paper_broker_readiness_report(report: dict, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "written", "status_zh": "已写入", "path": str(path), "file_size_bytes": path.stat().st_size}


def _check_config_safety(*, config_path: Path, provider: str, section: dict, config_error: str | None) -> dict:
    safety = section.get("safety") or {}
    evidence = {
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "provider": provider,
        "allow_external_paper_api": _bool(section.get("allow_external_paper_api")),
        "live_order_submission_enabled": _bool(safety.get("live_order_submission_enabled")),
        "require_paper_mode": safety.get("require_paper_mode", True) is True,
        "config_error": config_error,
    }
    if config_error:
        return _check("paper_broker_config", "纸面交易配置", "fail", "纸面交易提供方配置无法读取。", evidence)
    if evidence["live_order_submission_enabled"]:
        return _check("paper_broker_config", "纸面交易配置", "fail", "纸面交易配置错误启用了真实资金下单。", evidence)
    if not evidence["require_paper_mode"]:
        return _check("paper_broker_config", "纸面交易配置", "fail", "纸面交易配置没有强制纸面模式。", evidence)
    return _check("paper_broker_config", "纸面交易配置", "pass", "纸面交易配置保持纸面模式和真实下单禁用。", evidence)


def _check_adapter_safety(status: dict) -> dict:
    evidence = {
        "provider": status.get("provider"),
        "mode": status.get("mode"),
        "adapter_readiness": status.get("adapter_readiness"),
        "live_order_submission_enabled": status.get("live_order_submission_enabled"),
        "supports_real_broker_place_order": status.get("supports_real_broker_place_order"),
    }
    if status.get("live_order_submission_enabled") or status.get("supports_real_broker_place_order"):
        return _check("paper_adapter_safety", "适配器安全边界", "fail", "纸面交易适配器暴露了真实下单能力。", evidence)
    if status.get("mode") != "paper":
        return _check("paper_adapter_safety", "适配器安全边界", "fail", "纸面交易适配器没有声明纸面模式。", evidence)
    return _check("paper_adapter_safety", "适配器安全边界", "pass", "适配器保持纸面模式，且不支持真实资金下单。", evidence)


def _check_active_paper_execution(status: dict) -> dict:
    evidence = {
        "provider": status.get("provider"),
        "provider_zh": status.get("provider_zh"),
        "adapter_readiness": status.get("adapter_readiness"),
        "connected": status.get("connected"),
        "paper_order_submission_enabled": status.get("paper_order_submission_enabled"),
        "supports_market_orders": status.get("supports_market_orders"),
        "execution_model_zh": status.get("execution_model_zh"),
    }
    if status.get("adapter_readiness") == "ready" and status.get("paper_order_submission_enabled") and status.get("supports_market_orders"):
        return _check("active_paper_execution", "当前纸面成交能力", "pass", "当前提供方可执行纸面订单，且只处于纸面模式。", evidence)
    return _check("active_paper_execution", "当前纸面成交能力", "fail", "当前提供方不能执行纸面订单；请回退本地沙盒或完成外部 paper 配置。", evidence)


def _check_external_account_sync(provider: str, status: dict, snapshot: dict) -> dict:
    evidence = {
        "provider": provider,
        "read_only_sync_enabled": status.get("read_only_sync_enabled"),
        "read_only_sync_ready": status.get("read_only_sync_ready"),
        "snapshot_status": snapshot.get("status"),
        "position_count": snapshot.get("position_count", 0),
        "recent_order_count": snapshot.get("recent_order_count", 0),
        "summary_zh": snapshot.get("summary_zh"),
    }
    if provider == "local_sandbox":
        return _check("external_paper_account_sync", "外部纸面账户同步", "warn", "当前使用本地沙盒；外部纸面账户端到端验证尚未接入，不阻断 6月15日本地模拟交易交付。", evidence)
    if status.get("read_only_sync_ready") and snapshot.get("status") == "ready":
        return _check("external_paper_account_sync", "外部纸面账户同步", "pass", "外部纸面账户只读同步已完成，且返回结果已脱敏。", evidence)
    return _check("external_paper_account_sync", "外部纸面账户同步", "fail", "外部纸面交易提供方已被选择，但账户只读同步未就绪。", evidence)


def _check_external_order_submission(provider: str, status: dict) -> dict:
    evidence = {
        "provider": provider,
        "paper_order_submission_enabled": status.get("paper_order_submission_enabled"),
        "paper_base_url_allowed": status.get("paper_base_url_allowed"),
        "credentials_present": status.get("credentials_present"),
        "live_order_submission_enabled": status.get("live_order_submission_enabled"),
    }
    if provider == "local_sandbox":
        return _check("external_paper_order_submission", "外部纸面下单端到端验证", "warn", "当前外部纸面下单端到端验证未启用；本地沙盒模拟成交仍可运行。", evidence)
    if status.get("paper_order_submission_enabled") and status.get("paper_base_url_allowed") is not False and not status.get("live_order_submission_enabled"):
        return _check("external_paper_order_submission", "外部纸面下单端到端验证", "pass", "外部纸面下单开关、纸面交易端点和真实下单禁用边界均通过。", evidence)
    return _check("external_paper_order_submission", "外部纸面下单端到端验证", "fail", "外部纸面交易提供方已被选择，但纸面下单端到端验证未就绪。", evidence)


def _check(check_id: str, title_zh: str, status: str, message_zh: str, evidence: dict | None = None) -> dict:
    return {
        "id": check_id,
        "title_zh": title_zh,
        "status": status,
        "status_zh": _status_zh(status),
        "message_zh": message_zh,
        "evidence": evidence or {},
    }


def _status_zh(status: str) -> str:
    return {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(status, "未知")


def _overall_status(provider: str, *, fail_count: int, warn_count: int, external_e2e_ready: bool) -> str:
    if fail_count:
        return "blocked"
    if external_e2e_ready:
        return "external_paper_ready"
    if provider == "local_sandbox":
        return "local_paper_ready_external_pending"
    if warn_count:
        return "needs_attention"
    return "ready"


def _overall_status_zh(provider: str, *, fail_count: int, warn_count: int, external_e2e_ready: bool) -> str:
    if fail_count:
        return "不可用"
    if external_e2e_ready:
        return "外部纸面账户就绪"
    if provider == "local_sandbox":
        return "本地模拟可用，外部纸面账户待接入"
    if warn_count:
        return "需关注"
    return "就绪"


def _summary_zh(provider: str, *, fail_count: int, warn_count: int, external_e2e_ready: bool) -> str:
    if fail_count:
        return "纸面交易提供方预检失败；不能把当前提供方作为成熟自动模拟交易交付。"
    if external_e2e_ready:
        return "外部纸面账户只读同步和纸面下单门槛均通过，真实下单仍保持禁用。"
    if provider == "local_sandbox":
        return "本地沙盒模拟交易可用于 6月15日自动模拟交易；外部纸面账户端到端验证仍是下一阶段缺口。"
    if warn_count:
        return "纸面交易提供方可观察运行，但仍有关注项。"
    return "纸面交易提供方预检通过。"


def _external_paper_e2e_ready(provider: str, status: dict, snapshot: dict) -> bool:
    if provider == "local_sandbox":
        return False
    return bool(
        status.get("paper_order_submission_enabled")
        and status.get("paper_base_url_allowed") is not False
        and status.get("live_order_submission_enabled") is False
        and status.get("supports_real_broker_place_order") is False
        and snapshot.get("status") == "ready"
    )


def _public_status(status: dict) -> dict:
    safe = dict(status)
    for key in ("credential_source", "key_id", "secret_key", "api_secret", "account_number", "account_id"):
        safe.pop(key, None)
    return safe


def _external_snapshot_summary(snapshot: dict) -> dict:
    return {
        "status": snapshot.get("status"),
        "status_zh": snapshot.get("status_zh"),
        "provider": snapshot.get("provider"),
        "provider_zh": snapshot.get("provider_zh"),
        "read_only_sync_enabled": snapshot.get("read_only_sync_enabled"),
        "read_only_sync_enabled_zh": snapshot.get("read_only_sync_enabled_zh"),
        "position_count": snapshot.get("position_count", 0),
        "recent_order_count": snapshot.get("recent_order_count", 0),
        "live_order_submission_enabled": snapshot.get("live_order_submission_enabled"),
        "live_order_submission_enabled_zh": snapshot.get("live_order_submission_enabled_zh"),
        "summary_zh": snapshot.get("summary_zh"),
    }


def _provider_zh(provider: str) -> str:
    return {
        "local_sandbox": "本地沙盒模拟交易",
        "alpaca_paper": "Alpaca 纸面交易 API",
        "ibkr_paper": "IBKR 纸面交易 API",
        "moomoo_paper": "富途牛牛纸面交易 API",
        "external_paper_api": "外部纸面交易 API",
    }.get(provider, "未知纸面交易提供方")


def _bool(value: Any) -> bool:
    return bool(value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 Alpha 纸面交易提供方就绪状态。")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON；默认输出中文摘要。")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="JSON 报告输出路径。")
    args = parser.parse_args()
    report = collect_paper_broker_readiness()
    write_result = write_paper_broker_readiness_report(report, args.output)
    report["write_result"] = write_result
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_paper_broker_readiness_summary_zh(report))
        print(f"报告路径：{write_result['path']}")
    raise SystemExit(0 if report["status"] != "fail" else 1)


if __name__ == "__main__":
    main()
