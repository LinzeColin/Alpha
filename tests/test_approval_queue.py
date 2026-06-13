from datetime import datetime, timedelta, timezone

from backend.app.services.approval_queue import ApprovalQueue


def test_approval_queue_persists_ticket(tmp_path):
    path = tmp_path / "approval_queue.json"
    ticket = {"ticket_id": "ticket_1", "status": "pending_owner_approval"}

    queue = ApprovalQueue(path)
    assert queue.enqueue(ticket)["status"] == "queued"

    reloaded = ApprovalQueue(path)
    assert reloaded.list_tickets() == [ticket]


def test_approval_queue_summarizes_fresh_and_expired_pending_tickets(tmp_path):
    now = datetime(2026, 6, 13, 0, 0, tzinfo=timezone.utc)
    queue = ApprovalQueue(tmp_path / "approval_queue.json")
    fresh_ticket = {
        "ticket_id": "ticket_fresh",
        "status": "pending_owner_approval",
        "intent": {"expires_at": (now + timedelta(seconds=300)).isoformat()},
    }
    expired_ticket = {
        "ticket_id": "ticket_expired",
        "status": "pending_owner_approval",
        "intent": {"expires_at": (now - timedelta(seconds=1)).isoformat()},
    }

    queue.extend([fresh_ticket, expired_ticket])

    summary = queue.summary(now=now)
    latest = queue.latest_with_freshness(now=now)

    assert summary["total_count"] == 2
    assert summary["fresh_pending_count"] == 1
    assert summary["expired_pending_count"] == 1
    assert latest[0]["actionability"] == "fresh_pending_owner_approval"
    assert latest[0]["freshness"]["seconds_until_expiry"] == 300
    assert latest[1]["actionability"] == "expired_owner_approval"
    assert latest[1]["freshness"]["status"] == "expired"
