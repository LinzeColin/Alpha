from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable, Protocol

import yaml

from backend.app.services.display_locale import (
    zh_account_ref,
    zh_adapter_id,
    zh_broker_name,
    zh_order_type,
    zh_reason,
    zh_side,
    zh_status,
    zh_time_in_force,
)
from backend.app.services.paper_broker import PaperBroker, PaperOrder


ALPACA_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
ALPACA_PAPER_KEY_ID_ENV = "ALPACA_PAPER_KEY_ID"
ALPACA_PAPER_SECRET_KEY_ENV = "ALPACA_PAPER_SECRET_KEY"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class PaperExecutionModel:
    model_id: str = "fixed_cost_slippage_v1"
    model_name_zh: str = "固定佣金与滑点模型"
    slippage_bps: float = 5.0
    commission_per_order: float = 1.0
    currency: str = "AUD"

    def apply(self, order: PaperOrder) -> tuple[PaperOrder, dict]:
        reference_price = float(order.price)
        side = str(order.side)
        direction = 1.0 if side == "buy" else -1.0 if side == "sell" else 0.0
        slippage_amount = reference_price * (self.slippage_bps / 10_000.0) * direction
        fill_price = round(reference_price + slippage_amount, 4)
        commission = round(float(self.commission_per_order), 2)
        adjusted_order = PaperOrder(
            idempotency_key=order.idempotency_key,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            reference_price=reference_price,
            commission=commission,
            slippage_bps=self.slippage_bps,
            execution_model_id=self.model_id,
        )
        return adjusted_order, {
            "execution_model_id": self.model_id,
            "execution_model_zh": self.model_name_zh,
            "slippage_bps": self.slippage_bps,
            "commission": commission,
            "currency": self.currency,
            "reference_price": reference_price,
            "simulated_fill_price": fill_price,
            "slippage_per_share": round(fill_price - reference_price, 4),
            "estimated_total_cost": round((fill_price * order.quantity) + commission if side == "buy" else commission, 2),
        }

    def as_dict(self) -> dict:
        return {
            "execution_model_id": self.model_id,
            "execution_model_zh": self.model_name_zh,
            "slippage_bps": self.slippage_bps,
            "commission_per_order": self.commission_per_order,
            "currency": self.currency,
        }


class PaperBrokerAdapter(Protocol):
    def status(self) -> dict:
        """Return broker-paper execution status that is safe to expose."""
        ...

    def submit_order(self, order: PaperOrder, *, source_ticket: dict | None = None) -> dict:
        """Submit a paper order and return a broker-like receipt."""
        ...

    def skipped_receipt(self, order: PaperOrder, *, reason: str, source_ticket: dict | None = None) -> dict:
        """Return a broker-like receipt for a risk-blocked or skipped paper order."""
        ...

    def external_snapshot(self) -> dict:
        """Return a safe external paper account snapshot when supported."""
        ...


