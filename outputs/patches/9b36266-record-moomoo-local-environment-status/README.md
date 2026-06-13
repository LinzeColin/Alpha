# Backup: 9b36266 Record Moomoo local environment status

Local commit: `9b36266509351313b128ceef92b056fe86231057`
Base commit: `d5a730f55369b0219e5033e58fb14fc3df6e2450`
Created by: Codex local run on 2026-06-13

## Why this backup exists

A normal `git push origin main` failed from the local machine with:

```text
fatal: could not read Username for 'https://github.com': Device not configured
```

This connector-backed folder stores a recovery patch for the local HANDOFF update.

## Scope

This commit records the latest local Moomoo/OpenD environment evidence:

- `lsof` shows `moomoo_Op` listening on `127.0.0.1:11111`.
- Unsandboxed read-only `nc -zv 127.0.0.1 11111` succeeded.
- Codex sandboxed socket checks can return `Operation not permitted` and should not be treated as OpenD failure by itself.
- System Python and project `.venv` both cannot find `moomoo`, `futu-api`, or `futu` packages.
- Alpha's own Moomoo probe returns `api_missing`, with OpenD connected but API package unavailable.

## Restore

Apply after `d5a730f55369b0219e5033e58fb14fc3df6e2450`:

```bash
git am outputs/patches/9b36266-record-moomoo-local-environment-status/0001-record-moomoo-local-environment-status.patch
```

## Safety boundary

This patch is documentation-only. It does not read broker credentials, unlock trading, or submit real-money orders.
