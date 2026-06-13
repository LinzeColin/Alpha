# Backup: bb27ef8 Add soak readiness and read-only quote visibility

Local commit: `bb27ef8bfcd6035dc8b4ee8fb75ce55501652f12`
Base commit: `a50aa769306c34d06e598ccdaad090bfa04080c6`
Created by: Codex local run on 2026-06-13

## Why this backup exists

A normal `git push origin main` could not fast-forward because the GitHub `main` branch contains connector-created backup commits not present in the local branch:

```text
! [rejected] main -> main (fetch first)
error: failed to push some refs to 'github.com:LinzeColin/Alpha.git'
```

The pre-push verification itself passed when the hook used the project virtualenv:

```text
PATH="$PWD/.venv/bin:$PATH" git push origin main
[ECC pre-push] Verification checks passed.
61 passed, 1 warning
```

This folder stores connector-backed recovery shards for the local commit.

## Scope

This commit adds:

- `/readiness/soak`, `scripts/check_alpha_soak.sh`, and `backend.app.services.soak_readiness` for a Chinese 30-day local soak start-gate report.
- Dashboard “长运行预检” and `/dashboard/state.soak_readiness`.
- Moomoo OpenD read-only quote snapshot support at `/broker/moomoo/quote-snapshot` and dashboard “只读行情快照”.
- Optional `broker` dependency extra with `moomoo-api`.
- Moomoo SDK HOME guard using `runtime/moomoo_api_home` and a lock around temporary HOME switching.
- Tests proving soak readiness fail-closed behavior and Moomoo quote snapshot read-only boundaries.

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
Safety scan -> no real broker place_order/unlock_trade/trade_context_enabled=true/live_order_submission_enabled=true path
```

## Patch Shards

Apply by concatenating files in lexical order:

```bash
cat changes.patch.part-aa changes.patch.part-ab changes.patch.part-ac changes.patch.part-ad > changes.patch
git am changes.patch
```

## Safety Boundary

This commit does not add broker credentials, trade unlock, trade context, real broker order submission, or unattended live trading. Moomoo access is quote-context-only.
