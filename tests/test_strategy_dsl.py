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
    with pytest.raises(ValueError) as exc_info:
        validate_strategy(p)
    assert "MVP 禁止使用杠杆" in str(exc_info.value)


def test_short_rejected():
    p = valid_payload()
    p["risk"]["no_short"] = False
    with pytest.raises(ValueError) as exc_info:
        validate_strategy(p)
    assert "MVP 禁止卖空" in str(exc_info.value)


def test_options_rejected():
    p = valid_payload()
    p["risk"]["no_options"] = False
    with pytest.raises(ValueError) as exc_info:
        validate_strategy(p)
    assert "MVP 禁止期权" in str(exc_info.value)