def load_paper_broker_config(config_path: str | Path | None) -> dict:
    if config_path is None:
        return {"paper_broker": {"provider": "local_sandbox"}}
    path = Path(config_path)
    if not path.exists():
        return {"paper_broker": {"provider": "local_sandbox"}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("paper broker config must be a mapping")
    paper_broker = data.get("paper_broker") or {}
    if not isinstance(paper_broker, dict):
        raise ValueError("paper_broker config section must be a mapping")
    return {"paper_broker": paper_broker}


def build_paper_broker_adapter(
    paper_broker: PaperBroker,
    *,
    config_path: str | Path | None = None,
    config: dict | None = None,
) -> PaperBrokerAdapter:
    config_data = config or load_paper_broker_config(config_path)
    section = config_data.get("paper_broker") or {}
    provider = str(section.get("provider", "local_sandbox"))
    if provider == "local_sandbox":
        return LocalSandboxPaperBrokerAdapter(paper_broker)
    if provider == "alpaca_paper":
        if not section.get("allow_external_paper_api", False):
            return UnavailableExternalPaperBrokerAdapter(
                requested_provider=provider,
                reason="external paper broker adapter disabled by safety config",
            )
        external = section.get("external_paper_api") or {}
        if not isinstance(external, dict):
            return UnavailableExternalPaperBrokerAdapter(
                requested_provider=provider,
                reason="external paper broker adapter not configured",
            )
        return AlpacaPaperBrokerAdapter.from_config(external)
    if provider in {"external_paper_api", "ibkr_paper", "moomoo_paper"}:
        return UnavailableExternalPaperBrokerAdapter(
            requested_provider=provider,
            reason=_external_provider_block_reason(section),
        )
    return UnavailableExternalPaperBrokerAdapter(
        requested_provider=provider,
        reason="external paper broker adapter not configured",
    )


@dataclass
class LocalSandboxPaperBrokerAdapter:
    paper_broker: PaperBroker
    execution_model: PaperExecutionModel = PaperExecutionModel()
    adapter_id: str = "local_sandbox_paper_broker"
    broker_name: str = "Alpha Local Sandbox"
    account_ref: str = "local_paper_account"

    def status(self) -> dict:
        latest_trade = self.paper_broker.trade_log[-1] if self.paper_broker.trade_log else None
        return {
            "provider": "local_sandbox",
            "provider_zh": "本地沙盒模拟交易",
            "adapter_id": self.adapter_id,
            "adapter_id_zh": zh_adapter_id(self.adapter_id),
            "adapter_readiness": "ready",
            "adapter_readiness_zh": zh_status("ready"),
            "broker_name": self.broker_name,
            "broker_name_zh": zh_broker_name(self.broker_name),
            "mode": "paper",
            "mode_zh": zh_status("paper"),
            "paper_order_submission_enabled": True,
            "paper_order_submission_enabled_zh": "是",
            "external_paper_api_enabled": False,
            "external_paper_api_enabled_zh": "否",
            "account_ref": self.account_ref,
            "account_ref_zh": zh_account_ref(self.account_ref),
            "connected": True,
            "connected_zh": "是",
            "credential_required": False,
            "credential_required_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "supports_market_orders": True,
            "supports_market_orders_zh": "是",
            "supports_real_broker_place_order": False,
            "supports_real_broker_place_order_zh": "否",
            "execution_model": self.execution_model.as_dict(),
            "execution_model_zh": self.execution_model.model_name_zh,
            "slippage_bps": self.execution_model.slippage_bps,
            "commission_per_order": self.execution_model.commission_per_order,
            "total_commission": round(sum(float(row.get("commission", 0.0) or 0.0) for row in self.paper_broker.trade_log), 2),
            "paper_trade_count": len(self.paper_broker.trade_log),
            "latest_trade": latest_trade,
        }

    def submit_order(self, order: PaperOrder, *, source_ticket: dict | None = None) -> dict:
        simulated_order, execution = self.execution_model.apply(order)
        result = self.paper_broker.submit_order(simulated_order)
        status = str(result.get("status", "unknown"))
        filled = status == "filled"
        return {
            "provider": "local_sandbox",
            "provider_zh": "本地沙盒模拟交易",
            "adapter_id": self.adapter_id,
            "adapter_id_zh": zh_adapter_id(self.adapter_id),
            "adapter_readiness": "ready",
            "adapter_readiness_zh": zh_status("ready"),
            "broker_name": self.broker_name,
            "broker_name_zh": zh_broker_name(self.broker_name),
            "mode": "paper",
            "mode_zh": zh_status("paper"),
            "paper_order_submission_enabled": True,
            "paper_order_submission_enabled_zh": "是",
            "external_paper_api_enabled": False,
            "external_paper_api_enabled_zh": "否",
            "account_ref": self.account_ref,
            "account_ref_zh": zh_account_ref(self.account_ref),
            "connected": True,
            "connected_zh": "是",
            "credential_required": False,
            "credential_required_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "status": status,
            "status_zh": zh_status(status),
            "reason": result.get("reason"),
            "reason_zh": zh_reason(result.get("reason")),
            "broker_order_id": _paper_order_id(simulated_order.idempotency_key) if filled else None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "side_zh": zh_side(order.side),
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "order_type_zh": zh_order_type(_ticket_payload(source_ticket).get("order_type", "market")),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
            "time_in_force_zh": zh_time_in_force(_ticket_payload(source_ticket).get("time_in_force", "day")),
            "submitted_at": _utc_now_iso(),
            "filled_quantity": order.quantity if filled else 0.0,
            "average_fill_price": simulated_order.price if filled else None,
            "reference_price": execution["reference_price"],
            "estimated_notional": round(order.quantity * order.price, 2),
            "gross_fill_notional": round(simulated_order.quantity * simulated_order.price, 2) if filled else None,
            "commission": execution["commission"] if filled else 0.0,
            "slippage_bps": execution["slippage_bps"],
            "slippage_per_share": execution["slippage_per_share"] if filled else None,
            "execution_model_id": execution["execution_model_id"],
            "execution_model_zh": execution["execution_model_zh"],
            "execution_cost_zh": _execution_cost_zh(execution, filled=filled),
            "paper_result": result,
        }

    def skipped_receipt(self, order: PaperOrder, *, reason: str, source_ticket: dict | None = None) -> dict:
        _, execution = self.execution_model.apply(order)
        return {
            "provider": "local_sandbox",
            "provider_zh": "本地沙盒模拟交易",
            "adapter_id": self.adapter_id,
            "adapter_id_zh": zh_adapter_id(self.adapter_id),
            "adapter_readiness": "ready",
            "adapter_readiness_zh": zh_status("ready"),
            "broker_name": self.broker_name,
            "broker_name_zh": zh_broker_name(self.broker_name),
            "mode": "paper",
            "mode_zh": zh_status("paper"),
            "paper_order_submission_enabled": True,
            "paper_order_submission_enabled_zh": "是",
            "external_paper_api_enabled": False,
            "external_paper_api_enabled_zh": "否",
            "account_ref": self.account_ref,
            "account_ref_zh": zh_account_ref(self.account_ref),
            "connected": True,
            "connected_zh": "是",
            "credential_required": False,
            "credential_required_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "status": "skipped",
            "status_zh": zh_status("skipped"),
            "reason": reason,
            "reason_zh": zh_reason(reason),
            "broker_order_id": None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "side_zh": zh_side(order.side),
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "order_type_zh": zh_order_type(_ticket_payload(source_ticket).get("order_type", "market")),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
            "time_in_force_zh": zh_time_in_force(_ticket_payload(source_ticket).get("time_in_force", "day")),
            "submitted_at": _utc_now_iso(),
            "filled_quantity": 0.0,
            "average_fill_price": None,
            "reference_price": execution["reference_price"],
            "estimated_notional": round(order.quantity * order.price, 2),
            "gross_fill_notional": None,
            "commission": 0.0,
            "slippage_bps": execution["slippage_bps"],
            "slippage_per_share": None,
            "execution_model_id": execution["execution_model_id"],
            "execution_model_zh": execution["execution_model_zh"],
            "execution_cost_zh": "未成交，未产生模拟成交成本。",
            "paper_result": {"status": "skipped", "reason": reason},
        }

    def external_snapshot(self) -> dict:
        return _external_snapshot_unavailable(
            provider="local_sandbox",
            provider_zh="本地沙盒模拟交易",
            reason="external paper broker read only sync unavailable",
            reason_zh="本地沙盒不需要外部纸面账户同步。",
        )


@dataclass
class UnavailableExternalPaperBrokerAdapter:
    requested_provider: str
    reason: str
    adapter_id: str = "external_paper_api_unavailable"
    broker_name: str = "External Paper API"

    def status(self) -> dict:
        return {
            "provider": self.requested_provider,
            "provider_zh": _paper_provider_zh(self.requested_provider),
            "adapter_id": self.adapter_id,
            "adapter_id_zh": zh_adapter_id(self.adapter_id),
            "adapter_readiness": "not_configured",
            "adapter_readiness_zh": zh_status("not_configured"),
            "broker_name": self.broker_name,
            "broker_name_zh": zh_broker_name(self.broker_name),
            "mode": "paper",
            "mode_zh": zh_status("paper"),
            "account_ref": "external_paper_account",
            "account_ref_zh": "外部纸面账户",
            "connected": False,
            "connected_zh": "否",
            "credential_required": True,
            "credential_required_zh": "是",
            "paper_order_submission_enabled": False,
            "paper_order_submission_enabled_zh": "否",
            "external_paper_api_enabled": False,
            "external_paper_api_enabled_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "supports_market_orders": False,
            "supports_market_orders_zh": "否",
            "supports_real_broker_place_order": False,
            "supports_real_broker_place_order_zh": "否",
            "reason": self.reason,
            "reason_zh": zh_reason(self.reason),
            "next_step_zh": "先完成外部 paper API 适配器、凭据隔离、纸面模式证明和回归测试；未完成前继续使用本地沙盒模拟交易。",
            "execution_model": {},
            "execution_model_zh": "外部纸面交易 API 未就绪",
            "slippage_bps": 0.0,
            "commission_per_order": 0.0,
            "total_commission": 0.0,
            "paper_trade_count": 0,
            "latest_trade": None,
        }

    def submit_order(self, order: PaperOrder, *, source_ticket: dict | None = None) -> dict:
        return self.skipped_receipt(
            order,
            reason="external paper broker paper order submission unavailable",
            source_ticket=source_ticket,
        )

    def skipped_receipt(self, order: PaperOrder, *, reason: str, source_ticket: dict | None = None) -> dict:
        status = self.status()
        return {
            **status,
            "status": "skipped",
            "status_zh": zh_status("skipped"),
            "reason": reason,
            "reason_zh": zh_reason(reason),
            "broker_order_id": None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "side_zh": zh_side(order.side),
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "order_type_zh": zh_order_type(_ticket_payload(source_ticket).get("order_type", "market")),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
            "time_in_force_zh": zh_time_in_force(_ticket_payload(source_ticket).get("time_in_force", "day")),
            "submitted_at": _utc_now_iso(),
            "filled_quantity": 0.0,
            "average_fill_price": None,
            "reference_price": order.price,
            "estimated_notional": round(order.quantity * order.price, 2),
            "gross_fill_notional": None,
            "commission": 0.0,
            "slippage_bps": 0.0,
            "slippage_per_share": None,
            "execution_model_id": "external_paper_api_unavailable",
            "execution_model_zh": "外部纸面交易 API 未就绪",
            "execution_cost_zh": "未成交，未产生纸面交易成本。",
            "paper_result": {"status": "skipped", "reason": reason, "reason_zh": zh_reason(reason)},
        }

    def external_snapshot(self) -> dict:
        return _external_snapshot_unavailable(
            provider=self.requested_provider,
            provider_zh=_paper_provider_zh(self.requested_provider),
            reason=self.reason,
            reason_zh=zh_reason(self.reason),
        )


@dataclass
class AlpacaPaperBrokerAdapter:
    base_url: str = ALPACA_PAPER_BASE_URL
    key_id_env: str = ALPACA_PAPER_KEY_ID_ENV
    secret_key_env: str = ALPACA_PAPER_SECRET_KEY_ENV
    timeout_seconds: float = 10.0
    read_only_sync_enabled: bool = False
    order_submission_enabled: bool = False
    http_post_json: Callable[[str, dict, dict, float], dict] | None = None
    http_get_json: Callable[[str, dict, float], dict | list] | None = None
    adapter_id: str = "alpaca_paper_broker"
    broker_name: str = "Alpaca Paper"

    @classmethod
    def from_config(cls, config: dict) -> "AlpacaPaperBrokerAdapter":
        return cls(
            base_url=str(config.get("base_url", ALPACA_PAPER_BASE_URL)).rstrip("/"),
            key_id_env=str(config.get("key_id_env", ALPACA_PAPER_KEY_ID_ENV)),
            secret_key_env=str(config.get("secret_key_env", ALPACA_PAPER_SECRET_KEY_ENV)),
            timeout_seconds=float(config.get("timeout_seconds", 10.0)),
            read_only_sync_enabled=bool(config.get("read_only_sync_enabled", False)),
            order_submission_enabled=bool(config.get("order_submission_enabled", False)),
        )

    def status(self) -> dict:
        readiness, reason = self._readiness()
        credentials_present = self._credentials_present()
        ready = readiness == "ready"
        paper_order_enabled = ready and self.order_submission_enabled
        read_only_ready = ready and self.read_only_sync_enabled
        return {
            "provider": "alpaca_paper",
            "provider_zh": _paper_provider_zh("alpaca_paper"),
            "adapter_id": self.adapter_id,
            "adapter_id_zh": zh_adapter_id(self.adapter_id),
            "adapter_readiness": readiness,
            "adapter_readiness_zh": zh_status(readiness),
            "broker_name": self.broker_name,
            "broker_name_zh": zh_broker_name(self.broker_name),
            "mode": "paper",
            "mode_zh": zh_status("paper"),
            "account_ref": "alpaca_paper_account_env",
            "account_ref_zh": "Alpaca 纸面账户",
            "connected": readiness == "ready",
            "connected_zh": "是" if readiness == "ready" else "否",
            "credential_required": True,
            "credential_required_zh": "是",
            "credentials_present": credentials_present,
            "credentials_present_zh": "是" if credentials_present else "否",
            "credential_source": "environment_variables",
            "credential_source_zh": "环境变量",
            "base_url": self.base_url,
            "paper_base_url_allowed": _is_allowed_alpaca_paper_base_url(self.base_url),
            "paper_base_url_allowed_zh": "是" if _is_allowed_alpaca_paper_base_url(self.base_url) else "否",
            "read_only_sync_enabled": self.read_only_sync_enabled,
            "read_only_sync_enabled_zh": "是" if self.read_only_sync_enabled else "否",
            "read_only_sync_ready": read_only_ready,
            "read_only_sync_ready_zh": "是" if read_only_ready else "否",
            "paper_order_submission_enabled": paper_order_enabled,
            "paper_order_submission_enabled_zh": "是" if paper_order_enabled else "否",
            "external_paper_api_enabled": read_only_ready or paper_order_enabled,
            "external_paper_api_enabled_zh": "是" if read_only_ready or paper_order_enabled else "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "supports_market_orders": paper_order_enabled,
            "supports_market_orders_zh": "是" if paper_order_enabled else "否",
            "supports_real_broker_place_order": False,
            "supports_real_broker_place_order_zh": "否",
            "reason": reason,
            "reason_zh": zh_reason(reason),
            "next_step_zh": "仅在确认 Alpaca paper key、paper base URL 和回归测试通过后启用；不得使用 live endpoint 或 live key。",
            "execution_model": {"execution_model_id": "alpaca_paper_api_v1", "execution_model_zh": "Alpaca Paper API 模拟撮合"},
            "execution_model_zh": "Alpaca Paper API 模拟撮合",
            "slippage_bps": 0.0,
            "commission_per_order": 0.0,
            "total_commission": 0.0,
            "paper_trade_count": 0,
            "latest_trade": None,
        }

    def submit_order(self, order: PaperOrder, *, source_ticket: dict | None = None) -> dict:
        readiness, reason = self._readiness()
        if readiness != "ready":
            return self.skipped_receipt(order, reason=reason, source_ticket=source_ticket)
        if not self.order_submission_enabled:
            return self.skipped_receipt(
                order,
                reason="external paper broker paper order submission unavailable",
                source_ticket=source_ticket,
            )

        try:
            payload = _alpaca_order_payload(order, source_ticket=source_ticket)
        except RuntimeError as exc:
            return {
                **self._receipt_base(order, source_ticket=source_ticket),
                "status": "skipped",
                "status_zh": zh_status("skipped"),
                "reason": "alpaca paper order rejected",
                "reason_zh": f"{zh_reason('alpaca paper order rejected')}：{exc}",
                "paper_result": {"status": "skipped", "reason": "alpaca paper order rejected", "reason_zh": zh_reason("alpaca paper order rejected")},
            }
        headers = self._headers()
        try:
            response = (self.http_post_json or _post_json)(f"{self.base_url}/v2/orders", payload, headers, self.timeout_seconds)
        except RuntimeError as exc:
            safe_error = _redact_values(str(exc), self._credential_values())
            return {
                **self._receipt_base(order, source_ticket=source_ticket),
                "status": "skipped",
                "status_zh": zh_status("skipped"),
                "reason": "alpaca paper api request failed",
                "reason_zh": f"{zh_reason('alpaca paper api request failed')}：{safe_error}",
                "paper_result": {"status": "skipped", "reason": "alpaca paper api request failed", "reason_zh": zh_reason("alpaca paper api request failed")},
            }

        provider_status = str(response.get("status") or "submitted")
        return {
            **self._receipt_base(order, source_ticket=source_ticket),
            "status": "submitted",
            "status_zh": zh_status("submitted"),
            "reason": "alpaca paper order submitted",
            "reason_zh": zh_reason("alpaca paper order submitted"),
            "broker_order_id": response.get("id"),
            "provider_order_status": provider_status,
            "provider_order_status_zh": _alpaca_order_status_zh(provider_status),
            "submitted_at": response.get("submitted_at") or _utc_now_iso(),
            "filled_quantity": _float_or_zero(response.get("filled_qty")),
            "average_fill_price": _float_or_none(response.get("filled_avg_price")),
            "paper_result": {
                "status": "submitted",
                "status_zh": zh_status("submitted"),
                "reason": "alpaca paper order submitted",
                "reason_zh": zh_reason("alpaca paper order submitted"),
                "provider_order_status": provider_status,
                "provider_order_status_zh": _alpaca_order_status_zh(provider_status),
                "provider_response": _sanitize_alpaca_order_response(response),
            },
        }

    def skipped_receipt(self, order: PaperOrder, *, reason: str, source_ticket: dict | None = None) -> dict:
        return {
            **self._receipt_base(order, source_ticket=source_ticket),
            "status": "skipped",
            "status_zh": zh_status("skipped"),
            "reason": reason,
            "reason_zh": zh_reason(reason),
            "paper_result": {"status": "skipped", "reason": reason, "reason_zh": zh_reason(reason)},
        }

    def external_snapshot(self) -> dict:
        readiness, reason = self._readiness()
        if readiness != "ready":
            return _external_snapshot_unavailable(
                provider="alpaca_paper",
                provider_zh=_paper_provider_zh("alpaca_paper"),
                reason=reason,
                reason_zh=zh_reason(reason),
            )
        if not self.read_only_sync_enabled:
            return _external_snapshot_unavailable(
                provider="alpaca_paper",
                provider_zh=_paper_provider_zh("alpaca_paper"),
                reason="external paper broker read only sync unavailable",
                reason_zh=zh_reason("external paper broker read only sync unavailable"),
            )
        headers = self._headers()
        try:
            account = (self.http_get_json or _get_json)(f"{self.base_url}/v2/account", headers, self.timeout_seconds)
            positions = (self.http_get_json or _get_json)(f"{self.base_url}/v2/positions", headers, self.timeout_seconds)
            orders_url = f"{self.base_url}/v2/orders?status=all&limit=50"
            orders = (self.http_get_json or _get_json)(orders_url, headers, self.timeout_seconds)
        except RuntimeError as exc:
            safe_error = _redact_values(str(exc), self._credential_values())
            return {
                **_external_snapshot_unavailable(
                    provider="alpaca_paper",
                    provider_zh=_paper_provider_zh("alpaca_paper"),
                    reason="alpaca paper api request failed",
                    reason_zh=f"{zh_reason('alpaca paper api request failed')}：{safe_error}",
                ),
                "read_only_sync_enabled": True,
                "read_only_sync_enabled_zh": "是",
            }
        safe_account = _sanitize_alpaca_account(account if isinstance(account, dict) else {})
        safe_positions = [_sanitize_alpaca_position(item) for item in positions] if isinstance(positions, list) else []
        safe_orders = [_sanitize_alpaca_order_response(item) | {"status_zh": _alpaca_order_status_zh(str(item.get("status", "")))} for item in orders] if isinstance(orders, list) else []
        return {
            "status": "ready",
            "status_zh": "已同步",
            "provider": "alpaca_paper",
            "provider_zh": _paper_provider_zh("alpaca_paper"),
            "generated_at": _utc_now_iso(),
            "base_url": self.base_url,
            "read_only_sync_enabled": True,
            "read_only_sync_enabled_zh": "是",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
            "account": safe_account,
            "positions": safe_positions,
            "recent_orders": safe_orders,
            "position_count": len(safe_positions),
            "recent_order_count": len(safe_orders),
            "summary_zh": f"Alpaca 纸面账户同步完成：持仓 {len(safe_positions)} 个，最近订单 {len(safe_orders)} 条。",
        }

    def _receipt_base(self, order: PaperOrder, *, source_ticket: dict | None) -> dict:
        status = self.status()
        return {
            **status,
            "broker_order_id": None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "side_zh": zh_side(order.side),
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "order_type_zh": zh_order_type(_ticket_payload(source_ticket).get("order_type", "market")),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
            "time_in_force_zh": zh_time_in_force(_ticket_payload(source_ticket).get("time_in_force", "day")),
            "submitted_at": _utc_now_iso(),
            "filled_quantity": 0.0,
            "average_fill_price": None,
            "reference_price": order.price,
            "estimated_notional": round(order.quantity * order.price, 2),
            "gross_fill_notional": None,
            "commission": 0.0,
            "slippage_bps": 0.0,
            "slippage_per_share": None,
            "execution_model_id": "alpaca_paper_api_v1",
            "execution_model_zh": "Alpaca Paper API 模拟撮合",
            "execution_cost_zh": "外部纸面交易 API 回执；本地不估算滑点和佣金。",
        }

    def _credentials_present(self) -> bool:
        return bool(os.environ.get(self.key_id_env) and os.environ.get(self.secret_key_env))

    def _credential_values(self) -> tuple[str | None, str | None]:
        return os.environ.get(self.key_id_env), os.environ.get(self.secret_key_env)

    def _headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": os.environ.get(self.key_id_env, ""),
            "APCA-API-SECRET-KEY": os.environ.get(self.secret_key_env, ""),
            "Content-Type": "application/json",
        }

    def _readiness(self) -> tuple[str, str]:
        if not _is_allowed_alpaca_paper_base_url(self.base_url):
            return "not_configured", "external paper broker base url not allowed"
        if not self._credentials_present():
            return "not_configured", "external paper broker credentials missing"
        return "ready", "alpaca paper adapter ready"


