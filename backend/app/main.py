from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import yaml

from backend.app.api.routes import router
from backend.app.services.agent_runtime import AUTO_PAPER_AGENT
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = _load_agent_loop_settings()
    if settings["enabled"]:
        AUTO_PAPER_AGENT.start(
            loop_factory=lambda: build_default_loop(interval_seconds=settings["interval_seconds"]),
            interval_seconds=settings["interval_seconds"],
        )
    yield
    await AUTO_PAPER_AGENT.stop()


app = FastAPI(title="Personal Alpha Agent Workspace", version="0.1.0", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
