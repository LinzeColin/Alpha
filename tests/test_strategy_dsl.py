import pytest
from backend.app.schemas.strategy_dsl import validate_strategy


def valid_payload():
    return {
        "name": "ETF Momentum v0",
        "asset_class": "etf",
        "universe": ["SPY", "QQQ", "TLT"],
        "rebalance_frequency": "monthly",
        "signals": [{"type": "momentum", "lookback_days": 126}],
        "risk": {"no_leverage": True, "no_short": True, "no_options": True, "no_crypto_withdrawal": True},
    }


def test_valid_etf_strategy_passes():
    strategy = validate_strategy(valid_payload())
    assert strategy.name == "ETF Momentum v0"
    assert strategy.universe == ["SPY", "QQQ", "TLT"]


def test_leverage_rejected():
    p = valid_payload()
    p["risk"]["no_leverage"] = False
    with pytest.raises(ValueError):
        validate_strategy(p)


def test_short_rejected():
    p = valid_payload()
    p["risk"]["no_short"] = False
    with pytest.raises(ValueError):
        validate_strategy(p)


def test_options_rejected():
    p = valid_payload()
    p["risk"]["no_options"] = False
    with pytest.raises(ValueError):
        validate_strategy(p)
