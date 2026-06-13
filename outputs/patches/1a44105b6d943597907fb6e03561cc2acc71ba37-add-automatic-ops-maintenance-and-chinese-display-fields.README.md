# Backup Patch: automatic ops maintenance and Chinese display fields

Local commit: `1a44105b6d943597907fb6e03561cc2acc71ba37`

Local commit message: `Add automatic ops maintenance and Chinese display fields`

Reason for connector backup: local `git push origin main` failed because HTTPS credentials were unavailable (`could not read Username for 'https://github.com': Device not configured`).

Contents:

- App-managed `AutoOpsMaintenanceRuntime` for scheduled health sampling, stale backup creation, backup rotation, and health history JSONL.
- `/ops/maintenance/status` dashboard/API visibility.
- Chinese display fields for owner-facing runtime/status APIs.
- Fail-closed live order intent response with `status_zh`, `reason_zh`, and Chinese safety message.
- Project rule requiring user-visible Chinese display while keeping machine fields stable.
- Tests covering dashboard Chinese mappings, runtime Chinese snapshots, ops maintenance, and fail-closed live intent localization.

Apply locally:

```bash
base64 -d outputs/patches/1a44105b6d943597907fb6e03561cc2acc71ba37-add-automatic-ops-maintenance-and-chinese-display-fields.patch.gz.b64 | gunzip | git am
```

Validation performed locally:

```text
.venv/bin/python -m pytest tests/test_dashboard_state.py tests/test_agent_runtime.py tests/test_ops_runtime.py tests/test_live_broker_fail_closed.py -q -> 10 passed
.venv/bin/python -m pytest tests -q -> 38 passed
git diff --check -> passed
/health -> status_zh=正常
/agent/loop/status -> status_zh=等待下次运行
/ops/maintenance/status -> status_zh=等待下次维护
/live/order-intent -> status_zh=已拒绝, reason_zh=策略已禁用真实资金交易
```
