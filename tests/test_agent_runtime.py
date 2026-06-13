import asyncio

from backend.app.services.agent_runtime import AutoPaperAgentRuntime


class FakePaperLoop:
    def run_once(self):
        return {
            "run_id": "run_test",
            "status": "completed",
            "intent": {"symbol": "TLT", "strategy_id": "momentum_TLT_20d"},
            "risk_check": {"status": "approved_for_owner_review"},
            "approval_queue": {"ticket": {"status": "pending_owner_approval"}},
            "paper_order": {"status": "filled"},
            "broker_paper_order": {"status": "filled", "broker_order_id": "paper_123", "execution_model_zh": "固定佣金与滑点模型", "commission": 1.0, "slippage_bps": 5.0},
            "paper_portfolio": {"trade_count": 1, "total_equity": 9998.95, "total_commission": 1.0},
        }


def test_auto_paper_agent_runtime_runs_immediate_cycle_and_stops():
    runtime = AutoPaperAgentRuntime()

    async def exercise():
        runtime.start(loop_factory=FakePaperLoop, interval_seconds=60)
        for _ in range(50):
            snapshot = runtime.snapshot()
            if snapshot["run_count"] >= 1:
                break
            await asyncio.sleep(0.01)
        running = runtime.snapshot()
        stopped = await runtime.stop()
        return running, stopped

    running, stopped = asyncio.run(exercise())

    assert running["task_running"] is True
    assert running["run_count"] == 1
    assert running["error_count"] == 0
    assert running["status"] == "sleeping"
    assert running["status_zh"] == "等待下次运行"
    assert running["task_running_zh"] == "是"
    assert running["last_result_summary"]["intent_symbol"] == "TLT"
    assert running["last_result_summary"]["broker_paper_order_status"] == "filled"
    assert running["last_result_summary"]["broker_paper_order_status_zh"] == "模拟成交"
    assert running["last_result_summary"]["ticket_status_zh"] == "待人工确认"
    assert running["last_result_summary"]["broker_paper_order_id"] == "paper_123"
    assert running["last_result_summary"]["broker_paper_execution_model_zh"] == "固定佣金与滑点模型"
    assert running["last_result_summary"]["broker_paper_commission"] == 1.0
    assert running["last_result_summary"]["broker_paper_slippage_bps"] == 5.0
    assert running["last_result_summary"]["paper_total_commission"] == 1.0
    assert stopped["status"] == "stopped"
    assert stopped["status_zh"] == "已停止"
    assert stopped["task_running"] is False
