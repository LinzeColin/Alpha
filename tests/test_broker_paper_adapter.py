from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter, build_paper_broker_adapter
from backend.app.services.paper_broker import PaperBroker, PaperOrder


def test_local_sandbox_paper_adapter_reports_safe_status():
    adapter = LocalSandboxPaperBrokerAdapter(PaperBroker())

    status = adapter.status()

    assert status["adapter_id"] == "local_sandbox_paper_broker"
    assert status["provider"] == "local_sandbox"
    assert status["provider_zh"] == "本地沙盒模拟交易"
    assert status["adapter_readiness_zh"] == "就绪"
    assert status["mode"] == "paper"
    assert status["connected"] is True
    assert status["credential_required"] is False
    assert status["paper_order_submission_enabled"] is True
    assert status["external_paper_api_enabled"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["supports_real_broker_place_order"] is False
    assert status["execution_model_zh"] == "固定佣金与滑点模型"
    assert status["slippage_bps"] == 5.0
    assert status["commission_per_order"] == 1.0


def test_local_sandbox_paper_adapter_returns_broker_like_receipt():
    broker = PaperBroker()
    adapter = LocalSandboxPaperBrokerAdapter(broker)
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1", "broker_payload": {"order_type": "market"}})

    assert receipt["status"] == "filled"
    assert receipt["provider"] == "local_sandbox"
    assert receipt["adapter_readiness"] == "ready"
    assert receipt["mode"] == "paper"
    assert receipt["broker_order_id"].startswith("paper_")
    assert receipt["client_order_id"] == "run:key"
    assert receipt["ticket_id"] == "ticket_1"
    assert receipt["live_order_submission_enabled"] is False
    assert receipt["filled_quantity"] == 1
    assert receipt["reference_price"] == 91.95
    assert receipt["average_fill_price"] == 91.996
    assert receipt["commission"] == 1.0
    assert receipt["slippage_bps"] == 5.0
    assert receipt["execution_model_zh"] == "固定佣金与滑点模型"
    assert "滑点 5.00 基点" in receipt["execution_cost_zh"]
    assert "佣金 1.00 AUD" in receipt["execution_cost_zh"]
    assert "bps" not in receipt["execution_cost_zh"]
    assert receipt["paper_result"]["status"] == "filled"
    assert round(broker.cash, 2) == 9907.0
    assert broker.trade_log[0]["commission"] == 1.0
    assert broker.trade_log[0]["slippage_bps"] == 5.0
    assert broker.trade_log[0]["execution_model_id"] == "fixed_cost_slippage_v1"


def test_external_paper_api_adapter_fails_closed_when_disabled():
    broker = PaperBroker()
    adapter = build_paper_broker_adapter(
        broker,
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": False,
                "external_paper_api": {"order_submission_enabled": False},
            }
        },
    )
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    status = adapter.status()
    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1"})

    assert status["provider"] == "alpaca_paper"
    assert status["adapter_id"] == "external_paper_api_unavailable"
    assert status["adapter_readiness"] == "not_configured"
    assert status["paper_order_submission_enabled"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["supports_real_broker_place_order"] is False
    assert status["reason_zh"] == "安全配置未允许外部纸面交易 API 适配器"
    assert "继续使用本地沙盒模拟交易" in status["next_step_zh"]
    assert receipt["status"] == "skipped"
    assert receipt["reason_zh"] == "外部纸面交易 API 当前不可提交纸面订单"
    assert receipt["live_order_submission_enabled"] is False
    assert broker.trade_log == []


def test_unknown_paper_broker_provider_fails_closed():
    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={"paper_broker": {"provider": "unknown_provider"}},
    )

    status = adapter.status()

    assert status["adapter_id"] == "external_paper_api_unavailable"
    assert status["provider"] == "unknown_provider"
    assert status["live_order_submission_enabled"] is False
    assert status["reason_zh"] == "外部纸面交易 API 适配器尚未配置完成"
