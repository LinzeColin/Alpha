from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.services.display_locale import zh_status
from backend.app.services.market_data_gateway import MarketDataGateway
from backend.app.services.ops_health import (
    DEFAULT_MAX_BACKUP_COUNT,
    DEFAULT_MAX_HISTORY_ROWS,
    append_ops_health_history,
    collect_ops_health,
    create_runtime_backup,
    prune_runtime_backups,
)
from backend.app.services.runtime_status import atomic_write_runtime_snapshot


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class AutoOpsMaintenanceRuntime:
    """Runs scheduled health sampling, runtime backups, and backup rotation."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._enabled = False
        self._status = "stopped"
        self._root = Path(__file__).resolve().parents[3]
        self._loop_snapshot_provider: Callable[[], dict] | None = None
        self._interval_seconds = 300
        self._backup_interval_seconds = 86_400
        self._max_backup_count = DEFAULT_MAX_BACKUP_COUNT
        self._max_history_rows = DEFAULT_MAX_HISTORY_ROWS
        self._history_path = self._root / "runtime" / "ops_health_history.jsonl"
        self._backup_dir = self._root / "runtime" / "backups"
        self._status_path = self._root / "runtime" / "ops_maintenance_status.json"
        self._started_at: datetime | None = None
        self._last_run_started_at: datetime | None = None
        self._last_run_completed_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._run_count = 0
        self._backup_count = 0
        self._error_count = 0
        self._last_error: str | None = None
        self._last_persist_error: str | None = None
        self._last_result_summary: dict | None = None

    def start(
        self,
        *,
        root: str | Path,
        loop_snapshot_provider: Callable[[], dict],
        interval_seconds: int = 300,
        backup_interval_seconds: int = 86_400,
        max_backup_count: int = DEFAULT_MAX_BACKUP_COUNT,
        max_history_rows: int = DEFAULT_MAX_HISTORY_ROWS,
        history_path: str | Path | None = None,
        backup_dir: str | Path | None = None,
        status_path: str | Path | None = None,
    ) -> dict:
        if self._task and not self._task.done():
            return self.snapshot()
        self._root = Path(root)
        self._loop_snapshot_provider = loop_snapshot_provider
        self._interval_seconds = max(1, int(interval_seconds))
        self._backup_interval_seconds = max(1, int(backup_interval_seconds))
        self._max_backup_count = max(1, int(max_backup_count))
        self._max_history_rows = max(1, int(max_history_rows))
        self._history_path = Path(history_path) if history_path else self._root / "runtime" / "ops_health_history.jsonl"
        self._backup_dir = Path(backup_dir) if backup_dir else self._root / "runtime" / "backups"
        self._status_path = Path(status_path) if status_path else self._root / "runtime" / "ops_maintenance_status.json"
        self._enabled = True
        self._status = "starting"
        self._started_at = _utc_now()
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())
        self._persist_snapshot()
        return self.snapshot()

    async def stop(self) -> dict:
        self._enabled = False
        if not self._task:
            self._status = "stopped"
            return self.snapshot()
        if self._stop_event:
            self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5)
        except asyncio.TimeoutError:
            self._task.cancel()
            self._status = "stopped"
        self._persist_snapshot()
        return self.snapshot()

    async def _run(self) -> None:
        if not self._stop_event:
            self._status = "stopped"
            self._persist_snapshot()
            return
        while not self._stop_event.is_set():
            self._status = "running_maintenance"
            self._last_run_started_at = _utc_now()
            self._persist_snapshot()
            try:
                result = await asyncio.to_thread(self.run_cycle_once)
                self._last_run_completed_at = _utc_now()
                self._run_count += 1
                if result.get("backup_created"):
                    self._backup_count += 1
                self._last_error = None
                self._last_result_summary = self._summarize_result(result)
                self._status = "maintenance_sleeping"
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                self._last_run_completed_at = _utc_now()
                self._error_count += 1
                self._last_error = str(exc)
                self._status = "maintenance_error_sleeping"
            self._next_run_at = _utc_now() + timedelta(seconds=self._interval_seconds)
            self._persist_snapshot()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                continue
        self._status = "stopped"
        self._next_run_at = None
        self._persist_snapshot()

    def run_cycle_once(self) -> dict:
        loop_snapshot = self._loop_snapshot_provider() if self._loop_snapshot_provider else None
        gateway = MarketDataGateway(root=self._root)
        health = collect_ops_health(
            root=self._root,
            market_data_gateway=gateway,
            loop_snapshot=loop_snapshot,
            max_backup_age_seconds=self._backup_interval_seconds,
        )
        backup = None
        if self._backup_due(health):
            backup = create_runtime_backup(
                root=self._root,
                market_data_cache_path=gateway.cache_path,
                output_dir=self._backup_dir,
            )
        rotation = prune_runtime_backups(backup_root=self._backup_dir, max_backup_count=self._max_backup_count)
        maintenance_summary = {
            "status": "completed",
            "backup_created": bool(backup),
            "backup_path": backup.get("backup_path") if backup else None,
            "rotation_status": rotation.get("status"),
            "deleted_backup_count": rotation.get("deleted_count", 0),
        }
        history = append_ops_health_history(
            health,
            history_path=self._history_path,
            maintenance=maintenance_summary,
            max_rows=self._max_history_rows,
        )
        return {
            "status": "completed",
            "generated_at": _iso(_utc_now()),
            "health": health,
            "backup_created": bool(backup),
            "backup": backup,
            "rotation": rotation,
            "history": history,
            "backup_interval_seconds": self._backup_interval_seconds,
            "max_backup_count": self._max_backup_count,
        }

    def _backup_due(self, health: dict) -> bool:
        latest = health.get("latest_backup") or {}
        created_at = _parse_iso(latest.get("created_at"))
        if not created_at:
            return True
        age_seconds = int((_utc_now() - created_at).total_seconds())
        return age_seconds >= self._backup_interval_seconds

    def _summarize_result(self, result: dict) -> dict:
        health = result.get("health") or {}
        rotation = result.get("rotation") or {}
        history = result.get("history") or {}
        backup = result.get("backup") or {}
        return {
            "status": result.get("status"),
            "status_zh": zh_status(result.get("status")),
            "health_status": health.get("overall_status"),
            "health_status_zh": health.get("overall_status_zh"),
            "pass_count": health.get("pass_count"),
            "warn_count": health.get("warn_count"),
            "fail_count": health.get("fail_count"),
            "backup_created": result.get("backup_created"),
            "backup_path": backup.get("backup_path"),
            "rotation_status": rotation.get("status"),
            "rotation_status_zh": zh_status(rotation.get("status")),
            "deleted_backup_count": rotation.get("deleted_count", 0),
            "history_path": history.get("path"),
            "history_row_count": history.get("row_count"),
        }

    def _build_snapshot(self) -> dict:
        task_running = bool(self._task and not self._task.done())
        return {
            "enabled": self._enabled,
            "enabled_zh": "是" if self._enabled else "否",
            "status": self._status,
            "status_zh": zh_status(self._status),
            "task_running": task_running,
            "task_running_zh": "是" if task_running else "否",
            "interval_seconds": self._interval_seconds,
            "backup_interval_seconds": self._backup_interval_seconds,
            "max_backup_count": self._max_backup_count,
            "max_history_rows": self._max_history_rows,
            "history_path": str(self._history_path),
            "backup_dir": str(self._backup_dir),
            "started_at": _iso(self._started_at),
            "last_run_started_at": _iso(self._last_run_started_at),
            "last_run_completed_at": _iso(self._last_run_completed_at),
            "next_run_at": _iso(self._next_run_at),
            "run_count": self._run_count,
            "backup_count": self._backup_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_persist_error": self._last_persist_error,
            "last_persist_error_zh": "无" if not self._last_persist_error else "运行心跳写入失败。",
            "last_result_summary": self._last_result_summary,
            "status_path": str(self._status_path),
        }

    def _persist_snapshot(self) -> None:
        try:
            self._last_persist_error = None
            atomic_write_runtime_snapshot(self._status_path, self._build_snapshot(), snapshot_kind="ops_maintenance")
        except Exception as exc:
            self._last_persist_error = f"{exc.__class__.__name__}: {exc}"

    def snapshot(self) -> dict:
        return self._build_snapshot()


AUTO_OPS_MAINTENANCE = AutoOpsMaintenanceRuntime()
