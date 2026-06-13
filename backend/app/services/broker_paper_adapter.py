from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

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
            "adapter_id": self.adapter_id,
            "broker_name": self.broker_name,
            "mode": "paper",
            "account_ref": self.account_ref,
            "connected": True,
            "credential_required": False,
            "live_order_submission_enabled": False,
            "supports_market_orders": True,
            "supports_real_broker_place_order": False,
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
            "adapter_id": self.adapter_id,
            "broker_name": self.broker_name,
            "mode": "paper",
            "account_ref": self.account_ref,
            "connected": True,
            "credential_required": False,
            "live_order_submission_enabled": False,
            "status": status,
            "reason": result.get("reason"),
            "broker_order_id": _paper_order_id(simulated_order.idempotency_key) if filled else None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
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
            "adapter_id": self.adapter_id,
            "broker_name": self.broker_name,
            "mode": "paper",
            "account_ref": self.account_ref,
            "connected": True,
            "credential_required": False,
            "live_order_submission_enabled": False,
            "status": "skipped",
            "reason": reason,
            "broker_order_id": None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
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
