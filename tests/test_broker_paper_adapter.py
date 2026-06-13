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


def test_local_sandbox_external_snapshot_is_not_required():
    adapter = LocalSandboxPaperBrokerAdapter(PaperBroker())

    snapshot = adapter.external_snapshot()

    assert snapshot["status"] == "not_configured"
    assert snapshot["provider_zh"] == "本地沙盒模拟交易"
    assert snapshot["position_count"] == 0
    assert snapshot["recent_order_count"] == 0
    assert snapshot["live_order_submission_enabled"] is False
    assert snapshot["summary_zh"] == "本地沙盒不需要外部纸面账户同步。"


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


def test_alpaca_paper_adapter_requires_env_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET_KEY", raising=False)
    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": True,
                    "base_url": "https://paper-api.alpaca.markets",
                },
            }
        },
    )
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    status = adapter.status()
    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1"})

    assert status["adapter_id"] == "alpaca_paper_broker"
    assert status["provider"] == "alpaca_paper"
    assert status["base_url"] == "https://paper-api.alpaca.markets"
    assert status["credentials_present"] is False
    assert status["paper_order_submission_enabled"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["reason_zh"] == "外部纸面交易 API 凭据缺失"
    assert receipt["status"] == "skipped"
    assert receipt["reason_zh"] == "外部纸面交易 API 凭据缺失"


def test_alpaca_paper_external_snapshot_requires_read_only_sync_enabled(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "paper-secret")
    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": False,
                    "read_only_sync_enabled": False,
                    "base_url": "https://paper-api.alpaca.markets",
                },
            }
        },
    )

    status = adapter.status()
    snapshot = adapter.external_snapshot()

    assert status["adapter_readiness"] == "ready"
    assert status["paper_order_submission_enabled"] is False
    assert status["read_only_sync_enabled"] is False
    assert snapshot["status"] == "not_configured"
    assert snapshot["reason_zh"] == "外部纸面交易 API 只读同步不可用"
    assert snapshot["live_order_submission_enabled"] is False


def test_alpaca_paper_adapter_rejects_non_paper_base_url(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "paper-secret")
    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": True,
                    "base_url": "https://api.alpaca.markets",
                },
            }
        },
    )

    status = adapter.status()

    assert status["adapter_id"] == "alpaca_paper_broker"
    assert status["paper_base_url_allowed"] is False
    assert status["paper_order_submission_enabled"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["reason_zh"] == "外部纸面交易 API 地址不在纸面交易允许列表内"


def test_alpaca_paper_adapter_submits_mocked_paper_order(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "paper-secret")
    calls = []

    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": True,
                    "read_only_sync_enabled": True,
                    "base_url": "https://paper-api.alpaca.markets",
                },
            }
        },
    )
    adapter.http_post_json = lambda url, payload, headers, timeout: calls.append(
        {"url": url, "payload": payload, "headers": headers, "timeout": timeout}
    ) or {
        "id": "alpaca-paper-order-1",
        "client_order_id": "run:key",
        "symbol": "TLT",
        "qty": "1",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "status": "accepted",
        "submitted_at": "2026-06-13T07:00:00Z",
        "filled_qty": "0",
        "filled_avg_price": None,
    }
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    status = adapter.status()
    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1", "broker_payload": {"order_type": "market", "time_in_force": "day"}})

    assert status["adapter_readiness"] == "ready"
    assert status["credentials_present"] is True
    assert status["paper_order_submission_enabled"] is True
    assert status["live_order_submission_enabled"] is False
    assert calls[0]["url"] == "https://paper-api.alpaca.markets/v2/orders"
    assert calls[0]["payload"] == {
        "symbol": "TLT",
        "qty": "1",
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "client_order_id": "run:key",
    }
    assert calls[0]["headers"]["APCA-API-KEY-ID"] == "paper-key"
    assert calls[0]["headers"]["APCA-API-SECRET-KEY"] == "paper-secret"
    assert receipt["status"] == "submitted"
    assert receipt["broker_order_id"] == "alpaca-paper-order-1"
    assert receipt["provider_order_status_zh"] == "已接受"
    assert receipt["live_order_submission_enabled"] is False
    assert "paper-secret" not in str(receipt)
    assert receipt["paper_result"]["provider_response"]["id"] == "alpaca-paper-order-1"