def _external_provider_block_reason(section: dict) -> str:
    if not section.get("allow_external_paper_api", False):
        return "external paper broker adapter disabled by safety config"
    external = section.get("external_paper_api") or {}
    if not isinstance(external, dict) or not external.get("order_submission_enabled", False):
        return "external paper broker paper order submission unavailable"
    return "external paper broker adapter not configured"


def _paper_provider_zh(provider: str) -> str:
    return {
        "local_sandbox": "本地沙盒模拟交易",
        "external_paper_api": "外部纸面交易 API",
        "alpaca_paper": "Alpaca 纸面交易 API",
        "ibkr_paper": "IBKR 纸面交易 API",
        "moomoo_paper": "富途牛牛纸面交易 API",
    }.get(provider, "未知纸面交易提供方")


def _paper_order_id(idempotency_key: str) -> str:
    return f"paper_{sha256(idempotency_key.encode('utf-8')).hexdigest()[:16]}"


def _ticket_payload(ticket: dict | None) -> dict:
    if not ticket:
        return {}
    return ticket.get("broker_payload", {}) or {}


def _execution_cost_zh(execution: dict, *, filled: bool) -> str:
    if not filled:
        return "未成交，未产生模拟成交成本。"
    return (
        f"{execution['execution_model_zh']}："
        f"滑点 {execution['slippage_bps']:.2f} 基点，"
        f"佣金 {execution['commission']:.2f} {execution['currency']}。"
    )


