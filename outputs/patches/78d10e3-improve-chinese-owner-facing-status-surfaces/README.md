# 78d10e3 Improve Chinese owner-facing status surfaces

Local commit: `78d10e3d59315707c474c5a974a5aa3cc337ddd4`

Purpose: make owner-facing runtime/API surfaces fully understandable in Chinese while preserving raw machine fields for automation.

Validated locally:

- `.venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_approval_queue.py tests/test_moomoo_broker_probe.py tests/test_live_broker_fail_closed.py -q` -> 23 passed
- `.venv/bin/python -m pytest tests -q` -> 53 passed
- `git diff --check` -> passed
- safety scan -> no new real broker `place_order`/`unlock_trade` path; live-order submission remains disabled

Git push from local machine failed because HTTPS credentials were unavailable: `fatal: could not read Username for 'https://github.com': Device not configured`.
