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

from backend.app.services.display_locale import zh_data_quality, zh_market_data_provider, zh_market_data_source
from backend.app.services.moomoo_broker_probe import MoomooQuoteSnapshotConfig, probe_moomoo_quote_snapshot


DEFAULT_PROVIDER = "cache_or_fixture"
PUBLIC_STOOQ_PROVIDER = "stooq"
MOOMOO_OPEND_PROVIDER = "moomoo_opend"


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
        moomoo_quote_probe=None,
    ) -> None:
        self.root = Path(root)
        self.config_path = Path(config_path) if config_path else self.root / "configs" / "market_data.yaml"
        self.config = self._load_config()
        self.fetcher = fetcher or urlopen
        self.moomoo_quote_probe = moomoo_quote_probe or probe_moomoo_quote_snapshot

    def resolve_price_path(self, *, force_refresh: bool = False) -> MarketDataSnapshot:
        provider = self.provider
        cache_path = self.cache_path
        fixture_path = self.fixture_path
        refresh_error = None
        refreshed = False
        refresh_status = None

        if provider == MOOMOO_OPEND_PROVIDER and (force_refresh or self._cache_is_missing_or_stale()):
            try:
                refresh_status = self.refresh_moomoo_opend_cache()
                refreshed = True
            except Exception as exc:
                refresh_error = str(exc)
        elif provider == PUBLIC_STOOQ_PROVIDER and (force_refresh or self._cache_is_missing_or_stale()):
            try:
                refresh_status = self.refresh_public_stooq_cache()
                refreshed = True
            except Exception as exc:  # pragma: no cover - defensive external-source boundary
                refresh_error = str(exc)

        if cache_path.exists():
            source_kind = self._cache_source_kind(cache_path)
            status = self._status_for_path(
                price_path=cache_path,
                provider=provider,
                source_kind=source_kind,
                data_quality=self._cache_quality(),
                real_market_data=source_kind in {"public_cache", "broker_quote_cache"},
                refresh_attempted=provider in {PUBLIC_STOOQ_PROVIDER, MOOMOO_OPEND_PROVIDER}
                and (force_refresh or refreshed or refresh_error is not None),
                refresh_succeeded=refreshed,
                refresh_error=refresh_error,
            )
            if refresh_status and refresh_status.get("quote_snapshot"):
                status["quote_snapshot"] = refresh_status["quote_snapshot"]
            return MarketDataSnapshot(
                price_path=cache_path,
                status=status,
            )

        return MarketDataSnapshot(
            price_path=fixture_path,
            status=self._status_for_path(
                price_path=fixture_path,
                provider=provider,
                source_kind="fixture",
                data_quality="sample",
                real_market_data=False,
                refresh_attempted=provider in {PUBLIC_STOOQ_PROVIDER, MOOMOO_OPEND_PROVIDER}
                and (force_refresh or refresh_error is not None),
                refresh_succeeded=False,
                refresh_error=refresh_error,
            ),
        )

    def refresh_cache(self) -> dict:
        if self.provider == MOOMOO_OPEND_PROVIDER:
            return self.refresh_moomoo_opend_cache()
        return self.refresh_public_stooq_cache()

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

    def refresh_moomoo_opend_cache(self) -> dict:
        cfg = MoomooQuoteSnapshotConfig.from_env()
        quote_cfg = MoomooQuoteSnapshotConfig(
            host=cfg.host,
            port=cfg.port,
            timeout_seconds=cfg.timeout_seconds,
            api_home=cfg.api_home,
            symbols=tuple(self.moomoo_symbols),
        )
        snapshot = self.moomoo_quote_probe(quote_cfg)
        if snapshot.get("status") != "ready":
            raise ValueError(snapshot.get("message_zh") or "富途牛牛只读行情快照未就绪")
        quote_rows = _moomoo_snapshot_rows(snapshot.get("quotes", []), fetched_at=utc_now_iso())
        if quote_rows.empty:
            raise ValueError("富途牛牛开放网关未返回可用行情行")
        history = self._load_overlay_base_history()
        combined = pd.concat([history, quote_rows], ignore_index=True) if not history.empty else quote_rows
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
        combined = combined.dropna(subset=["date", "symbol", "close"])
        combined = combined.sort_values(["date", "symbol", "fetched_at"]).drop_duplicates(
            subset=["date", "symbol"],
            keep="last",
        )
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(self.cache_path, index=False)
        status = self._status_for_path(
            price_path=self.cache_path,
            provider=MOOMOO_OPEND_PROVIDER,
            source_kind="broker_quote_cache",
            data_quality="fresh",
            real_market_data=True,
            refresh_attempted=True,
            refresh_succeeded=True,
            refresh_error=None,
        )
        status["quote_snapshot"] = {
            "provider_id": snapshot.get("provider_id"),
            "mode_zh": snapshot.get("mode_zh"),
            "row_count": snapshot.get("row_count", 0),
            "trade_context_enabled": False,
            "live_order_submission_enabled": False,
            "message_zh": snapshot.get("message_zh"),
        }
        return status

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
    def moomoo_symbols(self) -> list[str]:
        configured = self.config.get("moomoo_symbols")
        if configured:
            return [str(symbol).upper() for symbol in configured]
        return [symbol if "." in symbol else f"US.{symbol}" for symbol in self.symbols]

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

    def _cache_source_kind(self, cache_path: Path) -> str:
        try:
            source = pd.read_csv(cache_path, usecols=["source"])["source"].astype(str)
        except (ValueError, FileNotFoundError, pd.errors.EmptyDataError):
            return "local_cache"
        if source.str.contains("moomoo", case=False, na=False).any():
            return "broker_quote_cache"
        if source.str.contains("public", case=False, na=False).any():
            return "public_cache"
        return "local_cache"

    def _load_overlay_base_history(self) -> pd.DataFrame:
        source_path = self.cache_path if self.cache_path.exists() else self.fixture_path
        if not source_path.exists():
            return pd.DataFrame(columns=["date", "symbol", "close", "source", "source_ref", "fetched_at"])
        frame = pd.read_csv(source_path)
        required = {"date", "symbol", "close"}
        if not required.issubset(frame.columns):
            return pd.DataFrame(columns=["date", "symbol", "close", "source", "source_ref", "fetched_at"])
        frame = frame.copy()
        if "source" not in frame.columns:
            frame["source"] = "fixture_seed"
        if "source_ref" not in frame.columns:
            frame["source_ref"] = frame["symbol"].astype(str)
        if "fetched_at" not in frame.columns:
            frame["fetched_at"] = ""
        return frame[["date", "symbol", "close", "source", "source_ref", "fetched_at"]]

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
            "provider_zh": zh_market_data_provider(provider),
            "source_kind": source_kind,
            "source_kind_zh": zh_market_data_source(source_kind),
            "data_quality": data_quality,
            "data_quality_zh": zh_data_quality(data_quality),
            "real_market_data": real_market_data,
            "real_market_data_zh": "是" if real_market_data else "否",
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
            "refresh_attempted_zh": "是" if refresh_attempted else "否",
            "refresh_succeeded": refresh_succeeded,
            "refresh_succeeded_zh": "是" if refresh_succeeded else "否",
            "refresh_error": refresh_error,
            "refresh_error_zh": zh_market_data_refresh_error(refresh_error),
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


