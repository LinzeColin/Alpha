from __future__ import annotations

import csv
from datetime import datetime, timezone
from html import escape
from io import StringIO

from backend.app.services.approval_queue import annotate_ticket_freshness
from backend.app.services.display_locale import zh_order_type, zh_reason, zh_side, zh_status, zh_time_in_force


BROKER_TICKET_EXPORT_SCHEMA_VERSION = "2026-06-13.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_broker_ready_order_export(
    ticket: dict,
    *,
    broker_profile: str = "generic_manual_broker_entry",
    generated_by: str = "alpha_dashboard",
) -> dict:
    annotated = annotate_ticket_freshness(ticket)
    broker_payload = annotated.get("broker_payload") or {}
    intent = annotated.get("intent") or {}
    risk_check = annotated.get("risk_check") or {}
    status = str(annotated.get("status", "unknown"))
    freshness = annotated.get("freshness") or {}
    manual_entry_allowed, blocked_reason = _manual_entry_gate(status=status, freshness=freshness, risk_check=risk_check)
    csv_row = _csv_row(
        ticket=annotated,
        broker_payload=broker_payload,
        intent=intent,
        manual_entry_allowed=manual_entry_allowed,
        blocked_reason=blocked_reason,
    )
    return {
        "schema_version": BROKER_TICKET_EXPORT_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "generated_by": generated_by,
        "broker_profile": broker_profile,
        "ticket_id": annotated.get("ticket_id"),
        "status": status,
        "status_zh": zh_status(status),
        "actionability": annotated.get("actionability"),
        "actionability_zh": zh_status(annotated.get("actionability")),
        "created_at": annotated.get("created_at"),
        "expires_at": annotated.get("expires_at") or intent.get("expires_at"),
        "freshness": freshness,
        "freshness_zh": zh_status(freshness.get("status")),
        "manual_entry_allowed": manual_entry_allowed,
        "manual_entry_allowed_zh": "是" if manual_entry_allowed else "否",
        "blocked_reason": blocked_reason,
        "blocked_reason_zh": zh_reason(blocked_reason),
        "live_order_submission_enabled": False,
        "submission_mode": "manual_owner_broker_confirmation_only",
        "submission_mode_zh": "仅供所有者在经纪商系统中人工确认录入",
        "safety_message_zh": "该工单只用于人工复核和手动录入，不会通过 Alpha 自动提交真实资金订单。",
        "broker_payload": broker_payload,
        "broker_payload_zh": _broker_payload_zh(broker_payload),
        "manual_entry_fields": _manual_entry_fields(broker_payload, intent),
        "csv_row": csv_row,
        "risk_check": risk_check,
        "risk_check_zh": {
            "status_zh": zh_status(risk_check.get("status")),
            "reason_zh": zh_reason(risk_check.get("reason")),
            "allowed_zh": "是" if risk_check.get("allowed") else "否",
        },
        "intent": intent,
        "owner_review": annotated.get("owner_review"),
        "broker_ticket_export": annotated.get("broker_ticket_export"),
    }


def format_broker_ready_order_csv(export_package: dict) -> str:
    buffer = StringIO()
    row = export_package.get("csv_row") or {}
    payload_zh = export_package.get("broker_payload_zh") or {}
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "工单号",
            "标的",
            "方向",
            "数量",
            "订单类型",
            "有效期",
            "参考价格",
            "参考名义金额",
            "客户订单号",
            "过期时间",
            "允许人工录入",
            "阻止原因",
            "允许真实下单",
            "提交方式",
        ]
    )
    writer.writerow(
        [
            row.get("ticket_id"),
            row.get("symbol"),
            payload_zh.get("side_zh") or zh_side(row.get("side")),
            row.get("quantity"),
            payload_zh.get("order_type_zh") or zh_order_type(row.get("order_type")),
            payload_zh.get("time_in_force_zh") or zh_time_in_force(row.get("time_in_force")),
            row.get("estimated_price"),
            row.get("estimated_notional_aud"),
            row.get("client_order_id"),
            row.get("expires_at"),
            export_package.get("manual_entry_allowed_zh") or ("是" if row.get("manual_entry_allowed") else "否"),
            export_package.get("blocked_reason_zh") or "无",
            "是" if row.get("live_order_submission_enabled") else "否",
            export_package.get("submission_mode_zh") or "仅供所有者在经纪商系统中人工确认录入",
        ]
    )
    return buffer.getvalue()


