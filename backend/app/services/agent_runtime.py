from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.services.display_locale import zh_status


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class AutoPaperAgentRuntime:
    """Owns the app-level automatic paper trading loop."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._loop_factory: Callable[[], Any] | None = None
        self._interval_seconds = 300
        self._enabled = False
        self._status = "stopped"
        self._started_at: datetime | None = None
        self._last_run_started_at: datetime | None = None
        self._last_run_completed_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._run_count = 0
        self._error_count = 0
        self._last_error: str | None = None
        self._last_result_summary: dict | None = None

    def start(self, *, loop_factory: Callable[[], Any], interval_seconds: int = 300) -> dict:
        if self._task and not self._task.done():
            return self.snapshot()
        self._loop_factory = loop_factory
        self._interval_seconds = int(interval_seconds)
        self._enabled = True
        self._status = "starting"
        self._started_at = _utc_now()
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())
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
        return self.snapshot()

    async def _run(self) -> None:
        if not self._loop_factory or not self._stop_event:
            self._status = "stopped"
            return
        while not self._stop_event.is_set():
            self._status = "running_cycle"
            self._last_run_started_at = _utc_now()
            try:
                result = await asyncio.to_thread(self._run_cycle)
                self._last_run_completed_at = _utc_now()
                self._run_count += 1
                self._last_error = None
                self._last_result_summary = self._summarize_result(result)
                self._status = "sleeping"
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                self._last_run_completed_at = _utc_now()
                self._error_count += 1
                self._last_error = str(exc)
                self._status = "error_sleeping"

            self._next_run_at = _utc_now() + timedelta(seconds=self._interval_seconds)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                continue
        self._status = "stopped"
        self._next_run_at = None

    def _run_cycle(self) -> dict:
        if not self._loop_factory:
            raise RuntimeError("agent loop factory is not configured")
        loop = self._loop_factory()
        result = loop.run_once()
        if not isinstance(result, dict):
            raise TypeError("paper loop result must be a dict")
        return result

    def _summarize_result(self, result: dict) -> dict:
        ticket = result.get("approval_queue", {}).get("ticket", {})
        portfolio = result.get("paper_portfolio", {})
        intent = result.get("intent", {})
        broker_paper_order = result.get("broker_paper_order", {})
        return {
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "status_zh": zh_status(result.get("status")),
            "intent_symbol": intent.get("symbol"),
            "intent_strategy_id": intent.get("strategy_id"),
            "risk_status": result.get("risk_check", {}).get("status"),
            "risk_status_zh": zh_status(result.get("risk_check", {}).get("status")),
            "ticket_status": ticket.get("status"),
            "ticket_status_zh": zh_status(ticket.get("status")),
            "paper_order_status": result.get("paper_order", {}).get("status"),
            "paper_order_status_zh": zh_status(result.get("paper_order", {}).get("status")),
            "broker_paper_order_status": broker_paper_order.get("status"),
            "broker_paper_order_status_zh": zh_status(broker_paper_order.get("status")),
            "broker_paper_order_id": broker_paper_order.get("broker_order_id"),
            "paper_trade_count": portfolio.get("trade_count"),
            "paper_total_equity": portfolio.get("total_equity"),
        }

    def snapshot(self) -> dict:
        task_running = bool(self._task and not self._task.done())
        return {
            "enabled": self._enabled,
            "enabled_zh": "是" if self._enabled else "否",
            "status": self._status,
            "status_zh": zh_status(self._status),
            "task_running": task_running,
            "task_running_zh": "是" if task_running else "否",
            "interval_seconds": self._interval_seconds,
            "started_at": _iso(self._started_at),
            "last_run_started_at": _iso(self._last_run_started_at),
            "last_run_completed_at": _iso(self._last_run_completed_at),
            "next_run_at": _iso(self._next_run_at),
            "run_count": self._run_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_result_summary": self._last_result_summary,
        }


AUTO_PAPER_AGENT = AutoPaperAgentRuntime()