def _moomoo_snapshot_rows(quotes: list[dict], *, fetched_at: str) -> pd.DataFrame:
    rows = []
    for quote in quotes:
        code = str(quote.get("code") or "").strip().upper()
        price = _first_number(quote.get("last_price"), quote.get("bid_price"), quote.get("ask_price"))
        if not code or price is None:
            continue
        parsed_time = pd.to_datetime(quote.get("update_time"), errors="coerce")
        rows.append(
            {
                "date": parsed_time.date().isoformat() if not pd.isna(parsed_time) else utc_now().date().isoformat(),
                "symbol": code.split(".")[-1],
                "close": float(price),
                "source": "moomoo_opend_snapshot",
                "source_ref": code,
                "fetched_at": fetched_at,
            }
        )
    return pd.DataFrame(rows, columns=["date", "symbol", "close", "source", "source_ref", "fetched_at"])


def _first_number(*values: object) -> float | None:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(number):
            continue
        return number
    return None


def zh_market_data_refresh_error(refresh_error: object) -> str:
    if refresh_error is None or refresh_error == "":
        return "无"
    text = str(refresh_error)
    if "Moomoo" in text:
        text = text.replace("Moomoo", "富途牛牛")
    if "public provider returned no usable market data" in text:
        return "公共行情源没有返回可用市场数据，已回退到本地数据。"
    if "public provider response missing columns" in text:
        return "公共行情源返回字段不完整，已回退到本地数据。"
    if "富途牛牛" in text:
        return text
    lowered = text.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "行情源连接超时，已回退到本地数据。"
    if "urlopen error" in lowered or "connection" in lowered:
        return "行情源连接失败，已回退到本地数据。"
    return "行情刷新失败，已回退到本地数据。"
