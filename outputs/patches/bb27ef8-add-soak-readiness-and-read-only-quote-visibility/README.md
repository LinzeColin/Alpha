# Backup: soak readiness and read-only quote visibility

Primary implementation commit: `bb27ef8bfcd6035dc8b4ee8fb75ce55501652f12`
Latest verification commit: `3b3d0c971b98d4646f5e2ce566e6110402e9a942`
Backup branch: `codex/soak-readiness-quote`
Created by: Codex local run on 2026-06-13

## Why this backup exists

A normal `git push origin main` could not fast-forward because the GitHub `main` branch contains connector-created backup commits not present in the local branch:

```text
! [rejected] main -> main (fetch first)
error: failed to push some refs to 'github.com:LinzeColin/Alpha.git'
```

A non-conflicting backup branch was pushed successfully and then fast-forwarded to include runtime verification evidence:

```text
PATH="$PWD/.venv/bin:$PATH" git push origin HEAD:refs/heads/codex/soak-readiness-quote
[ECC pre-push] Verification checks passed.
61 passed, 1 warning
[new branch] HEAD -> codex/soak-readiness-quote

PATH="$PWD/.venv/bin:$PATH" git push origin HEAD:refs/heads/codex/soak-readiness-quote
[ECC pre-push] Verification checks passed.
61 passed, 1 warning
bb27ef8..3b3d0c9 HEAD -> codex/soak-readiness-quote
```

## Scope

The backup branch includes:

- `/readiness/soak`, `scripts/check_alpha_soak.sh`, and `backend.app.services.soak_readiness` for a Chinese 30-day local soak start-gate report.
- Dashboard “长运行预检” and `/dashboard/state.soak_readiness`.
- Moomoo OpenD read-only quote snapshot support at `/broker/moomoo/quote-snapshot` and dashboard “只读行情快照”.
- Optional `broker` dependency extra with `moomoo-api`.
- Moomoo SDK HOME guard using `runtime/moomoo_api_home` and a lock around temporary HOME switching.
- Tests proving soak readiness fail-closed behavior and Moomoo quote snapshot read-only boundaries.
- HANDOFF runtime verification evidence in `3b3d0c9`.

## Validation

```text
.venv/bin/python -m pytest tests/test_soak_readiness.py tests/test_dashboard_state.py -q -> 12 passed
.venv/bin/python -m pytest tests/test_soak_readiness.py tests/test_paper_readiness.py tests/test_ops_health.py tests/test_ops_runtime.py tests/test_dashboard_state.py -q -> 18 passed
.venv/bin/python -m pytest tests -q -> 61 passed
.venv/bin/python -m pytest tests/test_soak_readiness.py tests/test_moomoo_broker_probe.py tests/test_dashboard_state.py -q -> 19 passed
.venv/bin/python -m pytest tests/test_moomoo_broker_probe.py tests/test_dashboard_state.py -q -> 16 passed
git diff --check -> passed
scripts/check_alpha_soak.sh with no running API -> fail-closed, 不可开始长运行, pass/warn/fail=4/0/4
scripts/check_alpha_soak.sh with running API -> 可观察运行, pass/warn/fail=7/1/0
/readiness/soak runtime -> 可观察运行, pass/warn/fail=7/1/0
/broker/moomoo/quote-snapshot runtime -> status_zh=已获取, row_count=3, codes=US.SPY/US.QQQ/US.TLT, trade_context_enabled=false, live_order_submission_enabled=false
ECC pre-push on backup branch -> 61 passed, 1 warning
Safety scan -> no real broker place_order/unlock_trade/trade_context_enabled=true/live_order_submission_enabled=true path
```

## Recovery

Use the backup branch directly:

```bash
git fetch origin codex/soak-readiness-quote
git checkout codex/soak-readiness-quote
```

Or cherry-pick the commits from that branch after resolving the current `main` history divergence.

## Safety Boundary

This backup does not add broker credentials, trade unlock, trade context, real broker order submission, or unattended live trading. Moomoo access is quote-context-only.
