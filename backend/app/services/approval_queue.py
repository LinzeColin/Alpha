from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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

    def get_ticket(self, ticket_id: str) -> dict | None:
        for ticket in self._tickets:
            if ticket.get("ticket_id") == ticket_id:
                return dict(ticket)
        return None

    def latest(self, limit: int = 20) -> list[dict]:
        return self._tickets[-limit:]

    def latest_with_freshness(self, limit: int = 20, *, now: datetime | None = None) -> list[dict]:
        return [annotate_ticket_freshness(ticket, now=now) for ticket in self.latest(limit)]

    def summary(self, *, now: datetime | None = None) -> dict:
        annotated = [annotate_ticket_freshness(ticket, now=now) for ticket in self._tickets]
        fresh_pending = [ticket for ticket in annotated if ticket.get("actionability") == "fresh_pending_owner_approval"]
        expired_pending = [ticket for ticket in annotated if ticket.get("actionability") == "expired_owner_approval"]
        blocked = [ticket for ticket in annotated if ticket.get("status") == "blocked_by_risk"]
        owner_reviewed = [ticket for ticket in annotated if ticket.get("status") == "owner_reviewed"]
        owner_rejected = [ticket for ticket in annotated if ticket.get("status") == "owner_rejected"]
        exported = [ticket for ticket in annotated if ticket.get("status") == "broker_ticket_exported"]
        return {
            "total_count": len(annotated),
            "fresh_pending_count": len(fresh_pending),
            "expired_pending_count": len(expired_pending),
            "blocked_count": len(blocked),
            "owner_reviewed_count": len(owner_reviewed),
            "owner_rejected_count": len(owner_rejected),
            "broker_ticket_exported_count": len(exported),
            "latest_fresh_ticket_created_at": fresh_pending[-1].get("created_at") if fresh_pending else None,
            "latest_ticket_created_at": annotated[-1].get("created_at") if annotated else None,
        }

    def extend(self, tickets: Iterable[dict]) -> None:
        for ticket in tickets:
            self.enqueue(ticket)

    def mark_owner_reviewed(self, ticket_id: str, *, actor_id: str = "owner", note: str | None = None) -> dict:
        return self._transition_ticket(
            ticket_id,
            "owner_reviewed",
            actor_id=actor_id,
            action="owner_reviewed_for_manual_broker_confirmation",
            note=note,
        )

    def reject(self, ticket_id: str, *, actor_id: str = "owner", note: str | None = None) -> dict:
        return self._transition_ticket(
            ticket_id,
            "owner_rejected",
            actor_id=actor_id,
            action="owner_rejected_order_ticket",
            note=note,
        )

    def mark_exported(self, ticket_id: str, *, actor_id: str = "owner", note: str | None = None) -> dict:
        return self._transition_ticket(
            ticket_id,
            "broker_ticket_exported",
            actor_id=actor_id,
            action="owner_marked_broker_ready_ticket_exported",
            note=note,
        )

    def _transition_ticket(
        self,
        ticket_id: str,
        new_status: str,
        *,
        actor_id: str,
        action: str,
        note: str | None,
    ) -> dict:
        for index, ticket in enumerate(self._tickets):
            if ticket.get("ticket_id") != ticket_id:
                continue
            current_status = str(ticket.get("status", "unknown"))
            if current_status == new_status:
                return {
                    "status": "unchanged",
                    "reason": "ticket_already_in_requested_state",
                    "ticket": annotate_ticket_freshness(ticket),
                }
            blocked_reason = _transition_blocker(current_status, new_status)
            if blocked_reason:
                return {
                    "status": "blocked",
                    "reason": blocked_reason,
                    "ticket": annotate_ticket_freshness(ticket),
                }
            updated = dict(ticket)
            updated["status"] = new_status
            updated["updated_at"] = utc_now_iso()
            event = {
                "action": action,
                "actor_id": actor_id,
                "from_status": current_status,
                "to_status": new_status,
                "at": updated["updated_at"],
            }
            if note:
                event["note"] = note
            updated.setdefault("status_history", [])
            updated["status_history"] = [*updated["status_history"], event]
            if new_status in {"owner_reviewed", "owner_rejected"}:
                updated["owner_review"] = {
                    "status": new_status,
                    "actor_id": actor_id,
                    "reviewed_at": updated["updated_at"],
                    "note": note or "",
                }
            if new_status == "broker_ticket_exported":
                updated["broker_ticket_export"] = {
                    "actor_id": actor_id,
                    "exported_at": updated["updated_at"],
                    "note": note or "",
                    "live_order_submission_enabled": False,
                }
            self._tickets[index] = updated
            self._persist()
            return {
                "status": "updated",
                "previous_status": current_status,
                "new_status": new_status,
                "ticket": annotate_ticket_freshness(updated),
            }
        return {"status": "not_found", "ticket_id": ticket_id}

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
    elif annotated.get("status") in {"owner_reviewed", "owner_rejected", "broker_ticket_exported"}:
        annotated["actionability"] = annotated["status"]
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


def _transition_blocker(current_status: str, new_status: str) -> str | None:
    if current_status == "blocked_by_risk" and new_status in {"owner_reviewed", "broker_ticket_exported"}:
        return "risk_blocked_ticket_cannot_be_owner_reviewed_or_exported"
    if current_status == "owner_rejected" and new_status in {"owner_reviewed", "broker_ticket_exported"}:
        return "rejected_ticket_cannot_be_reopened_or_exported"
    if current_status == "broker_ticket_exported" and new_status != "owner_rejected":
        return "exported_ticket_cannot_transition_except_rejection"
    if new_status == "broker_ticket_exported" and current_status != "owner_reviewed":
        return "ticket_must_be_owner_reviewed_before_export"
    return None