def format_broker_ready_order_html_zh(export_package: dict) -> str:
    manual_fields = export_package.get("manual_entry_fields") or []
    field_rows = "\n".join(
        "<tr>"
        f"<th>{_html(field.get('label_zh'))}</th>"
        f"<td>{_html(field.get('display_zh'))}</td>"
        "</tr>"
        for field in manual_fields
    )
    risk_check = export_package.get("risk_check_zh") or {}
    status_kind = "ok" if export_package.get("manual_entry_allowed") else "warn"
    blocked_reason = export_package.get("blocked_reason_zh") or "无"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alpha 工单详情</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f5f6f3; color: #1d1f21; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 24px; display: grid; gap: 16px; }}
    header, section {{ background: #ffffff; border: 1px solid #d8ddd2; border-radius: 8px; padding: 16px; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    h2 {{ margin: 0 0 12px; font-size: 15px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid #eceee8; text-align: left; vertical-align: top; }}
    th {{ width: 180px; color: #5c6258; font-size: 12px; letter-spacing: 0; }}
    .pill {{ display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }}
    .ok {{ background: #e6f5ec; color: #176c3a; }}
    .warn {{ background: #fff3d6; color: #8a5b00; }}
    .muted {{ color: #6a7166; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Alpha 经纪商就绪工单</h1>
      <div class="muted">该页面只用于人工复核与手动录入，不会通过 Alpha 自动提交真实资金订单。</div>
    </header>
    <section>
      <h2>工单状态</h2>
      <table>
        <tbody>
          <tr><th>工单号</th><td>{_html(export_package.get("ticket_id"))}</td></tr>
          <tr><th>状态</th><td>{_html(export_package.get("status_zh"))}</td></tr>
          <tr><th>可操作性</th><td>{_html(export_package.get("actionability_zh"))}</td></tr>
          <tr><th>时效性</th><td>{_html(export_package.get("freshness_zh"))}</td></tr>
          <tr><th>允许人工录入</th><td><span class="pill {status_kind}">{_html(export_package.get("manual_entry_allowed_zh"))}</span></td></tr>
          <tr><th>阻止原因</th><td>{_html(blocked_reason)}</td></tr>
          <tr><th>真实下单</th><td>否</td></tr>
          <tr><th>生成时间</th><td>{_html(export_package.get("generated_at"))}</td></tr>
          <tr><th>过期时间</th><td>{_html(export_package.get("expires_at"))}</td></tr>
        </tbody>
      </table>
    </section>
    <section>
      <h2>人工录入字段</h2>
      <table><tbody>{field_rows or '<tr><td class="muted">暂无字段</td></tr>'}</tbody></table>
    </section>
    <section>
      <h2>风控结果</h2>
      <table>
        <tbody>
          <tr><th>状态</th><td>{_html(risk_check.get("status_zh"))}</td></tr>
          <tr><th>原因</th><td>{_html(risk_check.get("reason_zh"))}</td></tr>
          <tr><th>允许进入人工复核</th><td>{_html(risk_check.get("allowed_zh"))}</td></tr>
        </tbody>
      </table>
    </section>
    <section>
      <h2>安全说明</h2>
      <table>
        <tbody>
          <tr><th>提交方式</th><td>{_html(export_package.get("submission_mode_zh"))}</td></tr>
          <tr><th>说明</th><td>{_html(export_package.get("safety_message_zh"))}</td></tr>
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def _manual_entry_gate(*, status: str, freshness: dict, risk_check: dict) -> tuple[bool, str | None]:
    if status == "blocked_by_risk" or not risk_check.get("allowed", False):
        return False, "risk_blocked_ticket_cannot_be_owner_reviewed_or_exported"
    if freshness.get("status") != "fresh":
        return False, "expired_ticket_cannot_be_owner_reviewed_or_exported"
    if status not in {"owner_reviewed", "broker_ticket_exported"}:
        return False, "ticket_must_be_owner_reviewed_before_export"
    return True, None


def _html(value: object) -> str:
    if value is None or value == "":
        return "无"
    return escape(str(value), quote=True)


def _broker_payload_zh(payload: dict) -> dict:
    return {
        "symbol": payload.get("symbol"),
        "side_zh": zh_side(payload.get("side")),
        "quantity": payload.get("quantity"),
        "order_type_zh": zh_order_type(payload.get("order_type")),
        "time_in_force_zh": zh_time_in_force(payload.get("time_in_force")),
        "estimated_price": payload.get("estimated_price"),
        "client_order_id": payload.get("client_order_id"),
    }


def _manual_entry_fields(payload: dict, intent: dict) -> list[dict]:
    fields = [
        ("标的", "symbol", payload.get("symbol")),
        ("方向", "side", payload.get("side"), zh_side(payload.get("side"))),
        ("数量", "quantity", payload.get("quantity")),
        ("订单类型", "order_type", payload.get("order_type"), zh_order_type(payload.get("order_type"))),
        ("有效期", "time_in_force", payload.get("time_in_force"), zh_time_in_force(payload.get("time_in_force"))),
        ("参考价格", "estimated_price", payload.get("estimated_price")),
        ("参考名义金额", "estimated_notional_aud", intent.get("estimated_notional_aud")),
        ("客户订单号", "client_order_id", payload.get("client_order_id")),
    ]
    rows = []
    for item in fields:
        label_zh, key, value, *display = item
        rows.append(
            {
                "label_zh": label_zh,
                "key": key,
                "value": value,
                "display_zh": display[0] if display else str(value) if value is not None else "无",
            }
        )
    return rows


def _csv_row(*, ticket: dict, broker_payload: dict, intent: dict, manual_entry_allowed: bool, blocked_reason: str | None) -> dict:
    return {
        "ticket_id": ticket.get("ticket_id"),
        "symbol": broker_payload.get("symbol"),
        "side": broker_payload.get("side"),
        "quantity": broker_payload.get("quantity"),
        "order_type": broker_payload.get("order_type"),
        "time_in_force": broker_payload.get("time_in_force"),
        "estimated_price": broker_payload.get("estimated_price"),
        "estimated_notional_aud": intent.get("estimated_notional_aud"),
        "client_order_id": broker_payload.get("client_order_id"),
        "expires_at": ticket.get("expires_at") or intent.get("expires_at"),
        "manual_entry_allowed": manual_entry_allowed,
        "blocked_reason": blocked_reason or "",
        "live_order_submission_enabled": False,
        "submission_mode": "manual_owner_broker_confirmation_only",
    }
