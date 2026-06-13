from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


REQUIRED_DASHBOARD_TEXT = [
    "Alpha 控制台",
    "运行模拟交易周期",
    "生成运行备份",
    "刷新公共行情",
    "系统快照",
    "纸面交易提供方",
    "允许纸面下单",
    "外部账户同步",
    "同步说明",
    "长运行预检",
    "长运行历史",
    "审批队列",
    "富途牛牛开放网关（只读）",
]

BANNED_DASHBOARD_TEXT = [
    "Alpha Dashboard",
    "Run Paper Cycle",
    "System Snapshot",
    "Approval Queue",
    "<th>Adapter</th>",
    "Broker-ready",
]

REQUIRED_STATE_FIELDS = [
    ("health", "status_zh"),
    ("market_data", "source_kind_zh"),
    ("paper_broker_status", "mode_zh"),
    ("paper_broker_status", "provider_zh"),
    ("paper_broker_status", "adapter_readiness_zh"),
    ("paper_broker_status", "paper_order_submission_enabled_zh"),
    ("paper_broker_status", "live_order_submission_enabled_zh"),
    ("paper_broker_external_snapshot", "status_zh"),
    ("paper_broker_external_snapshot", "provider_zh"),
    ("paper_broker_external_snapshot", "summary_zh"),
    ("paper_broker_external_snapshot", "live_order_submission_enabled_zh"),
    ("moomoo_broker_status", "mode_zh"),
    ("soak_readiness", "summary_zh"),
    ("soak_readiness_history", "summary_zh"),
    ("owner_summary", "message_zh"),
]

REQUIRED_DASHBOARD_ENDPOINT_REFERENCES = [
    "/dashboard/state",
    "/paper/run-once",
    "/ops/backup",
    "/market-data/refresh",
    "/orders/approval-queue/",
    "owner-review",
    "reject",
    "mark-exported",
    "/broker-ticket/view",
    "/broker-ticket.csv",
]

