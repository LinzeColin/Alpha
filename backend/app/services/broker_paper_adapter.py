from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Protocol

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
    if provider in {"external_paper_api", "alpaca_paper", "ibkr_paper", "moomoo_paper"}:
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
