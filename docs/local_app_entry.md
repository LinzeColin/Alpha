# Alpha Local App Entry

The local dashboard entrypoint is:

```text
outputs/applications/Alpha.command
```

Compatibility entrypoint matching the requested external folder spelling:

```text
outputs/applicatioins/Alpha.command
```

Recommended repo launcher:

```text
outputs/applications/Alpha.command
```

The command starts the FastAPI dashboard at:

```text
http://127.0.0.1:8000/dashboard
```

It creates `.venv` when missing, starts `uvicorn`, starts the 300-second paper
trading agent loop inside the FastAPI app lifecycle, writes dashboard logs to
`runtime/alpha_dashboard.log`, and opens the dashboard URL on macOS.

The dashboard exposes automatic loop status at:

```text
http://127.0.0.1:8000/agent/loop/status
```

Observed external legacy copy:

```text
/Users/linzezhang/Downloads/applicatioins/Alpha.command exists and is executable.
```
