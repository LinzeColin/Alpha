# 71e9bf8 Backup: Add Chinese broker ticket view

Local commit: `71e9bf84bf1babf9ba903f6bb561364cd1c3094c`

Reason for connector backup: local `git push origin main` failed because HTTPS credentials were unavailable on this machine: `fatal: could not read Username for 'https://github.com': Device not configured`.

This directory stores a recoverable base64-encoded unified diff for the local commit.

## Files

- `changes.patch.b64`

Restore command:

```bash
base64 -D -i outputs/patches/71e9bf8-add-chinese-broker-ticket-view/changes.patch.b64 -o /tmp/71e9bf8.patch
git apply /tmp/71e9bf8.patch
```

## Scope

- Adds a Chinese owner-facing HTML broker-ticket view at `/orders/approval-queue/{ticket_id}/broker-ticket/view`.
- Changes the dashboard `查看工单` action to open the Chinese HTML view instead of raw JSON.
- Keeps JSON and CSV broker-ticket endpoints unchanged for automation and manual broker import.
- Replaces owner-facing `bps` text with `基点` in dashboard, CLI summary, execution-cost receipt, and docs.
- Adds regression tests for Chinese broker-ticket HTML and display-unit leakage.

## Validation Evidence

- Target tests: `.venv/bin/python -m pytest tests/test_broker_ticket_export.py tests/test_dashboard_state.py tests/test_broker_paper_adapter.py tests/test_paper_trading_loop.py tests/test_agent_runtime.py -q` -> `18 passed`
- Full regression: `.venv/bin/python -m pytest tests -q` -> `47 passed`
- `git diff --check` -> passed
- Safety scan -> no new real broker `place_order` path; live-order submission remains disabled
- Runtime broker-ticket view -> generated `ticket_fcd7cb8153f4`, owner reviewed it, `/broker-ticket/view` returned Chinese title and submission-mode copy, and did not expose `manual_owner_broker_confirmation_only`
- Runtime dashboard page -> `lang=zh-CN`, contains `/broker-ticket/view`, and owner-facing English slippage unit was absent
- Browser DOM check -> dashboard had a `查看工单` button for `ticket_fcd7cb8153f4` with onclick target `openBrokerTicket('ticket_fcd7cb8153f4')`; Browser connection interrupted during the click, so runtime HTTP verification was used for the final page check.

## Safety Boundary

This commit only changes user-facing display and broker-ticket viewing. It does not implement unattended real-money broker order submission and does not change the committed live trading boundary.