def test_alpaca_paper_external_snapshot_sanitizes_account_positions_and_orders(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY_ID", "paper-key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "paper-secret")
    calls = []
    responses = {
        "https://paper-api.alpaca.markets/v2/account": {
            "id": "account-id-secret",
            "account_number": "PA123456",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "100000.00",
            "buying_power": "200000.00",
            "equity": "101234.56",
            "portfolio_value": "101234.56",
            "long_market_value": "1234.56",
            "trading_blocked": False,
            "transfers_blocked": False,
            "account_blocked": False,
            "pattern_day_trader": False,
        },
        "https://paper-api.alpaca.markets/v2/positions": [
            {
                "asset_id": "asset-id-hidden",
                "symbol": "TLT",
                "asset_class": "us_equity",
                "side": "long",
                "qty": "2",
                "avg_entry_price": "91.0",
                "market_value": "184.00",
                "cost_basis": "182.00",
                "unrealized_pl": "2.00",
                "unrealized_plpc": "0.010989",
                "current_price": "92.00",
                "lastday_price": "91.50",
                "change_today": "0.00546",
            }
        ],
        "https://paper-api.alpaca.markets/v2/orders?status=all&limit=50": [
            {
                "id": "order-id-1",
                "client_order_id": "run:key",
                "symbol": "TLT",
                "asset_class": "us_equity",
                "qty": "1",
                "filled_qty": "0",
                "type": "market",
                "side": "buy",
                "time_in_force": "day",
                "status": "accepted",
                "submitted_at": "2026-06-13T07:00:00Z",
            }
        ],
    }
    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": False,
                    "read_only_sync_enabled": True,
                    "base_url": "https://paper-api.alpaca.markets",
                },
            }
        },
    )
    adapter.http_get_json = lambda url, headers, timeout: calls.append({"url": url, "headers": headers, "timeout": timeout}) or responses[url]

    snapshot = adapter.external_snapshot()

    assert snapshot["status"] == "ready"
    assert snapshot["status_zh"] == "已同步"
    assert snapshot["account"]["account_id_present"] is True
    assert snapshot["account"]["account_number_present"] is True
    assert snapshot["account"]["account_identifier_redacted_zh"] == "账户标识已隐藏"
    assert snapshot["account"]["status_zh"] == "正常"
    assert snapshot["account"]["equity"] == 101234.56
    assert snapshot["positions"][0]["symbol"] == "TLT"
    assert snapshot["positions"][0]["side_zh"] == "多头"
    assert snapshot["recent_orders"][0]["status_zh"] == "已接受"
    assert snapshot["position_count"] == 1
    assert snapshot["recent_order_count"] == 1
    assert "持仓 1 个" in snapshot["summary_zh"]
    assert "account-id-secret" not in str(snapshot)
    assert "PA123456" not in str(snapshot)
    assert "paper-secret" not in str(snapshot)
    assert calls[0]["headers"]["APCA-API-SECRET-KEY"] == "paper-secret"


def test_alpaca_paper_adapter_redacts_custom_env_credentials_on_request_error(monkeypatch):
    monkeypatch.setenv("CUSTOM_ALPACA_PAPER_KEY_ID", "custom-paper-key")
    monkeypatch.setenv("CUSTOM_ALPACA_PAPER_SECRET_KEY", "custom-paper-secret")

    adapter = build_paper_broker_adapter(
        PaperBroker(),
        config={
            "paper_broker": {
                "provider": "alpaca_paper",
                "allow_external_paper_api": True,
                "external_paper_api": {
                    "order_submission_enabled": True,
                    "base_url": "https://paper-api.alpaca.markets",
                    "key_id_env": "CUSTOM_ALPACA_PAPER_KEY_ID",
                    "secret_key_env": "CUSTOM_ALPACA_PAPER_SECRET_KEY",
                },
            }
        },
    )

    def failing_post(url, payload, headers, timeout):
        raise RuntimeError(f"HTTP 403 custom-paper-key custom-paper-secret {headers['APCA-API-SECRET-KEY']}")

    adapter.http_post_json = failing_post
    order = PaperOrder(idempotency_key="run:key", symbol="TLT", side="buy", quantity=1, price=91.95)

    status = adapter.status()
    receipt = adapter.submit_order(order, source_ticket={"ticket_id": "ticket_1", "broker_payload": {"order_type": "market", "time_in_force": "day"}})

    assert status["adapter_readiness"] == "ready"
    assert status["reason_zh"] == "Alpaca 纸面交易适配器就绪"
    assert receipt["status"] == "skipped"
    assert "custom-paper-key" not in str(receipt)
    assert "custom-paper-secret" not in str(receipt)
    assert "[redacted]" in receipt["reason_zh"]
    assert receipt["live_order_submission_enabled"] is False


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
