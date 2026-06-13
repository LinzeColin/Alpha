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


def test_local_sandbox_paper_adapter_returns_broker_like_receipt():
    adapter = LocalSandboxPaperBrokerAdapter(PaperBroker())
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1", "broker_payload": {"order_type": "market"}})

    assert receipt["status"] == "filled"
    assert receipt["mode"] == "paper"
    assert receipt["broker_order_id"].startswith("paper_")
    assert receipt["client_order_id"] == "run:key"
    assert receipt["ticket_id"] == "ticket_1"
    assert receipt["live_order_submission_enabled"] is False
    assert receipt["filled_quantity"] == 1
    assert receipt["paper_result"]["status"] == "filled"