def _is_allowed_alpaca_paper_base_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    return parsed.scheme == "https" and parsed.netloc == "paper-api.alpaca.markets" and parsed.path in {"", "/"}


def _alpaca_order_payload(order: PaperOrder, *, source_ticket: dict | None) -> dict:
    payload = _ticket_payload(source_ticket)
    order_type = str(payload.get("order_type", "market"))
    time_in_force = str(payload.get("time_in_force", "day"))
    if order_type != "market" or time_in_force != "day":
        raise RuntimeError("Alpaca paper adapter currently allows market/day orders only")
    return {
        "symbol": order.symbol,
        "qty": _format_quantity(order.quantity),
        "side": order.side,
        "type": "market",
        "time_in_force": "day",
        "client_order_id": order.idempotency_key,
    }


def _format_quantity(quantity: float) -> str:
    if float(quantity).is_integer():
        return str(int(quantity))
    return f"{float(quantity):.8f}".rstrip("0").rstrip(".")


def _post_json(url: str, payload: dict, headers: dict, timeout_seconds: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_redact_values(body, _alpaca_header_redaction_values(headers))}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("Alpaca paper API response is not an object")
    return value


def _get_json(url: str, headers: dict, timeout_seconds: float) -> dict | list:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_redact_values(body, _alpaca_header_redaction_values(headers))}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    value = json.loads(text)
    if not isinstance(value, (dict, list)):
        raise RuntimeError("Alpaca paper API response is not an object or list")
    return value


