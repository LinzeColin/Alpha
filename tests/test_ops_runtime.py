from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from backend.app.services.ops_runtime import AutoOpsMaintenanceRuntime


def test_auto_ops_maintenance_runtime_runs_backup_and_history(tmp_path):
    runtime = AutoOpsMaintenanceRuntime()

    def loop_snapshot():
        return {
            "enabled": True,
            "status": "sleeping",
            "task_running": True,
            "interval_seconds": 300,
            "run_count": 1,
            "error_count": 0,
        }

    async def exercise():
        status_path = tmp_path / "runtime" / "ops_maintenance_status.json"
        runtime.start(
            root=tmp_path,
            loop_snapshot_provider=loop_snapshot,
            interval_seconds=60,
            backup_interval_seconds=1,
            max_backup_count=2,
            max_history_rows=5,
            history_path=tmp_path / "runtime" / "ops_health_history.jsonl",
            backup_dir=tmp_path / "runtime" / "backups",
            status_path=status_path,
        )
        for _ in range(100):
            snapshot = runtime.snapshot()
            if snapshot["run_count"] >= 1:
                break
            await asyncio.sleep(0.01)
        running = runtime.snapshot()
        heartbeat = json.loads(status_path.read_text(encoding="utf-8"))
        stopped = await runtime.stop()
        stopped_heartbeat = json.loads(status_path.read_text(encoding="utf-8"))
        return running, stopped, heartbeat, stopped_heartbeat

    running, stopped, heartbeat, stopped_heartbeat = asyncio.run(exercise())

    assert running["task_running"] is True
    assert running["run_count"] == 1
    assert running["backup_count"] == 1
    assert running["error_count"] == 0
    assert running["status"] == "maintenance_sleeping"
    assert running["status_zh"] == "等待下次维护"
    assert running["task_running_zh"] == "是"
    assert running["last_result_summary"]["backup_created"] is True
    assert running["last_result_summary"]["status_zh"] == "已完成"
    assert running["last_result_summary"]["rotation_status_zh"] in {"未变化", "已轮转"}
    assert Path(running["history_path"]).exists()
    assert len(list((tmp_path / "runtime" / "backups").glob("alpha_state_*"))) == 1
    assert heartbeat["snapshot_kind"] == "ops_maintenance"
    assert heartbeat["process_id"] == os.getpid()
    assert heartbeat["task_running"] is True
    assert heartbeat["last_persist_error_zh"] == "无"
    assert heartbeat["run_count"] == 1
    assert stopped["status"] == "stopped"
    assert stopped["status_zh"] == "已停止"
    assert stopped["task_running"] is False
    assert stopped_heartbeat["status"] == "stopped"
    assert stopped_heartbeat["task_running"] is False
