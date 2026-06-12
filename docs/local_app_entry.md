# Alpha Local App Entry

The local dashboard entrypoint is:

```text
outputs/applications/Alpha.command
```

Recommended repo launcher:

```text
outputs/applications/Alpha.command
```

The command starts the FastAPI dashboard at:

```text
http://127.0.0.1:8000/dashboard
```

It creates `.venv` when missing, starts `uvicorn`, writes logs to `runtime/alpha_dashboard.log`, and opens the dashboard URL on macOS.

Observed external legacy copy:

```text
/Users/linzezhang/Downloads/applicatioins/Alpha.command exists and is executable.
```