def _external_snapshot_unavailable(*, provider: str, provider_zh: str, reason: str, reason_zh: str) -> dict:
    return {
        "status": "not_configured",
        "status_zh": zh_status("not_configured"),
        "provider": provider,
        "provider_zh": provider_zh,
        "generated_at": _utc_now_iso(),
        "read_only_sync_enabled": False,
        "read_only_sync_enabled_zh": "否",
        "live_order_submission_enabled": False,
        "live_order_submission_enabled_zh": "否",
        "reason": reason,
        "reason_zh": reason_zh,
        "account": {},
        "positions": [],
        "recent_orders": [],
        "position_count": 0,
        "recent_order_count": 0,
        "summary_zh": reason_zh,
    }


def _sanitize_alpaca_account(account: dict) -> dict:
    return {
        "account_id_present": bool(account.get("id")),
        "account_number_present": bool(account.get("account_number")),
        "account_identifier_redacted_zh": "账户标识已隐藏",
        "status": account.get("status"),
        "status_zh": _alpaca_account_status_zh(str(account.get("status", ""))),
        "currency": account.get("currency"),
        "cash": _float_or_none(account.get("cash")),
        "buying_power": _float_or_none(account.get("buying_power")),
        "equity": _float_or_none(account.get("equity")),
        "portfolio_value": _float_or_none(account.get("portfolio_value")),
        "long_market_value": _float_or_none(account.get("long_market_value")),
        "short_market_value": _float_or_none(account.get("short_market_value")),
        "trading_blocked": bool(account.get("trading_blocked", False)),
        "transfers_blocked": bool(account.get("transfers_blocked", False)),
        "account_blocked": bool(account.get("account_blocked", False)),
        "pattern_day_trader": bool(account.get("pattern_day_trader", False)),
    }


