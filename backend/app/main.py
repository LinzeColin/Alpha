from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import yaml

from backend.app.api.routes import router
from backend.app.services.agent_runtime import AUTO_PAPER_AGENT
from backend.app.services.ops_runtime import AUTO_OPS_MAINTENANCE
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, build_default_loop


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOOP_CONFIG = ROOT / "configs" / "agent_loop.yaml"


def _load_agent_loop_settings() -> dict:
    if not AGENT_LOOP_CONFIG.exists():
        return {"enabled": True, "interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS}
    data = yaml.safe_load(AGENT_LOOP_CONFIG.read_text(encoding="utf-8")) or {}
    paper_loop = data.get("paper_trading_loop", {})
    return {
        "enabled": bool(paper_loop.get("enabled", True)),
        "interval_seconds": int(paper_loop.get("refresh_interval_seconds", DEFAULT_REFRESH_INTERVAL_SECONDS)),
    }


def _load_ops_maintenance_settings() -> dict:
    defaults = {
        "enabled": True,
        "interval_seconds": 300,
        "backup_interval_seconds": 86_400,
        "max_backup_count": 30,
        "max_history_rows": 10_000,
        "history_path": "runtime/ops_health_history.jsonl",
        "backup_dir": "runtime/backups",
    }
    if not AGENT_LOOP_CONFIG.exists():
        return defaults
    data = yaml.safe_load(AGENT_LOOP_CONFIG.read_text(encoding="utf-8")) or {}
    ops = data.get("ops_maintenance", {})
    return {
        "enabled": bool(ops.get("enabled", defaults["enabled"])),
        "interval_seconds": int(ops.get("interval_seconds", defaults["interval_seconds"])),
        "backup_interval_seconds": int(ops.get("backup_interval_seconds", defaults["backup_interval_seconds"])),
        "max_backup_count": int(ops.get("max_backup_count", defaults["max_backup_count"])),
        "max_history_rows": int(ops.get("max_history_rows", defaults["max_history_rows"])),
        "history_path": str(ops.get("history_path", defaults["history_path"])),
        "backup_dir": str(ops.get("backup_dir", defaults["backup_dir"])),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = _load_agent_loop_settings()
    if settings["enabled"]:
        AUTO_PAPER_AGENT.start(
            loop_factory=lambda: build_default_loop(interval_seconds=settings["interval_seconds"]),
            interval_seconds=settings["interval_seconds"],
        )
    ops_settings = _load_ops_maintenance_settings()
    if ops_settings["enabled"]:
        AUTO_OPS_MAINTENANCE.start(
            root=ROOT,
            loop_snapshot_provider=AUTO_PAPER_AGENT.snapshot,
            interval_seconds=ops_settings["interval_seconds"],
            backup_interval_seconds=ops_settings["backup_interval_seconds"],
            max_backup_count=ops_settings["max_backup_count"],
            max_history_rows=ops_settings["max_history_rows"],
            history_path=ROOT / ops_settings["history_path"],
            backup_dir=ROOT / ops_settings["backup_dir"],
        )
    yield
    await AUTO_OPS_MAINTENANCE.stop()
    await AUTO_PAPER_AGENT.stop()


app = FastAPI(title="Personal Alpha Agent Workspace", version="0.1.0", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
