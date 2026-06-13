# Patch Backup: 2e92d1f Localize runtime display surfaces

Local push from Codex was blocked by HTTPS credential configuration:

```text
fatal: could not read Username for 'https://github.com': Device not configured
```

This remote backup stores the local commit patch as a gzip-compressed base64 file:

```text
outputs/patches/2e92d1f-localize-runtime-display-surfaces.patch.gz.b64
```

Apply after decoding with:

```bash
base64 -d outputs/patches/2e92d1f-localize-runtime-display-surfaces.patch.gz.b64 | gunzip | git am
```

Commit summary:

- Added `backend/app/services/display_locale.py` for Chinese runtime display mappings.
- Localized dashboard-visible agent, adapter, broker, strategy, order type, validity, risk reason, and unknown fallback text.
- Changed `paper_trading_loop --once` default output to a Chinese human-readable summary.
- Preserved `paper_trading_loop --once --json` for raw automation output.
- Added tests for Chinese dashboard/CLI summary display.
- Updated README, HANDOFF, and decision log.

Validation evidence from local run:

```text
.venv/bin/python -m pytest tests/test_dashboard_state.py -q -> 6 passed
.venv/bin/python -m backend.app.services.paper_trading_loop --once --queue-path /tmp/alpha_zh_queue.sqlite3 --paper-state-path /tmp/alpha_zh_portfolio.json -> Chinese summary displayed
.venv/bin/python -m backend.app.services.paper_trading_loop --once --json --queue-path /tmp/alpha_zh_json_queue.sqlite3 --paper-state-path /tmp/alpha_zh_json_portfolio.json -> raw JSON displayed
.venv/bin/python -m pytest tests -q -> 31 passed
Browser dashboard check -> title Alpha 控制台, lang zh-CN, Chinese agent/adapter/risk/order/storage text present, forbidden visible raw tokens [], browserErrors []
git diff --check -> passed
Safety scan -> live_trading defaults remain disabled; no real broker place_order was added
```
