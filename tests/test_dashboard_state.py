from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.api import routes
from backend.app.main import app
from backend.app.services.display_locale import format_paper_cycle_summary_zh, zh_reason, zh_status
from backend.app.services.approval_queue import ApprovalQueue


def _patch_fixture_market_data(monkeypatch, tmp_path):
    monkeypatch.delenv("ALPHA_MARKET_DATA_PROVIDER", raising=False)
    config = tmp_path / "market_data.yaml"
    config.write_text(
        "\n".join(
            [
                'provider: "cache_or_fixture"',
                'symbols: ["SPY", "QQQ", "TLT"]',
                f'cache_path: "{tmp_path / "missing_market_cache.csv"}"',
                'fixture_path: "data/sample_prices.csv"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(routes, "MARKET_DATA_CONFIG_PATH", config)


def test_dashboard_state_exposes_agent_portfolio_strategy_and_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.sqlite3")
    monkeypatch.setattr(routes, "PAPER_STATE_PATH", tmp_path / "paper_portfolio.json")
    monkeypatch.setattr(routes, "STRATEGY_HISTORY_PATH", tmp_path / "strategy_tournament_history.jsonl")
    monkeypatch.setattr(routes, "PAPER_PERFORMANCE_PATH", tmp_path / "paper_performance_history.jsonl")
    monkeypatch.setattr(routes, "DATA_PATH", Path("data/sample_prices.csv"))
    _patch_fixture_market_data(monkeypatch, tmp_path)

    run_result = routes.paper_run_once()
    state = routes.dashboard_state()

    assert run_result["status"] == "completed"
    assert run_result["market_data"]["source_kind"] in {"fixture", "public_cache", "local_cache", "broker_quote_cache"}
    assert state["health"]["refresh_interval_seconds"] == 300
    assert state["health"]["status_zh"] == "正常"
    assert state["health"]["mode_zh"] == "研究、模拟交易与候选订单人工复核模式"
    assert state["market_data"]["latest_date"] is not None
    assert state["market_data"]["real_market_data"] is False
    assert state["ops_health"]["safety_boundary"]["live_order_submission_enabled"] is False
    assert state["ops_health"]["check_count"] >= 1
    assert state["ops_maintenance"]["status"] in {"stopped", "maintenance_sleeping", "running_maintenance", "starting"}
    assert state["ops_maintenance"]["backup_interval_seconds"] > 0
    assert state["paper_readiness"]["deadline"] == "2026-06-15"
    assert state["paper_readiness"]["deadline_zh"] == "2026年6月15日"
    assert state["paper_readiness"]["dashboard_app_deadline"] == "2026-06-17"
    assert state["paper_readiness"]["dashboard_app_deadline_zh"] == "2026年6月17日"
    assert state["paper_readiness"]["check_count"] == 10
    assert state["paper_readiness"]["safety_boundary"]["live_order_submission_enabled"] is False
    assert state["soak_readiness"]["target_days"] == 30
    assert state["soak_readiness"]["check_count"] == 8
    assert state["soak_readiness"]["safety_boundary"]["live_order_submission_enabled"] is False
    assert state["agent_status"]["status"] == "ready"
    assert state["paper_portfolio"]["trade_count"] == 1
    assert state["paper_performance"]["status"] == "ready"
    assert state["paper_performance"]["run_count"] == 1
    assert state["paper_performance"]["latest_total_equity"] == state["paper_portfolio"]["total_equity"]
    assert state["paper_performance"]["total_return_zh"] == "-0.01%"
    assert state["paper_performance"]["current_drawdown_zh"] == "0.00%"
    assert state["paper_performance"]["latest_total_commission"] == 1.0
    assert state["paper_performance"]["latest_execution_model_zh"] == "固定佣金与滑点模型"
    assert state["paper_broker_status"]["adapter_id"] == "local_sandbox_paper_broker"
    assert state["paper_broker_status"]["mode"] == "paper"
    assert state["paper_broker_status"]["live_order_submission_enabled"] is False
    assert state["paper_broker_status"]["execution_model_zh"] == "固定佣金与滑点模型"
    assert state["paper_broker_status"]["commission_per_order"] == 1.0
    assert state["paper_broker_status"]["slippage_bps"] == 5.0
    assert state["paper_broker_status"]["paper_trade_count"] == 1
    assert state["moomoo_broker_status"]["provider_id"] == "moomoo_opend"
    assert state["moomoo_broker_status"]["mode_zh"] == "只读连接探测"
    assert state["moomoo_broker_status"]["live_order_submission_enabled"] is False
    assert state["moomoo_broker_status"]["trade_unlock_required"] is False
    assert state["moomoo_broker_status"]["supports_real_broker_place_order"] is False
    assert "提交真实资金订单" in state["moomoo_broker_status"]["forbidden_operations_zh"]
    assert state["moomoo_quote_snapshot"]["mode_zh"] == "只读行情快照"
    assert state["moomoo_quote_snapshot"]["trade_context_enabled"] is False
    assert state["moomoo_quote_snapshot"]["live_order_submission_enabled"] is False
    assert state["strategy_tournament"]["candidate_count"] > 0
    assert state["strategy_tournament"]["validation_summary"]["validated_count"] > 0
    assert "hit_rate" in state["strategy_tournament"]["winner"]
    assert state["strategy_journal"]["status"] == "ready"
    assert state["strategy_journal"]["run_count"] == 1
    assert state["strategy_journal"]["latest_winner_strategy_id"] == run_result["strategy_tournament"]["winner"]["strategy_id"]
    assert state["strategy_journal"]["latest_winner_strategy_id_zh"].startswith("动量策略 ")
    assert state["strategy_journal"]["latest_winner_decision_zh"] == "可进入模拟交易"
    assert state["strategy_journal"]["stability_ratio_zh"] == "100.00%"
    assert state["approval_queue"]["count"] == 1
    assert state["approval_queue"]["storage"]["backend"] == "sqlite"
    assert state["approval_queue"]["storage"]["backend_zh"] == "SQLite 数据库"
    assert state["approval_queue"]["storage"]["durable"] is True
    assert state["owner_summary"]["approval_queue_storage"]["backend"] == "sqlite"
    assert state["owner_summary"]["system_mode_zh"] == "研究、模拟交易与候选订单人工复核模式"
    assert state["owner_summary"]["required_owner_actions_zh"] == ["复核候选订单工单"]
    assert state["owner_summary"]["message_zh"] == "当前有 1 张有效候选单需要人工复核。"
    assert state["agent_status"]["approval_queue_storage"]["backend"] == "sqlite"


def test_agent_status_reports_app_runtime_loop_state(tmp_path, monkeypatch):
    loop_state = {
        "enabled": True,
        "status": "sleeping",
        "task_running": True,
        "interval_seconds": 300,
        "run_count": 1,
        "error_count": 0,
    }
    monkeypatch.setattr(routes.AUTO_PAPER_AGENT, "snapshot", lambda: loop_state)
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.sqlite3")

    status = routes.agent_status()

    assert status["loop"] == loop_state
    assert status["loop"]["task_running"] is True
    assert status["pending_tickets"] == 0
    assert status["approval_queue_storage"]["backend"] == "sqlite"


def test_owner_summary_counts_only_fresh_pending_tickets(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    queue_path = tmp_path / "approval_queue.json"
    queue = ApprovalQueue(queue_path)
    queue.enqueue(
        {
            "ticket_id": "ticket_expired",
            "status": "pending_owner_approval",
            "created_at": now.isoformat(),
            "intent": {"expires_at": (now - timedelta(seconds=1)).isoformat()},
            "broker_payload": {},
            "risk_check": {},
        }
    )
    monkeypatch.setattr(routes, "QUEUE_PATH", queue_path)

    summary = routes.owner_summary()
    api_queue = routes.approval_queue()

    assert summary["pending_order_tickets"] == 0
    assert summary["expired_order_tickets"] == 1
    assert api_queue["count"] == 0
    assert api_queue["summary"]["total_count"] == 1
    assert api_queue["summary"]["expired_pending_count"] == 1


def test_approval_queue_review_actions_are_exposed_to_dashboard_state(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.sqlite3")
    monkeypatch.setattr(routes, "PAPER_STATE_PATH", tmp_path / "paper_portfolio.json")
    monkeypatch.setattr(routes, "STRATEGY_HISTORY_PATH", tmp_path / "strategy_tournament_history.jsonl")
    monkeypatch.setattr(routes, "PAPER_PERFORMANCE_PATH", tmp_path / "paper_performance_history.jsonl")
    monkeypatch.setattr(routes, "DATA_PATH", Path("data/sample_prices.csv"))
    _patch_fixture_market_data(monkeypatch, tmp_path)

    run_result = routes.paper_run_once()
    ticket_id = run_result["approval_queue"]["ticket"]["ticket_id"]

    reviewed = routes.approval_queue_owner_review(ticket_id, {"actor_id": "owner_dashboard"})
    broker_ticket = routes.approval_queue_broker_ticket(ticket_id)
    broker_ticket_view = routes.approval_queue_broker_ticket_view(ticket_id).body.decode("utf-8")
    broker_ticket_csv = routes.approval_queue_broker_ticket_csv(ticket_id).body.decode("utf-8")
    exported = routes.approval_queue_mark_exported(ticket_id, {"actor_id": "owner_dashboard"})
    state = routes.dashboard_state()

    assert reviewed["new_status"] == "owner_reviewed"
    assert broker_ticket["manual_entry_allowed"] is True
    assert broker_ticket["manual_entry_allowed_zh"] == "是"
    assert broker_ticket["live_order_submission_enabled"] is False
    assert broker_ticket["broker_payload_zh"]["side_zh"] == "买入"
    assert "Alpha 经纪商就绪工单" in broker_ticket_view
    assert "允许人工录入" in broker_ticket_view
    assert "仅供所有者在经纪商系统中人工确认录入" in broker_ticket_view
    assert "不会通过 Alpha 自动提交真实资金订单" in broker_ticket_view
    assert "manual_owner_broker_confirmation_only" not in broker_ticket_view
    assert "工单号,标的,方向,数量" in broker_ticket_csv
    assert "ticket_id,symbol,side,quantity" not in broker_ticket_csv
    assert exported["new_status"] == "broker_ticket_exported"
    assert state["approval_queue"]["summary"]["fresh_pending_count"] == 0
    assert state["approval_queue"]["summary"]["broker_ticket_exported_count"] == 1
    assert state["approval_queue"]["tickets"][0]["status"] == "broker_ticket_exported"
    assert state["approval_queue"]["tickets"][0]["broker_ticket_export"]["live_order_submission_enabled"] is False
    assert state["approval_queue"]["storage"]["backend"] == "sqlite"


def test_dashboard_html_uses_chinese_user_visible_text():
    html = routes.dashboard()

    assert '<html lang="zh-CN">' in html
    assert "Alpha 控制台" in html
    assert "运行模拟交易周期" in html
    assert "系统快照" in html
    assert "模拟组合" in html
    assert "模拟绩效" in html
    assert "智能体运行状态" in html
    assert "模拟交易状态" in html
    assert "模拟收益率" in html
    assert "累计收益率" in html
    assert "最大回撤" in html
    assert "权益高水位" in html
    assert "执行模型" in html
    assert "模拟滑点" in html
    assert "单笔佣金" in html
    assert "累计佣金" in html
    assert "最近成交成本" in html
    assert "/broker-ticket/view" in html
    assert "策略锦标赛" in html
    assert "策略迭代历史" in html
    assert "策略稳定度" in html
    assert "连续胜出次数" in html
    assert "审批队列" in html
    assert "模拟交易执行层" in html
    assert "富途牛牛开放网关（只读）" in html
    assert "富途牛牛开放网关" in html
    assert "富途行情" in html
    assert "只读连接探测" in html
    assert "只读行情快照" in html
    assert "开放网关连接" in html
    assert "接口包" in html
    assert "软件开发包可导入" in html
    assert "下一步" in html
    assert "交易解锁" in html
    assert "禁止操作" in html
    assert "行情数据" in html
    assert "运行健康" in html
    assert "交付就绪" in html
    assert "模拟交易交付日期" in html
    assert "网页与本地应用交付日期" in html
    assert "交付项" in html
    assert "长运行预检" in html
    assert "目标周期" in html
    assert "预检项" in html
    assert "刷新公共行情" in html
    assert "生成运行备份" in html
    assert "自动维护" in html
    assert "自动备份次数" in html
    assert "健康历史" in html
    assert "备份保留数" in html
    assert "行情源" in html
    assert "富途牛牛只读行情" in html
    assert "经纪商只读行情缓存" in html
    assert "行情质量" in html
    assert "真实市场数据" in html
    assert "公共延迟行情缓存" in html
    assert "允许真实下单" in html
    assert "适配器" in html
    assert "本地沙盒模拟经纪商适配器" in html
    assert "模拟交易循环智能体" in html
    assert "市价单" in html
    assert "当日有效" in html
    assert "下单前风控检查通过" in html
    assert "有效候选单" in html
    assert "过期候选单" in html
    assert "已复核" in html
    assert "已导出工单" in html
    assert "队列存储" in html
    assert "持久化" in html
    assert "标记已复核" in html
    assert "标记已导出" in html
    assert "查看工单" in html
    assert "下载工单表格" in html
    assert "待人工确认" in html
    assert "最近更新：" in html
    assert "总体状态" in html
    assert "安全边界" in html
    assert "检查项" in html
    assert "maintenance_sleeping: '等待下次维护'" in html
    assert "running_maintenance: '正在维护'" in html
    assert "degraded: '需关注'" in html
    assert "'pre-trade risk checks passed': '下单前风控检查通过'" in html

    assert "Alpha Dashboard" not in html
    assert "Run Paper Cycle" not in html
    assert "System Snapshot" not in html
    assert "Approval Queue" not in html
    assert "No pending tickets" not in html
    assert "<th>Adapter</th>" not in html
    assert "Moomoo OpenD" not in html
    assert "API 包" not in html
    assert "SDK 可导入" not in html
    assert " bps" not in html


def test_fastapi_metadata_is_chinese():
    schema = app.openapi()

    assert schema["info"]["title"] == "Alpha 个人量化智能体工作台"
    assert "本地优先" in schema["info"]["description"]
    assert "Personal Alpha Agent Workspace" not in schema["info"]["title"]


def test_owner_facing_http_errors_are_chinese():
    with pytest.raises(HTTPException) as exc_info:
        routes.approval_queue_broker_ticket("missing_ticket")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {"code": "ticket_not_found", "message_zh": "未找到工单"}


def test_strategy_validation_error_is_chinese():
    payload = {
        "name": "ETF Momentum v0",
        "asset_class": "etf",
        "universe": ["SPY", "QQQ", "TLT"],
        "rebalance_frequency": "monthly",
        "signals": [{"type": "momentum", "lookback_days": 126}],
        "risk": {"no_leverage": False, "no_short": True, "no_options": True, "no_crypto_withdrawal": True},
    }

    with pytest.raises(HTTPException) as exc_info:
        routes.strategy_validate(payload)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "strategy_validation_failed",
        "message_zh": "策略定义校验失败：MVP 禁止使用杠杆。",
    }
    assert "prohibits" not in exc_info.value.detail["message_zh"]


def test_python_display_locale_covers_runtime_statuses_and_live_reasons():
    assert zh_status("maintenance_sleeping") == "等待下次维护"
    assert zh_status("running_maintenance") == "正在维护"
    assert zh_status("degraded") == "需关注"
    assert zh_status("pass") == "通过"
    assert zh_status("written") == "已写入"
    assert zh_status("empty") == "暂无记录"
    assert zh_reason("live trading disabled by policy") == "策略已禁用真实资金交易"
    assert zh_reason("FailClosedLiveBroker never submits real orders") == "失败即关闭真实经纪商适配器不会提交真实订单"


def test_paper_cycle_summary_is_chinese_for_human_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "QUEUE_PATH", tmp_path / "approval_queue.sqlite3")
    monkeypatch.setattr(routes, "PAPER_STATE_PATH", tmp_path / "paper_portfolio.json")
    monkeypatch.setattr(routes, "STRATEGY_HISTORY_PATH", tmp_path / "strategy_tournament_history.jsonl")
    monkeypatch.setattr(routes, "PAPER_PERFORMANCE_PATH", tmp_path / "paper_performance_history.jsonl")
    monkeypatch.setattr(routes, "DATA_PATH", Path("data/sample_prices.csv"))
    _patch_fixture_market_data(monkeypatch, tmp_path)

    result = routes.paper_run_once()
    summary = format_paper_cycle_summary_zh(result)

    assert "Alpha 模拟交易周期摘要" in summary
    assert "候选订单：" in summary
    assert "策略迭代：已写入" in summary
    assert "模拟绩效：累计收益 -0.01%" in summary
    assert "累计佣金 1.0" in summary
    assert "行情数据：" in summary
    assert f"真实市场数据 {'是' if result['market_data']['real_market_data'] else '否'}" in summary
    assert "风控：已通过风控，待人工确认（下单前风控检查通过）" in summary
    assert "执行层：本地沙盒模拟经纪商适配器" in summary
    assert "模型 固定佣金与滑点模型" in summary
    assert "滑点 5.00 基点" in summary
    assert " bps" not in summary
    assert "单笔佣金 1.00" in summary
    assert "安全边界：本周期只执行模拟交易并生成待人工确认工单，不会提交真实资金订单。" in summary
    assert "pending_owner_approval" not in summary
    assert "local_sandbox_paper_broker" not in summary
