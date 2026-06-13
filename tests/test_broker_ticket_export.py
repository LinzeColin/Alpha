from datetime import datetime, timedelta, timezone

from backend.app.services.broker_ticket_export import build_broker_ready_order_export, format_broker_ready_order_csv


def _reviewed_ticket(expires_delta_seconds: int = 300) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = (now + timedelta(seconds=expires_delta_seconds)).isoformat()
    return {
        "ticket_id": "ticket_export",
        "status": "owner_reviewed",
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "broker_payload": {
            "symbol": "TLT",
            "side": "buy",
            "quantity": 1.0,
            "order_type": "market",
            "time_in_force": "day",
            "estimated_price": 91.95,
            "client_order_id": "run_1:momentum_TLT_20d:TLT:buy:1",
        },
        "intent": {
            "estimated_notional_aud": 91.95,
            "expires_at": expires_at,
            "strategy_id": "momentum_TLT_20d",
        },
        "risk_check": {"allowed": True, "status": "approved_for_owner_review", "reason": "pre-trade risk checks passed"},
        "owner_review": {"status": "owner_reviewed", "actor_id": "owner_dashboard", "reviewed_at": now.isoformat()},
    }


def test_broker_ready_order_export_package_is_manual_and_chinese_readable():
    package = build_broker_ready_order_export(_reviewed_ticket())

    assert package["schema_version"] == "2026-06-13.v1"
    assert package["manual_entry_allowed"] is True
    assert package["manual_entry_allowed_zh"] == "是"
    assert package["live_order_submission_enabled"] is False
    assert package["submission_mode_zh"] == "仅供所有者在经纪商系统中人工确认录入"
    assert package["safety_message_zh"] == "该工单只用于人工复核和手动录入，不会通过 Alpha 自动提交真实资金订单。"
    assert package["broker_payload_zh"]["side_zh"] == "买入"
    assert package["broker_payload_zh"]["order_type_zh"] == "市价单"
    assert package["broker_payload_zh"]["time_in_force_zh"] == "当日有效"
    assert package["risk_check_zh"]["reason_zh"] == "下单前风控检查通过"
    assert package["csv_row"]["symbol"] == "TLT"
    assert package["csv_row"]["live_order_submission_enabled"] is False


def test_broker_ready_order_export_blocks_expired_ticket():
    package = build_broker_ready_order_export(_reviewed_ticket(expires_delta_seconds=-1))

    assert package["manual_entry_allowed"] is False
    assert package["blocked_reason"] == "expired_ticket_cannot_be_owner_reviewed_or_exported"
    assert package["blocked_reason_zh"] == "工单已过期，不能复核或导出"


def test_broker_ready_order_csv_contains_single_manual_order_row():
    package = build_broker_ready_order_export(_reviewed_ticket())
    csv_text = format_broker_ready_order_csv(package)

    assert "ticket_id,symbol,side,quantity,order_type,time_in_force" in csv_text
    assert "ticket_export,TLT,buy,1.0,market,day,91.95,91.95" in csv_text
    assert "manual_owner_broker_confirmation_only" in csv_text
