# d5a730f Document Chinese display coverage

Local commit: `d5a730f55369b0219e5033e58fb14fc3df6e2450`

Purpose: document the full Chinese display acceptance scope in README, requirements alignment, decision log, and HANDOFF.

Validated locally before commit:

- `.venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_approval_queue.py tests/test_moomoo_broker_probe.py tests/test_live_broker_fail_closed.py -q` -> 23 passed
- `.venv/bin/python -m pytest tests -q` -> 53 passed
- `git diff --check` -> passed
- safety scan -> no new real broker `place_order`/`unlock_trade` path; live-order submission remains disabled

Git push from local machine failed because HTTPS credentials were unavailable: `fatal: could not read Username for 'https://github.com': Device not configured`.
