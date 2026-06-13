from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import yaml


DEFAULT_PROVIDER = "cache_or_fixture"
PUBLIC_STOOQ_PROVIDER = "stooq"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass(frozen=True)
class MarketDataSnapshot:
    price_path: Path
    status: dict


class MarketDataGateway:
    """Resolve the price dataset used by research, paper trading, and dashboard views."""

    def __init__(
        self,
        *,
        root: str | Path,
        config_path: str | Path | None = None,
        fetcher=None,
    ) -> None:
        self.root = Path(root)
        self.config_path = Path(config_path) if config_path else self.root / "configs" / "market_data.yaml"
        self.config = self._load_config()
        self.fetcher = fetcher or urlopen

    def resolve_price_path(self, *, force_refresh: bool = False) -> MarketDataSnapshot:
        provider = self.provider
        cache_path = self.cache_path
        fixture_path = self.fixture_path
        refresh_error = None
        refreshed = False

        if provider == PUBLIC_STOOQ_PROVIDER and (force_refresh or self._cache_is_missing_or_stale()):
            try:
                self.refresh_public_stooq_cache()
                refreshed = True
            except Exception as exc:  # pragma: no cover - defensive external-source boundary
                refresh_error = str(exc)

        if cache_path.exists():
            return MarketDataSnapshot(
                price_path=cache_path,
                status=self._status_for_path(
                    price_path=cache_path,
                    provider=provider,
                    source_kind="public_cache" if self._cache_has_public_data(cache_path) else "local_cache",
                    data_quality=self._cache_quality(),
                    real_market_data=self._cache_has_public_data(cache_path),
                    refresh_attempted=provider == PUBLIC_STOOQ_PROVIDER and (force_refresh or refreshed or refresh_error is not None),
                    refresh_succeeded=refreshed,
                    refresh_error=refresh_error,
                ),
            )

        return MarketDataSnapshot(
            price_path=fixture_path,
            status=self._status_for_path(
                price_path=fixture_path,
                provider=provider,
                source_kind="fixture",
                data_quality="sample",
                real_market_data=False,
                refresh_attempted=provider == PUBLIC_STOOQ_PROVIDER and (force_refresh or refresh_error is not None),
                refresh_succeeded=False,
                refresh_error=refresh_error,
            ),
        )

    def refresh_public_stooq_cache(self) -> dict:
        frames = []
        fetched_at = utc_now_iso()
        for symbol in self.symbols:
            frame = self._fetch_stooq_symbol(symbol, fetched_at=fetched_at)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            raise ValueError("public provider returned no usable market data")
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values(["date", "symbol"])
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(self.cache_path, index=False)
        return self._status_for_path(
            price_path=self.cache_path,
            provider=PUBLIC_STOOQ_PROVIDER,
            source_kind="public_cache",
            data_quality="fresh",
            real_market_data=True,
            refresh_attempted=True,
            refresh_succeeded=True,
            refresh_error=None,
        )

    def status(self) -> dict:
        return self.resolve_price_path(force_refresh=False).status

    @property
    def provider(self) -> str:
        configured = str(self.config.get("provider", DEFAULT_PROVIDER))
        return os.environ.get("ALPHA_MARKET_DATA_PROVIDER", configured).strip().lower() or DEFAULT_PROVIDER

    @property
    def symbols(self) -> list[str]:
        override = os.environ.get("ALPHA_MARKET_DATA_SYMBOLS")
        if override:
            return [item.strip().upper() for item in override.split(",") if item.strip()]
        symbols = self.config.get("symbols") or ["SPY", "QQQ", "TLT"]
        return [str(symbol).upper() for symbol in symbols]

    @property
    def cache_path(self) -> Path:
        return self._resolve_path(str(self.config.get("cache_path", "runtime/market_data/latest_prices.csv")))

    @property
    def fixture_path(self) -> Path:
        return self._resolve_path(str(self.config.get("fixture_path", "data/sample_prices.csv")))

    @property
    def max_cache_age_seconds(self) -> int:
        return int(self.config.get("max_cache_age_seconds", 86400))

    @property
    def network_timeout_seconds(self) -> int:
        return int(self.config.get("network_timeout_seconds", 10))

    @property
    def stooq_base_url(self) -> str:
        return str(self.config.get("stooq_base_url", "https://stooq.com/q/d/l/"))

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        loaded = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("market data config must be a mapping")
        return loaded

    def _resolve_path(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else self.root / path

    def _fetch_stooq_symbol(self, symbol: str, *, fetched_at: str) -> pd.DataFrame:
        stooq_symbol = f"{symbol.lower()}.us"
        query = urlencode({"s": stooq_symbol, "i": "d"})
        separator = "&" if "?" in self.stooq_base_url else "?"
        url = f"{self.stooq_base_url}{separator}{query}"
        with self.fetcher(url, timeout=self.network_timeout_seconds) as response:
            payload = response.read()
        df = pd.read_csv(io.BytesIO(payload), parse_dates=["Date"])
        required = {"Date", "Close"}
        if not required.issubset(df.columns):
            raise ValueError(f"public provider response missing columns for {symbol}")
        df = df.rename(columns={"Date": "date", "Close": "close"})
        df = df[["date", "close"]].copy()
        df["symbol"] = symbol.upper()
        df["source"] = "stooq_public_delayed"
        df["source_ref"] = stooq_symbol
        df["fetched_at"] = fetched_at
        df = df.dropna(subset=["date", "close"])
        df["close"] = df["close"].astype(float)
        return df[["date", "symbol", "close", "source", "source_ref", "fetched_at"]]

    def _cache_is_missing_or_stale(self) -> bool:
        if not self.cache_path.exists():
            return True
        return self._cache_age_seconds() > self.max_cache_age_seconds

    def _cache_age_seconds(self) -> int | None:
        if not self.cache_path.exists():
            return None
        modified_at = datetime.fromtimestamp(self.cache_path.stat().st_mtime, tz=timezone.utc)
        return max(0, int((utc_now() - modified_at).total_seconds()))

    def _cache_quality(self) -> str:
        age = self._cache_age_seconds()
        if age is None:
            return "missing"
        return "fresh" if age <= self.max_cache_age_seconds else "stale"

    def _cache_has_public_data(self, cache_path: Path) -> bool:
        try:
            df = pd.read_csv(cache_path, nrows=5)
        except Exception:
            return False
        if "source" not in df.columns:
            return False
        return bool(df["source"].astype(str).str.contains("public", case=False, na=False).any())

    def _status_for_path(
        self,
        *,
        price_path: Path,
        provider: str,
        source_kind: str,
        data_quality: str,
        real_market_data: bool,
        refresh_attempted: bool,
        refresh_succeeded: bool,
        refresh_error: str | None,
    ) -> dict:
        latest = _latest_dataset_stats(price_path)
        return {
            "provider": provider,
            "source_kind": source_kind,
            "data_quality": data_quality,
            "real_market_data": real_market_data,
            "price_path": str(price_path),
            "cache_path": str(self.cache_path),
            "fixture_path": str(self.fixture_path),
            "cache_exists": self.cache_path.exists(),
            "cache_age_seconds": self._cache_age_seconds(),
            "max_cache_age_seconds": self.max_cache_age_seconds,
            "symbols": self.symbols,
            "symbol_count": latest["symbol_count"],
            "row_count": latest["row_count"],
            "latest_date": latest["latest_date"],
            "latest_prices": latest["latest_prices"],
            "refresh_attempted": refresh_attempted,
            "refresh_succeeded": refresh_succeeded,
            "refresh_error": refresh_error,
            "generated_at": utc_now_iso(),
        }


def _latest_dataset_stats(price_path: Path) -> dict:
    if not price_path.exists():
        return {"symbol_count": 0, "row_count": 0, "latest_date": None, "latest_prices": {}}
    df = pd.read_csv(price_path, parse_dates=["date"])
    if df.empty:
        return {"symbol_count": 0, "row_count": 0, "latest_date": None, "latest_prices": {}}
    latest = df.sort_values("date").groupby("symbol").tail(1)
    latest_prices = {
        str(row["symbol"]): round(float(row["close"]), 4)
        for _, row in latest.sort_values("symbol").iterrows()
    }
    latest_date = latest["date"].max()
    return {
        "symbol_count": int(df["symbol"].nunique()),
        "row_count": int(len(df)),
        "latest_date": latest_date.date().isoformat() if hasattr(latest_date, "date") else str(latest_date),
        "latest_prices": latest_prices,
    }