REQUIRED_LAYOUT_CONTRACTS = [
    ("全局盒模型", "* { box-sizing: border-box;"),
    ("页面禁止整体横向溢出", "overflow-x: hidden;"),
    ("顶部栏允许换行", "flex-wrap: wrap;"),
    ("按钮组可换行", ".header-actions { display: flex; flex-wrap: wrap;"),
    ("卡片局部横向滚动", "section { background: #ffffff; border: 1px solid #d8ddd2; border-radius: 8px; padding: 16px; min-width: 0; overflow-x: auto;"),
    ("宽表格稳定最小宽度", "table { width: 100%; min-width: 620px;"),
    ("表格单元格允许断词", "overflow-wrap: anywhere;"),
    ("移动端断点", "@media (max-width: 720px)"),
    ("移动端单列内容网格", ".grid-two { grid-template-columns: minmax(0, 1fr);"),
    ("移动端按钮可伸缩", ".header-actions button { flex: 1 1 140px;"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 Alpha 控制台 HTTP 中文显示和安全边界。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Alpha API 根地址。")
    parser.add_argument("--timeout", type=float, default=10.0, help="单个 HTTP 请求超时秒数。")
    parser.add_argument(
        "--exercise-actions",
        action="store_true",
        help="实际调用安全的控制台动作端点：模拟交易周期和运行备份。",
    )
    args = parser.parse_args()

    errors: list[str] = []
    payload: dict[str, Any] = {"base_url": args.base_url.rstrip("/")}
    action_results: dict[str, dict] = {}
    base_url = str(payload["base_url"])

    try:
        health = _get_json(f"{base_url}/health", timeout=args.timeout)
        dashboard_html = _get_text(f"{base_url}/dashboard", timeout=args.timeout)
        state = _get_json(f"{base_url}/dashboard/state", timeout=args.timeout)
    except Exception as exc:
        errors.append(f"HTTP 读取失败：{exc}")
        health = {}
        dashboard_html = ""
        state = {}

    errors.extend(validate_dashboard_payloads(health=health, dashboard_html=dashboard_html, state=state))
    if args.exercise_actions and not errors:
        try:
            action_results = exercise_safe_dashboard_actions(base_url=base_url, timeout=args.timeout)
        except Exception as exc:
            errors.append(f"控制台安全动作调用失败：{exc}")
        else:
            errors.extend(validate_safe_action_results(action_results))
    report = {
        **payload,
        "status": "pass" if not errors else "fail",
        "status_zh": "通过" if not errors else "失败",
        "checked_dashboard_text_count": len(REQUIRED_DASHBOARD_TEXT),
        "checked_endpoint_reference_count": len(REQUIRED_DASHBOARD_ENDPOINT_REFERENCES),
        "checked_layout_contract_count": len(REQUIRED_LAYOUT_CONTRACTS),
        "checked_state_field_count": len(REQUIRED_STATE_FIELDS),
        "exercised_action_count": len(action_results),
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


def validate_dashboard_payloads(*, health: dict, dashboard_html: str, state: dict) -> list[str]:
    errors: list[str] = []

    if health.get("status") != "ok":
        errors.append("健康接口未返回 status=ok。")
    if health.get("status_zh") != "正常":
        errors.append("健康接口未返回中文状态“正常”。")
    if health.get("live_trading_enabled") is not False:
        errors.append("健康接口没有明确禁用真实交易。")

    for text in REQUIRED_DASHBOARD_TEXT:
        if text not in dashboard_html:
            errors.append(f"控制台缺少中文文案：{text}")
    for text in BANNED_DASHBOARD_TEXT:
        if text in dashboard_html:
            errors.append(f"控制台仍包含旧英文文案：{text}")
    for endpoint in REQUIRED_DASHBOARD_ENDPOINT_REFERENCES:
        if endpoint not in dashboard_html:
            errors.append(f"控制台缺少交互端点引用：{endpoint}")
    for label, css in REQUIRED_LAYOUT_CONTRACTS:
        if css not in dashboard_html:
            errors.append(f"控制台缺少布局规则：{label}")

    refresh_interval = health.get("refresh_interval_seconds")
    if refresh_interval != 300:
        errors.append(f"健康接口刷新间隔不是 300 秒：{refresh_interval}")

    for section, key in REQUIRED_STATE_FIELDS:
        value = (state.get(section) or {}).get(key)
        if value in (None, ""):
            errors.append(f"状态接口缺少中文字段：{section}.{key}")

    paper_broker = state.get("paper_broker_status") or {}
    if paper_broker.get("live_order_submission_enabled") is not False:
        errors.append("模拟经纪商状态没有明确禁用真实下单。")
    if paper_broker.get("supports_real_broker_place_order") is not False:
        errors.append("模拟经纪商状态没有明确禁止真实经纪商下单。")

    external_snapshot = state.get("paper_broker_external_snapshot") or {}
    if external_snapshot.get("live_order_submission_enabled") is not False:
        errors.append("外部纸面账户同步状态没有明确禁用真实下单。")
    account_snapshot = external_snapshot.get("account") or {}
    if "id" in account_snapshot or "account_number" in account_snapshot:
        errors.append("外部纸面账户同步状态不应暴露账户原始标识。")

    moomoo = state.get("moomoo_broker_status") or {}
    if moomoo.get("live_order_submission_enabled") is not False:
        errors.append("富途牛牛开放网关状态没有明确禁用真实下单。")
    if moomoo.get("trade_context_enabled") is not False:
        errors.append("富途牛牛开放网关状态不应启用交易上下文。")
    if moomoo.get("supports_real_broker_place_order") is not False:
        errors.append("富途牛牛开放网关状态没有明确禁止真实经纪商下单。")

    soak_history = state.get("soak_readiness_history") or {}
    safety = soak_history.get("safety_boundary") or {}
    if safety.get("live_order_submission_enabled") is not False:
        errors.append("长运行历史安全边界没有明确禁用真实下单。")

    return errors


def exercise_safe_dashboard_actions(*, base_url: str, timeout: float) -> dict[str, dict]:
    return {
        "paper_run_once": _post_json(f"{base_url}/paper/run-once", timeout=timeout),
        "ops_backup": _post_json(f"{base_url}/ops/backup", timeout=timeout),
    }


def validate_safe_action_results(action_results: dict[str, dict]) -> list[str]:
    errors: list[str] = []

    paper_result = action_results.get("paper_run_once") or {}
    if paper_result.get("status") != "completed":
        errors.append("模拟交易周期动作未返回 completed。")
    if ((paper_result.get("paper_broker_adapter") or {}).get("live_order_submission_enabled")) is not False:
        errors.append("模拟交易周期动作没有明确禁用真实下单。")
    approval_ticket = ((paper_result.get("approval_queue") or {}).get("ticket") or {})
    if approval_ticket.get("status") != "pending_owner_approval":
        errors.append("模拟交易周期动作没有生成待人工确认候选单。")
    if approval_ticket.get("status_zh") != "待人工确认":
        errors.append("模拟交易周期动作没有返回中文候选单状态。")

    backup_result = action_results.get("ops_backup") or {}
    if backup_result.get("status") != "completed":
        errors.append("运行备份动作未返回 completed。")
    health_after_backup = backup_result.get("health_after_backup") or {}
    safety = health_after_backup.get("safety_boundary") or {}
    if safety.get("live_order_submission_enabled") is not False:
        errors.append("运行备份后的健康报告没有明确禁用真实下单。")
    if not backup_result.get("backup_path"):
        errors.append("运行备份动作未返回备份路径。")

    return errors


def _get_text(url: str, *, timeout: float) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url}：{exc}") from exc


def _get_json(url: str, *, timeout: float) -> dict:
    text = _get_text(url, timeout=timeout)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError(f"{url}：响应不是 JSON object")
    return value


def _post_json(url: str, *, timeout: float) -> dict:
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url}：{exc}") from exc
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError(f"{url}：响应不是 JSON object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
