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
    assert snapshot.status["data_quality"] == "sample"
    assert snapshot.status["real_market_data"] is False
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
    assert status["real_market_data"] is True
    assert snapshot.price_path == cache
    assert snapshot.status["data_quality"] == "fresh"
    assert snapshot.status["latest_prices"] == {"SPY": 101.5}
    assert "s=spy.us" in calls[0][0]
    assert pd.read_csv(cache)["source"].iloc[0] == "stooq_public_delayed"
