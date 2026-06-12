from backend.app.services.paper_broker import PaperBroker, PaperOrder


def test_paper_broker_persists_portfolio_state(tmp_path):
    path = tmp_path / "paper_portfolio.json"
    broker = PaperBroker(cash=1000)
    result = broker.submit_order(PaperOrder(idempotency_key="k1", symbol="TLT", side="buy", quantity=2, price=10))
    assert result["status"] == "filled"
    broker.save(path)

    reloaded = PaperBroker.load(path)
    assert reloaded.cash == 980
    assert reloaded.positions == {"TLT": 2}
    assert reloaded.seen_keys == {"k1"}
    assert reloaded.trade_log[0]["notional"] == 20
