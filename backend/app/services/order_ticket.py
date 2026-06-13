from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    strategy_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    time_in_force: str
    estimated_price: float
    estimated_notional_aud: float
    idempotency_key: str
    source_run_id: str
    created_at: str
    expires_at: str

    @classmethod
    def create(
        cls,
        *,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: float,
        estimated_price: float,
        source_run_id: str,
        ttl_seconds: int = 300,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> "OrderIntent":
        created = datetime.now(timezone.utc).replace(microsecond=0)
        intent_id = f"intent_{uuid4().hex[:12]}"
        idempotency_key = f"{source_run_id}:{strategy_id}:{symbol}:{side}:{quantity}:{created.isoformat()}"
        return cls(
            intent_id=intent_id,
            strategy_id=strategy_id,
            symbol=symbol.upper(),
            side=side.lower(),
            quantity=float(quantity),
            order_type=order_type,
            time_in_force=time_in_force,
            estimated_price=round(float(estimated_price), 4),
            estimated_notional_aud=round(float(quantity) * float(estimated_price), 4),
            idempotency_key=idempotency_key,
            source_run_id=source_run_id,
            created_at=created.isoformat(),
            expires_at=(created + timedelta(seconds=ttl_seconds)).isoformat(),
        )

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BrokerReadyOrderTicket:
    ticket_id: str
    status: str
    human_action_required: bool
    expires_at: str
    broker_payload: dict
    risk_check: dict
    intent: dict
    created_at: str

    @classmethod
    def from_intent(cls, intent: OrderIntent, risk_check: dict) -> "BrokerReadyOrderTicket":
        status = "pending_owner_approval" if risk_check.get("allowed") else "blocked_by_risk"
        broker_payload = {
            "symbol": intent.symbol,
            "side": intent.side,
            "quantity": intent.quantity,
            "order_type": intent.order_type,
            "time_in_force": intent.time_in_force,
            "estimated_price": intent.estimated_price,
            "client_order_id": intent.idempotency_key,
        }
        return cls(
            ticket_id=f"ticket_{uuid4().hex[:12]}",
            status=status,
            human_action_required=True,
            expires_at=intent.expires_at,
            broker_payload=broker_payload,
            risk_check=risk_check,
            intent=intent.as_dict(),
            created_at=utc_now_iso(),
        )

    def as_dict(self) -> dict:
        return asdict(self)
