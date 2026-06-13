# 97f82d2 Backup: Add paper performance history tracking

Local commit: `97f82d2ddf19690007e891534506abf99426f481`

Reason for connector backup: local `git push origin main` failed because HTTPS credentials were unavailable on this machine: `fatal: could not read Username for 'https://github.com': Device not configured`.

This directory stores the recoverable unified-diff backup for the local commit, split by file to avoid connector/context truncation.

## Files

- `01-HANDOFF.patch`
- `02-README.patch`
- `03-routes.patch`
- `04-display-locale.patch`
- `05-paper-performance.patch`
- `06-paper-trading-loop.patch`
- `07-decision-log.patch`
- `08-requirements-alignment.patch`
- `09-test-dashboard-state.patch`
- `10-test-paper-performance.patch`
- `11-test-paper-trading-loop.patch`

## Validation Evidence

- `.venv/bin/python -m pytest tests/test_paper_performance.py tests/test_paper_trading_loop.py tests/test_dashboard_state.py -q` -> `13 passed`
- `.venv/bin/python -m pytest tests -q` -> `46 passed`
- `git diff --check` -> passed
- Safety scan -> no new real broker `place_order` path; live-order submission remains disabled
- Runtime API -> `POST /paper/run-once` returned `paper_performance.status_zh=已写入`, `total_return_zh=0.00%`, `live_order_submission_enabled=false`
- Runtime API -> `GET /paper/performance/history` returned `run_count=2`, `total_return_zh=0.00%`, `max_drawdown_zh=0.00%`
- Browser dashboard -> `lang=zh-CN`, visible Chinese labels included `模拟绩效`, `模拟收益率`, `累计收益率`, `最大回撤`, `权益高水位`; console errors `0`

## Safety Boundary

This commit records simulated portfolio performance history only. It does not implement unattended real-money broker order submission and does not change the committed live trading boundary.
