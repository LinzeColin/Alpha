from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def atomic_write_runtime_snapshot(path: str | Path, snapshot: dict, *, snapshot_kind: str) -> dict:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    enriched = {
        **snapshot,
        "snapshot_kind": snapshot_kind,
        "persisted_at": utc_now_iso(),
        "process_id": os.getpid(),
        "process_alive_at_write": True,
    }
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(enriched, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return enriched


def read_persisted_runtime_snapshot(
    path: str | Path,
    *,
    expected_kind: str,
    max_age_seconds: int,
    now: datetime | None = None,
) -> tuple[dict | None, dict]:
    target = Path(path)
    evidence: dict[str, Any] = {
        "path": str(target),
        "expected_kind": expected_kind,
        "exists": target.exists(),
        "max_age_seconds": max_age_seconds,
        "valid": False,
    }
    if not target.exists():
        evidence["reason"] = "missing"
        evidence["reason_zh"] = "心跳文件不存在。"
        return None, evidence
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        evidence["reason"] = "invalid_json"
        evidence["reason_zh"] = "心跳文件无法解析。"
        evidence["error"] = exc.__class__.__name__
        return None, evidence
    if not isinstance(payload, dict):
        evidence["reason"] = "invalid_payload"
        evidence["reason_zh"] = "心跳内容不是对象。"
        return None, evidence
    evidence["loaded"] = True
    evidence["snapshot_kind"] = payload.get("snapshot_kind")
    evidence["persisted_at"] = payload.get("persisted_at")
    evidence["process_id"] = payload.get("process_id")
    evidence["task_running"] = payload.get("task_running")
    if payload.get("snapshot_kind") != expected_kind:
        evidence["reason"] = "wrong_kind"
        evidence["reason_zh"] = "心跳类型不匹配。"
        return None, evidence
    persisted_at = _parse_iso(payload.get("persisted_at"))
    if not persisted_at:
        evidence["reason"] = "missing_persisted_at"
        evidence["reason_zh"] = "心跳缺少写入时间。"
        return None, evidence
    current = now or utc_now()
    age_seconds = max(0, int((current - persisted_at).total_seconds()))
    evidence["age_seconds"] = age_seconds
    if age_seconds > max_age_seconds:
        evidence["reason"] = "stale"
        evidence["reason_zh"] = "心跳已过期。"
        return None, evidence
    process_alive = _process_alive(payload.get("process_id"))
    evidence["process_alive"] = process_alive
    if process_alive is not True:
        evidence["reason"] = "process_not_alive" if process_alive is False else "process_status_unknown"
        evidence["reason_zh"] = "心跳进程未运行。" if process_alive is False else "无法确认心跳进程仍在运行。"
        return None, evidence
    payload["persisted_runtime_evidence"] = {**evidence, "valid": True, "reason": "valid", "reason_zh": "心跳新鲜且进程仍在运行。"}
    return payload, payload["persisted_runtime_evidence"]


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


def _process_alive(raw_pid: Any) -> bool | None:
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    return True
