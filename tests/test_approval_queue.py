from backend.app.services.approval_queue import ApprovalQueue


def test_approval_queue_persists_ticket(tmp_path):
    path = tmp_path / "approval_queue.json"
    ticket = {"ticket_id": "ticket_1", "status": "pending_owner_approval"}

    queue = ApprovalQueue(path)
    assert queue.enqueue(ticket)["status"] == "queued"

    reloaded = ApprovalQueue(path)
    assert reloaded.list_tickets() == [ticket]
