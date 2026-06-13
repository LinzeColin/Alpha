from __future__ import annotations

import json
from datetime import datetime, timezone
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

    def latest_with_freshness(self, limit: int = 20, *, now: datetime | None = None) -> list[dict]:
        return [annotate_ticket_freshness(ticket, now=now) for ticket in self.latest(limit)]

    def summary(self, *, now: datetime | None = None) -> dict:
        annotated = [annotate_ticket_freshness(ticket, now=now) for ticket in self._tickets]
        fresh_pending = [ticket for ticket in annotated if ticket.get("actionability") == "fresh_pending_owner_approval"]
        expired_pending = [ticket for ticket in annotated if ticket.get("actionability") == "expired_owner_approval"]
        blocked = [ticket for ticket in annotated if ticket.get("status") == "blocked_by_risk"]
        return {
            "total_count": len(annotated),
            "fresh_pending_count": len(fresh_pending),
            "expired_pending_count": len(expired_pending),
            "blocked_count": len(blocked),
            "latest_fresh_ticket_created_at": fresh_pending[-1].get("created_at") if fresh_pending else None,
            "latest_ticket_created_at": annotated[-1].get("created_at") if annotated else None,
        }

    def extend(self, tickets: Iterable[dict]) -> None:
        for ticket in tickets:
            self.enqueue(ticket)

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._tickets, indent=2, sort_keys=True), encoding="utf-8")


def annotate_ticket_freshness(ticket: dict, *, now: datetime | None = None) -> dict:
    annotated = dict(ticket)
    expires_at = annotated.get("expires_at") or annotated.get("intent", {}).get("expires_at")
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    freshness = _freshness(expires_at, now=now)
    annotated["freshness"] = freshness
    if annotated.get("status") == "pending_owner_approval":
        annotated["actionability"] = "fresh_pending_owner_approval" if freshness["status"] == "fresh" else "expired_owner_approval"
    elif annotated.get("status") == "blocked_by_risk":
        annotated["actionability"] = "blocked_by_risk"
    else:
        annotated["actionability"] = annotated.get("status", "unknown")
    return annotated


def _freshness(expires_at: str | None, *, now: datetime) -> dict:
    if not expires_at:
        return {"status": "unknown", "expires_at": None, "seconds_until_expiry": None}
    expires = _parse_iso_datetime(expires_at)
    if not expires:
        return {"status": "invalid", "expires_at": expires_at, "seconds_until_expiry": None}
    seconds_until_expiry = int((expires - now).total_seconds())
    return {
        "status": "fresh" if seconds_until_expiry > 0 else "expired",
        "expires_at": expires.isoformat(),
        "seconds_until_expiry": seconds_until_expiry,
    }


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
