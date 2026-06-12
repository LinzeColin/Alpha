from __future__ import annotations

from fastapi import FastAPI
from backend.app.api.routes import router

app = FastAPI(title="Personal Alpha Agent Workspace", version="0.1.0")
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
