from pathlib import Path

import pandas as pd

from backend.app.services.market_data_gateway import MarketDataGateway


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_market_data_gateway_falls_back_to_fixture_when_cache_missing(tmp_path):
    fixture = tmp_path / "fixture.csv"
    fixture.write_text("date,symbol,close\n2026-06-01,SPY,100.0\n", encoding="utf-8")
    config = tmp_path / "market_data.yaml"
    config.write_text(
        "\n".join(
            [
                'provider: "cache_or_fixture"',
                'symbols: ["SPY"]',
                f'cache_path: "{tmp_path / "missing_cache.csv"}"',
                f'fixture_path: "{fixture}"',
                "max_cache_age_seconds: 86400",
            ]
        ),
        encoding="utf-8",
    )

    snapshot = MarketDataGateway(root=Path("."), config_path=config).resolve_price_path()

    assert snapshot.price_path == fixture
    assert snapshot.status["source_kind"] == "fixture"
    assert snapshot.status["source_kind_zh"] == "样例数据"
    assert snapshot.status["data_quality"] == "sample"
    assert snapshot.status["data_quality_zh"] == "样例"
    assert snapshot.status["real_market_data"] is False
    assert snapshot.status["real_market_data_zh"] == "否"
    assert snapshot.status["latest_prices"] == {"SPY": 100.0}


def test_market_data_gateway_refreshes_public_stooq_cache(tmp_path):
    fixture = tmp_path / "fixture.csv"
    fixture.write_text("date,symbol,close\n2026-06-01,SPY,100.0\n", encoding="utf-8")
    cache = tmp_path / "cache.csv"
    config = tmp_path / "market_data.yaml"
    config.write_text(
        "\n".join(
            [
                'provider: "stooq"',
                'symbols: ["SPY"]',
                f'cache_path: "{cache}"',
                f'fixture_path: "{fixture}"',
                "max_cache_age_seconds: 86400",
                'stooq_base_url: "https://stooq.com/q/d/l/"',
            ]
        ),
        encoding="utf-8",
    )
    calls = []

    def fetcher(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(b"Date,Open,High,Low,Close,Volume\n2026-06-02,1,1,1,101.5,1000\n")

    gateway = MarketDataGateway(root=Path("."), config_path=config, fetcher=fetcher)

    status = gateway.refresh_public_stooq_cache()
    snapshot = gateway.resolve_price_path()

    assert cache.exists()
    assert status["source_kind"] == "public_cache"
    assert status["source_kind_zh"] == "公共延迟行情缓存"
    assert status["real_market_data"] is True
    assert status["real_market_data_zh"] == "是"
    assert status["refresh_error_zh"] == "无"
    assert snapshot.price_path == cache
    assert snapshot.status["data_quality"] == "fresh"
    assert snapshot.status["latest_prices"] == {"SPY": 101.5}
    assert "s=spy.us" in calls[0][0]
    assert pd.read_csv(cache)["source"].iloc[0] == "stooq_public_delayed"


def test_market_data_gateway_refreshes_moomoo_opend_quote_cache(tmp_path):
    fixture = tmp_path / "fixture.csv"
    fixture.write_text(
        "date,symbol,close\n2026-06-01,SPY,100.0\n2026-06-01,QQQ,200.0\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache.csv"
    config = tmp_path / "market_data.yaml"
    config.write_text(
        "\n".join(
            [
                'provider: "moomoo_opend"',
                'symbols: ["SPY", "QQQ"]',
                f'cache_path: "{cache}"',
                f'fixture_path: "{fixture}"',
                "max_cache_age_seconds: 86400",
            ]
        ),
        encoding="utf-8",
    )

    def quote_probe(config):
        assert config.symbols == ("US.SPY", "US.QQQ")
        return {
            "status": "ready",
            "provider_id": "moomoo_opend",
            "mode_zh": "只读行情快照",
            "message_zh": "已通过富途牛牛开放网关只读行情连接获取 2 条市场快照。",
            "row_count": 2,
            "quotes": [
                {"code": "US.SPY", "update_time": "2026-06-12 19:59:48.664", "last_price": 741.75},
                {"code": "US.QQQ", "update_time": "2026-06-12 20:01:36.677", "last_price": 721.34},
            ],
        }

    gateway = MarketDataGateway(root=Path("."), config_path=config, moomoo_quote_probe=quote_probe)

    status = gateway.refresh_moomoo_opend_cache()
    snapshot = gateway.resolve_price_path(force_refresh=True)
    cached = pd.read_csv(cache)

    assert status["provider"] == "moomoo_opend"
    assert status["provider_zh"] == "富途牛牛开放网关只读行情"
    assert status["source_kind"] == "broker_quote_cache"
    assert status["source_kind_zh"] == "经纪商只读行情缓存"
    assert status["data_quality"] == "fresh"
    assert status["data_quality_zh"] == "新鲜"
    assert status["real_market_data"] is True
    assert status["latest_prices"] == {"QQQ": 721.34, "SPY": 741.75}
    assert status["quote_snapshot"]["trade_context_enabled"] is False
    assert status["quote_snapshot"]["live_order_submission_enabled"] is False
    assert snapshot.price_path == cache
    assert snapshot.status["source_kind"] == "broker_quote_cache"
    assert snapshot.status["quote_snapshot"]["row_count"] == 2
    assert snapshot.status["quote_snapshot"]["trade_context_enabled"] is False
    assert snapshot.status["quote_snapshot"]["live_order_submission_enabled"] is False
    assert "moomoo_opend_snapshot" in set(cached["source"])


def test_market_data_gateway_falls_back_when_moomoo_quote_is_not_ready(tmp_path):
    fixture = tmp_path / "fixture.csv"
    fixture.write_text("date,symbol,close\n2026-06-01,SPY,100.0\n", encoding="utf-8")
    cache = tmp_path / "missing_cache.csv"
    config = tmp_path / "market_data.yaml"
    config.write_text(
        "\n".join(
            [
                'provider: "moomoo_opend"',
                'symbols: ["SPY"]',
                f'cache_path: "{cache}"',
                f'fixture_path: "{fixture}"',
                "max_cache_age_seconds: 86400",
            ]
        ),
        encoding="utf-8",
    )

    gateway = MarketDataGateway(
        root=Path("."),
        config_path=config,
        moomoo_quote_probe=lambda config: {
            "status": "blocked",
            "message_zh": "富途牛牛只读连接未就绪，未执行行情快照探测。",
            "quotes": [],
            "row_count": 0,
        },
    )

    snapshot = gateway.resolve_price_path(force_refresh=True)

    assert snapshot.price_path == fixture
    assert snapshot.status["source_kind"] == "fixture"
    assert snapshot.status["real_market_data"] is False
    assert snapshot.status["refresh_attempted"] is True
    assert snapshot.status["refresh_attempted_zh"] == "是"
    assert snapshot.status["refresh_succeeded"] is False
    assert snapshot.status["refresh_succeeded_zh"] == "否"
    assert "富途牛牛只读连接未就绪" in snapshot.status["refresh_error"]
    assert "富途牛牛只读连接未就绪" in snapshot.status["refresh_error_zh"]
    assert "Moomoo" not in snapshot.status["refresh_error_zh"]
