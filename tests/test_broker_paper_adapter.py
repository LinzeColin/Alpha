from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter
from backend.app.services.paper_broker import PaperBroker, PaperOrder


def test_local_sandbox_paper_adapter_reports_safe_status():
    adapter = LocalSandboxPaperBrokerAdapter(PaperBroker())

    status = adapter.status()

    assert status["adapter_id"] == "local_sandbox_paper_broker"
    assert status["mode"] == "paper"
    assert status["connected"] is True
    assert status["credential_required"] is False
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
