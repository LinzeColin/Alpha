from pathlib import Path

from backend.app.services.paper_maturity import (
    format_paper_trading_maturity_summary_zh,
    run_paper_trading_maturity_check,
    write_paper_trading_maturity_report,
)


def test_paper_trading_maturity_check_covers_cycles_rebalance_and_safety_boundary():
    report = run_paper_trading_maturity_check(root=Path("."), cycles=3)

    assert report["status"] == "pass"
    assert report["overall_status_zh"] == "成熟可用"
    assert report["cycle_count"] == 3
    assert report["fail_count"] == 0
    assert report["pass_count"] == report["check_count"]
    assert report["normal_cycles"]["cycle_count"] == 3
    assert report["normal_cycles"]["risk_allowed_count"] == 3
    assert report["normal_cycles"]["queued_count"] == 3
    assert report["normal_cycles"]["filled_count"] == 3
    assert report["normal_cycles"]["broker_ready_ticket_count"] == 3
    assert report["normal_cycles"]["readiness_overall_status"] == "healthy"
    assert len(report["cycle_chain_matrix"]["normal_cycles"]) == 3
    assert all(row["status"] == "pass" for row in report["cycle_chain_matrix"]["normal_cycles"])
    first_cycle = report["cycle_chain_matrix"]["normal_cycles"][0]
    assert first_cycle["intent_id"].startswith("intent_")
    assert first_cycle["ticket_id"].startswith("ticket_")
    assert first_cycle["risk_allowed"] is True
    assert first_cycle["queue_status"] == "queued"
    assert first_cycle["ticket_status"] == "pending_owner_approval"
    assert first_cycle["human_action_required"] is True
    assert first_cycle["client_order_id_matches_intent"] is True
    assert first_cycle["receipt_client_order_id_matches_intent"] is True
    assert first_cycle["receipt_ticket_id_matches_ticket"] is True
    assert first_cycle["paper_order_status"] == "filled"
    assert first_cycle["broker_receipt_status"] == "filled"
    assert first_cycle["ttl_seconds"] == 300
    assert first_cycle["refresh_interval_seconds"] == 300
    assert first_cycle["live_order_submission_enabled"] is False
    chain_checks = [check for check in report["checks"] if check["id"].endswith("_cycle_chain")]
    assert len(chain_checks) == 3
    assert all(check["status"] == "pass" for check in chain_checks)
    assert report["target_rebalance"]["sides"] == ["sell"]
    assert report["cycle_chain_matrix"]["target_rebalance"][0]["side"] == "sell"
    assert report["cycle_chain_matrix"]["target_rebalance"][0]["status"] == "pass"
    assert report["target_rebalance"]["filled_count"] == 1
    assert report["target_rebalance"]["symbols"] == ["TLT"]
    assert report["target_rebalance"]["latest_portfolio"]["cash"] > 5000.0
    assert report["rebalance"]["sides"] == ["sell"]
    assert report["cash_rebalance"]["sides"] == ["sell"]
    assert report["cycle_chain_matrix"]["cash_rebalance"][0]["side"] == "sell"
    assert report["cycle_chain_matrix"]["cash_rebalance"][0]["status"] == "pass"
    assert report["cash_rebalance"]["filled_count"] == 1
    assert report["cash_rebalance"]["latest_portfolio"]["cash"] > 1.0
    assert "临时关闭仓位/总敞口上限" in report["cash_rebalance"]["policy_override_zh"]
    assert report["safety_boundary"]["live_order_submission_enabled"] is False
    assert "真实下单" in report["safety_boundary"]["message_zh"]
    assert "真实资金订单" in report["safety_boundary"]["message_zh"]


def test_paper_trading_maturity_summary_and_write_result_are_chinese(tmp_path):
    report = run_paper_trading_maturity_check(root=Path("."), cycles=1)

    summary = format_paper_trading_maturity_summary_zh(report)
    write_result = write_paper_trading_maturity_report(report, tmp_path / "paper_maturity.json")

    assert "Alpha 模拟交易成熟度验收" in summary
    assert "逐周期候选订单链路" in summary
    assert "不触发真实下单" in summary
    assert "不提交真实资金订单" in summary
    assert "broker-ready" not in summary
    assert write_result["status_zh"] == "已写入"
    assert Path(write_result["path"]).exists()
