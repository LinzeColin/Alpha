from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class PaperOrder:
    idempotency_key: str
    symbol: str
    side: str
    quantity: float
    price: float


@dataclass
class PaperBroker:
    cash: float = 10000.0
    positions: Dict[str, float] = field(default_factory=dict)
    seen_keys: Set[str] = field(default_factory=set)

    def submit_order(self, order: PaperOrder) -> dict:
        if order.idempotency_key in self.seen_keys:
            return {"status": "rejected", "reason": "duplicate idempotency key"}
        if order.quantity <= 0 or order.price <= 0:
            return {"status": "rejected", "reason": "invalid quantity or price"}
        notional = order.quantity * order.price
        if order.side == "buy":
            if notional > self.cash:
                return {"status": "rejected", "reason": "insufficient paper cash"}
            self.cash -= notional
            self.positions[order.symbol] = self.positions.get(order.symbol, 0.0) + order.quantity
        elif order.side == "sell":
            current = self.positions.get(order.symbol, 0.0)
            if order.quantity > current:
                return {"status": "rejected", "reason": "insufficient paper position"}
            self.positions[order.symbol] = current - order.quantity
            self.cash += notional
        else:
            return {"status": "rejected", "reason": "invalid side"}
        self.seen_keys.add(order.idempotency_key)
        return {"status": "filled", "cash": round(self.cash, 2), "positions": dict(self.positions)}
