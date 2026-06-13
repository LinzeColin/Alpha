from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from backend.app.services.display_locale import zh_reason, zh_status, zh_storage_backend

SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
SQLITE_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ApprovalQueue:
    """Small file-backed queue for owner-reviewed broker-ready tickets."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.storage_backend = _storage_backend_for_path(self.path)
        self._tickets: list[dict] = []
        if self.storage_backend == "sqlite" and self.path:
            self._init_sqlite()
            self._migrate_json_sibling_if_needed()
        elif self.path and self.path.exists():
            self._tickets = json.loads(self.path.read_text(encoding="utf-8"))

    def enqueue(self, ticket: dict) -> dict:
        if self.get_ticket(str(ticket.get("ticket_id", ""))):
            return {"status": "duplicate", "status_zh": zh_status("duplicate"), "ticket": ticket}
        if self.storage_backend == "sqlite":
            self._save_sqlite_ticket(ticket, insert=True)
            return {"status": "queued", "status_zh": zh_status("queued"), "ticket": ticket}
        self._tickets.append(ticket)
        self._persist()
        return {"status": "queued", "status_zh": zh_status("queued"), "ticket": ticket}

    def list_tickets(self) -> list[dict]:
        if self.storage_backend == "sqlite":
            return self._fetch_sqlite_tickets()
        return list(self._tickets)

    def get_ticket(self, ticket_id: str) -> dict | None:
        if self.storage_backend == "sqlite":
            return self._fetch_sqlite_ticket(ticket_id)
        for ticket in self._tickets:
            if ticket.get("ticket_id") == ticket_id:
                return dict(ticket)
        return None

    def latest(self, limit: int = 20) -> list[dict]:
        if self.storage_backend == "sqlite":
            return self._fetch_sqlite_tickets(limit=limit)
        return self._tickets[-limit:]

    def latest_with_freshness(self, limit: int = 20, *, now: datetime | None = None) -> list[dict]:
        return [annotate_ticket_freshness(ticket, now=now) for ticket in self.latest(limit)]

    def summary(self, *, now: datetime | None = None) -> dict:
        annotated = [annotate_ticket_freshness(ticket, now=now) for ticket in self.list_tickets()]
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
            "storage": self.storage_status(),
            "message_zh": _summary_message_zh(len(fresh_pending), len(expired_pending), len(exported)),
        }

    def storage_status(self) -> dict:
        exists = bool(self.path and self.path.exists())
        return {
            "backend": self.storage_backend,
            "backend_zh": zh_storage_backend(self.storage_backend),
            "durable": self.storage_backend in {"json", "sqlite"},
            "durable_zh": "是" if self.storage_backend in {"json", "sqlite"} else "否",
            "path": str(self.path) if self.path else None,
            "exists": exists,
            "exists_zh": "是" if exists else "否",
            "schema_version": SQLITE_SCHEMA_VERSION if self.storage_backend == "sqlite" else None,
            "file_size_bytes": self.path.stat().st_size if exists and self.path else None,
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
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return {
                "status": "not_found",
                "status_zh": zh_status("not_found"),
                "reason": "ticket_not_found",
                "reason_zh": zh_reason("ticket_not_found"),
                "ticket_id": ticket_id,
            }
        current_status = str(ticket.get("status", "unknown"))
        if current_status == new_status:
            return {
                "status": "unchanged",
                "status_zh": zh_status("unchanged"),
                "reason": "ticket_already_in_requested_state",
                "reason_zh": zh_reason("ticket_already_in_requested_state"),
                "ticket": annotate_ticket_freshness(ticket),
            }
        blocked_reason = _transition_blocker(current_status, new_status)
        annotated_ticket = annotate_ticket_freshness(ticket)
        if blocked_reason:
            return {
                "status": "blocked",
                "status_zh": zh_status("blocked"),
                "reason": blocked_reason,
                "reason_zh": zh_reason(blocked_reason),
                "ticket": annotated_ticket,
            }
        freshness_status = (annotated_ticket.get("freshness") or {}).get("status")
        if new_status in {"owner_reviewed", "broker_ticket_exported"} and freshness_status != "fresh":
            return {
                "status": "blocked",
                "status_zh": zh_status("blocked"),
                "reason": "expired_ticket_cannot_be_owner_reviewed_or_exported",
                "reason_zh": zh_reason("expired_ticket_cannot_be_owner_reviewed_or_exported"),
                "ticket": annotated_ticket,
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
        self._save_ticket(updated)
        return {
            "status": "updated",
            "status_zh": zh_status("updated"),
            "previous_status": current_status,
            "previous_status_zh": zh_status(current_status),
            "new_status": new_status,
            "new_status_zh": zh_status(new_status),
            "ticket": annotate_ticket_freshness(updated),
        }

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._tickets, indent=2, sort_keys=True), encoding="utf-8")

    def _save_ticket(self, ticket: dict) -> None:
        if self.storage_backend == "sqlite":
            self._save_sqlite_ticket(ticket, insert=False)
            return
        for index, item in enumerate(self._tickets):
            if item.get("ticket_id") == ticket.get("ticket_id"):
                self._tickets[index] = ticket
                self._persist()
                return
        self._tickets.append(ticket)
        self._persist()

    def _connect(self) -> sqlite3.Connection:
        if not self.path:
            raise RuntimeError("sqlite approval queue requires a path")
        return sqlite3.connect(self.path)

    def _init_sqlite(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    updated_at TEXT,
                    status TEXT,
                    ticket_json TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_approval_tickets_created_at ON approval_tickets(created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_approval_tickets_status ON approval_tickets(status)")
            connection.execute(f"PRAGMA user_version={SQLITE_SCHEMA_VERSION}")

    def _save_sqlite_ticket(self, ticket: dict, *, insert: bool) -> None:
        ticket_id = str(ticket.get("ticket_id", ""))
        if not ticket_id:
            raise ValueError("approval ticket requires ticket_id")
        created_at = str(ticket.get("created_at") or utc_now_iso())
        updated_at = str(ticket.get("updated_at") or created_at)
        status = str(ticket.get("status", "unknown"))
        payload = json.dumps(ticket, sort_keys=True)
        with self._connect() as connection:
            if insert:
                connection.execute(
                    """
                    INSERT INTO approval_tickets (ticket_id, created_at, updated_at, status, ticket_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (ticket_id, created_at, updated_at, status, payload),
                )
            else:
                connection.execute(
                    """
                    UPDATE approval_tickets
                    SET created_at = ?, updated_at = ?, status = ?, ticket_json = ?
                    WHERE ticket_id = ?
                    """,
                    (created_at, updated_at, status, payload, ticket_id),
                )

    def _fetch_sqlite_ticket(self, ticket_id: str) -> dict | None:
        if not ticket_id:
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT ticket_json FROM approval_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _fetch_sqlite_tickets(self, limit: int | None = None) -> list[dict]:
        with self._connect() as connection:
            if limit is None:
                rows = connection.execute("SELECT ticket_json FROM approval_tickets ORDER BY rowid ASC").fetchall()
                return [json.loads(row[0]) for row in rows]
            rows = connection.execute(
                "SELECT ticket_json FROM approval_tickets ORDER BY rowid DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def _migrate_json_sibling_if_needed(self) -> None:
        if not self.path:
            return
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM approval_tickets").fetchone()
        if row and row[0]:
            return
        sibling = self.path.with_suffix(".json")
        if not sibling.exists():
            return
        try:
            tickets = json.loads(sibling.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(tickets, list):
            return
        for ticket in tickets:
            if isinstance(ticket, dict) and ticket.get("ticket_id"):
                self.enqueue(ticket)


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
    annotated["status_zh"] = zh_status(annotated.get("status"))
    annotated["actionability_zh"] = zh_status(annotated.get("actionability"))
    return annotated


def _freshness(expires_at: str | None, *, now: datetime) -> dict:
    if not expires_at:
        return {"status": "unknown", "status_zh": zh_status("unknown"), "expires_at": None, "seconds_until_expiry": None}
    expires = _parse_iso_datetime(expires_at)
    if not expires:
        return {"status": "invalid", "status_zh": zh_status("invalid"), "expires_at": expires_at, "seconds_until_expiry": None}
    seconds_until_expiry = int((expires - now).total_seconds())
    status = "fresh" if seconds_until_expiry > 0 else "expired"
    return {
        "status": status,
        "status_zh": zh_status(status),
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


def _summary_message_zh(fresh_pending_count: int, expired_pending_count: int, exported_count: int) -> str:
    if fresh_pending_count:
        return f"当前有 {fresh_pending_count} 张有效候选单需要人工复核。"
    if expired_pending_count:
        return f"当前没有有效候选单，已有 {expired_pending_count} 张过期候选单保留用于审计。"
    if exported_count:
        return f"当前没有待处理候选单，已有 {exported_count} 张工单完成导出记录。"
    return "当前没有待处理候选单。"


def _storage_backend_for_path(path: Path | None) -> str:
    if path is None:
        return "memory"
    if path.suffix.lower() in SQLITE_SUFFIXES:
        return "sqlite"
    return "json"
