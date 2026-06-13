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


def test_approval_queue_tracks_owner_review_and_export_transitions(tmp_path):
    queue = ApprovalQueue(tmp_path / "approval_queue.json")
    ticket = {
        "ticket_id": "ticket_review",
        "status": "pending_owner_approval",
        "broker_payload": {"symbol": "QQQ"},
        "risk_check": {"allowed": True},
    }
    queue.enqueue(ticket)

    reviewed = queue.mark_owner_reviewed("ticket_review", actor_id="owner_dashboard", note="looks actionable")
    exported = queue.mark_exported("ticket_review", actor_id="owner_dashboard")
    reloaded = ApprovalQueue(tmp_path / "approval_queue.json")
    stored = reloaded.get_ticket("ticket_review")
    summary = reloaded.summary()

    assert reviewed["status"] == "updated"
    assert reviewed["new_status"] == "owner_reviewed"
    assert exported["status"] == "updated"
    assert exported["new_status"] == "broker_ticket_exported"
    assert stored["status"] == "broker_ticket_exported"
    assert stored["owner_review"]["status"] == "owner_reviewed"
    assert stored["broker_ticket_export"]["live_order_submission_enabled"] is False
    assert [event["to_status"] for event in stored["status_history"]] == ["owner_reviewed", "broker_ticket_exported"]
    assert summary["fresh_pending_count"] == 0
    assert summary["owner_reviewed_count"] == 0
    assert summary["broker_ticket_exported_count"] == 1


def test_approval_queue_blocks_export_before_owner_review(tmp_path):
    queue = ApprovalQueue(tmp_path / "approval_queue.json")
    queue.enqueue({"ticket_id": "ticket_pending", "status": "pending_owner_approval"})

    result = queue.mark_exported("ticket_pending")

    assert result["status"] == "blocked"
    assert result["reason"] == "ticket_must_be_owner_reviewed_before_export"
    assert queue.get_ticket("ticket_pending")["status"] == "pending_owner_approval"


def test_approval_queue_blocks_owner_review_for_risk_blocked_ticket(tmp_path):
    queue = ApprovalQueue(tmp_path / "approval_queue.json")
    queue.enqueue({"ticket_id": "ticket_blocked", "status": "blocked_by_risk"})

    result = queue.mark_owner_reviewed("ticket_blocked")
    rejected = queue.reject("ticket_blocked")

    assert result["status"] == "blocked"
    assert result["reason"] == "risk_blocked_ticket_cannot_be_owner_reviewed_or_exported"
    assert rejected["status"] == "updated"
    assert rejected["new_status"] == "owner_rejected"
