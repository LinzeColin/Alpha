from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class ApprovalQueue:
    """Small file-backed queue for owner-reviewed broker-ready tickets."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._tickets: list[dict] = []
        if self.path and self.path.exists():
            self._tickets = json.loads(self.path.read_text(encoding="utf-8"))

    def enqueue(self, ticket: dict) -> dict:
        if any(item.get("ticket_id") == ticket.get("ticket_id") for item in self._tickets):
            return {"status": "duplicate", "ticket": ticket}
        self._tickets.append(ticket)
        self._persist()
        return {"status": "queued", "ticket": ticket}

    def list_tickets(self) -> list[dict]:
        return list(self._tickets)

    def latest(self, limit: int = 20) -> list[dict]:
        return self._tickets[-limit:]

    def extend(self, tickets: Iterable[dict]) -> None:
        for ticket in tickets:
            self.enqueue(ticket)

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._tickets, indent=2, sort_keys=True), encoding="utf-8")
