from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api import routes  # noqa: E402


REQUIRED_STATIC_TEXT = [
    "Alpha 控制台",
    "运行模拟交易周期",
    "系统快照",
    "智能体运行状态",
    "模拟交易状态（模拟交易执行层）",
    "富途牛牛开放网关（只读）",
    "行情数据",
    "运行健康",
    "交付就绪",
    "长运行预检",
    "长运行历史",
    "策略锦标赛",
    "策略迭代历史",
    "审批队列",
    "生成运行备份",
    "刷新公共行情",
    "标记已复核",
    "下载工单表格",
]

BANNED_UI_PHRASES = [
    "Alpha Dashboard",
    "Run Paper Cycle",
    "System Snapshot",
    "Approval Queue",
    "Broker-ready",
    "broker-ready",
    "No pending tickets",
    "Moomoo OpenD",
    "<th>Adapter</th>",
    " bps",
]

REQUIRED_STATE_KEYS = [
    ("health", "status_zh"),
    ("health", "mode_zh"),
    ("market_data", "source_kind_zh"),
    ("market_data", "real_market_data_zh"),
    ("ops_health", "overall_status_zh"),
    ("paper_readiness", "summary_zh"),
    ("soak_readiness", "summary_zh"),
    ("soak_readiness_history", "summary_zh"),
    ("owner_summary", "system_mode_zh"),
    ("paper_broker_status", "mode_zh"),
    ("paper_broker_status", "live_order_submission_enabled_zh"),
    ("moomoo_broker_status", "mode_zh"),
    ("moomoo_quote_snapshot", "mode_zh"),
    ("strategy_journal", "status_zh"),
]


def main() -> int:
    html = routes.dashboard()
    errors: list[str] = []

    for text in REQUIRED_STATIC_TEXT:
        if text not in html:
            errors.append(f"缺少静态中文文案：{text}")

    for phrase in BANNED_UI_PHRASES:
        if phrase in html:
            errors.append(f"发现禁止的英文界面文案：{phrase}")

    state = routes.dashboard_state()
    for section, key in REQUIRED_STATE_KEYS:
        value = (state.get(section) or {}).get(key)
        if value in (None, ""):
            errors.append(f"状态接口缺少中文字段：{section}.{key}")

    queue = state.get("approval_queue") or {}
    for ticket in queue.get("tickets") or []:
        if not ticket.get("status_zh"):
            errors.append(f"候选单缺少中文状态：{ticket.get('ticket_id')}")
        freshness = ticket.get("freshness") or {}
        if not freshness.get("status_zh"):
            errors.append(f"候选单缺少中文时效状态：{ticket.get('ticket_id')}")

    report = {
        "status": "pass" if not errors else "fail",
        "status_zh": "通过" if not errors else "失败",
        "checked_static_text_count": len(REQUIRED_STATIC_TEXT),
        "checked_state_key_count": len(REQUIRED_STATE_KEYS),
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
