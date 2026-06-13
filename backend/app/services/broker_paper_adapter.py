from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

from backend.app.services.paper_broker import PaperBroker, PaperOrder


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
            "paper_trade_count": len(self.paper_broker.trade_log),
            "latest_trade": latest_trade,
        }

    def submit_order(self, order: PaperOrder, *, source_ticket: dict | None = None) -> dict:
        result = self.paper_broker.submit_order(order)
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
            "broker_order_id": _paper_order_id(order.idempotency_key) if filled else None,
            "client_order_id": order.idempotency_key,
            "ticket_id": source_ticket.get("ticket_id") if source_ticket else None,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": _ticket_payload(source_ticket).get("order_type", "market"),
            "time_in_force": _ticket_payload(source_ticket).get("time_in_force", "day"),
            "submitted_at": _utc_now_iso(),
            "filled_quantity": order.quantity if filled else 0.0,
            "average_fill_price": order.price if filled else None,
            "estimated_notional": round(order.quantity * order.price, 2),
            "paper_result": result,
        }

    def skipped_receipt(self, order: PaperOrder, *, reason: str, source_ticket: dict | None = None) -> dict:
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
            "estimated_notional": round(order.quantity * order.price, 2),
            "paper_result": {"status": "skipped", "reason": reason},
        }


def _paper_order_id(idempotency_key: str) -> str:
    return f"paper_{sha256(idempotency_key.encode('utf-8')).hexdigest()[:16]}"


def _ticket_payload(ticket: dict | None) -> dict:
    if not ticket:
        return {}
    return ticket.get("broker_payload", {}) or {}
