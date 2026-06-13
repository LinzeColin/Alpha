# Backup Patch: manual broker-ready ticket export

Local commit: `dae7505a5fa3c1084a04240b0438f2c03b12e4bc`

Local commit message: `Add manual broker-ready ticket export`

Reason for connector backup: local `git push origin main` failed because HTTPS credentials were unavailable (`could not read Username for 'https://github.com': Device not configured`).

Contents:

- Adds `backend/app/services/broker_ticket_export.py` for manual-only broker-ready JSON/CSV ticket packages.
- Adds `GET /orders/approval-queue/{ticket_id}/broker-ticket` and `.csv` endpoints.
- Adds Dashboard actions: 查看工单 and 下载工单表格.
- Tightens approval queue state transitions so expired tickets cannot be owner-reviewed or exported.
- Preserves safety boundary: `live_order_submission_enabled: false`, no real broker `place_order` path.
- Updates README, decision log, requirements alignment, and handoff.

Validation performed locally:

```text
.venv/bin/python -m pytest tests/test_broker_ticket_export.py tests/test_approval_queue.py tests/test_dashboard_state.py -q -> 19 passed
.venv/bin/python -m pytest tests -q -> 42 passed
git diff --check -> passed
Runtime API: generated ticket_a03c19291ad8, owner_reviewed, broker-ticket manual_entry_allowed=true, live_order_submission_enabled=false, CSV header present, marked broker_ticket_exported
```

Apply locally:

```bash
base64 -d outputs/patches/dae7505a5fa3c1084a04240b0438f2c03b12e4bc-add-manual-broker-ready-ticket-export.patch.gz.b64 | gunzip | git am
```