def _sanitize_alpaca_position(position: dict) -> dict:
    return {
        "symbol": position.get("symbol"),
        "asset_class": position.get("asset_class"),
        "side": position.get("side"),
        "side_zh": {"long": "多头", "short": "空头"}.get(str(position.get("side")), "未知方向"),
        "qty": _float_or_none(position.get("qty")),
        "avg_entry_price": _float_or_none(position.get("avg_entry_price")),
        "market_value": _float_or_none(position.get("market_value")),
        "cost_basis": _float_or_none(position.get("cost_basis")),
        "unrealized_pl": _float_or_none(position.get("unrealized_pl")),
        "unrealized_plpc": _float_or_none(position.get("unrealized_plpc")),
        "current_price": _float_or_none(position.get("current_price")),
        "lastday_price": _float_or_none(position.get("lastday_price")),
        "change_today": _float_or_none(position.get("change_today")),
    }


def _sanitize_alpaca_order_response(response: dict) -> dict:
    allowed_keys = {
        "id",
        "client_order_id",
        "created_at",
        "updated_at",
        "submitted_at",
        "filled_at",
        "expired_at",
        "canceled_at",
        "failed_at",
        "replaced_at",
        "asset_id",
        "symbol",
        "asset_class",
        "qty",
        "filled_qty",
        "type",
        "side",
        "time_in_force",
        "limit_price",
        "stop_price",
        "filled_avg_price",
        "status",
        "extended_hours",
    }
    return {key: value for key, value in response.items() if key in allowed_keys}


