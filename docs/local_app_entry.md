# Alpha Local App Entry

Primary app-format entrypoints:

```text
/Users/linzezhang/Downloads/Alpha.app
/Users/linzezhang/Applications/Alpha.app
/Applications/Alpha.app
```

Repo app source and generated bundle:

```text
outputs/applications/Alpha.applescript
outputs/applications/Alpha.app
```

Compatibility command launchers:

```text
outputs/applications/Alpha.command
outputs/applicatioins/Alpha.command
```

The command starts the FastAPI dashboard at:

```text
http://127.0.0.1:8000/dashboard
```

The app is an AppleScript `.app` generated from `outputs/applications/Alpha.applescript`.
It calls `scripts/start_alpha_dashboard.sh`, creates `.venv` when missing,
starts `uvicorn`, starts the 300-second paper trading agent loop inside the
FastAPI app lifecycle, writes dashboard logs to `runtime/alpha_dashboard.log`,
and opens the dashboard URL on macOS.

The dashboard exposes automatic loop status at:

```text
http://127.0.0.1:8000/agent/loop/status
```

Verified app installation:

```text
plutil -lint passed for repo, Downloads, user Applications, and system Applications copies.
open -n /Users/linzezhang/Downloads/Alpha.app launched the dashboard and app-managed paper loop.
```
