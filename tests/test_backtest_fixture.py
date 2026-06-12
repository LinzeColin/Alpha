from backend.app.services.backtest import run_buy_and_hold_fixture


def test_backtest_fixture_is_deterministic():
    a = run_buy_and_hold_fixture("data/sample_prices.csv")
    b = run_buy_and_hold_fixture("data/sample_prices.csv")
    assert a == b
    assert a["trade_count"] == 3
    assert "max_drawdown" in a
    assert "ending_equity" in a