def _alpaca_header_redaction_values(headers: dict) -> tuple[object, ...]:
    return (
        headers.get("APCA-API-KEY-ID"),
        headers.get("APCA-API-SECRET-KEY"),
        os.environ.get(ALPACA_PAPER_KEY_ID_ENV),
        os.environ.get(ALPACA_PAPER_SECRET_KEY_ENV),
    )


def _redact_values(text: str, values: tuple[object, ...]) -> str:
    redacted = text
    for value in values:
        if value:
            redacted = redacted.replace(str(value), "[redacted]")
    return redacted


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: object) -> float:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else 0.0


def _alpaca_order_status_zh(status: str) -> str:
    return {
        "new": "新订单",
        "accepted": "已接受",
        "pending_new": "等待创建",
        "partially_filled": "部分成交",
        "filled": "已成交",
        "done_for_day": "当日完成",
        "canceled": "已取消",
        "expired": "已过期",
        "replaced": "已替换",
        "pending_cancel": "等待取消",
        "pending_replace": "等待替换",
        "accepted_for_bidding": "已接受竞价",
        "stopped": "已停止",
        "rejected": "已拒绝",
        "suspended": "已暂停",
        "calculated": "已计算",
    }.get(status, "未知订单状态")


def _alpaca_account_status_zh(status: str) -> str:
    return {
        "ACTIVE": "正常",
        "ACCOUNT_UPDATED": "账户已更新",
        "APPROVAL_PENDING": "等待审批",
        "APPROVED": "已审批",
        "REJECTED": "已拒绝",
        "ONBOARDING": "开户中",
        "SUBMISSION_FAILED": "提交失败",
        "DISABLED": "已停用",
    }.get(status, "未知账户状态")
