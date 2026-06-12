from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from backend.app.schemas.strategy_dsl import validate_strategy
from backend.app.services.backtest import run_buy_and_hold_fixture
from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, build_default_loop

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "configs" / "trading_governor_policy.yaml"
DATA_PATH = ROOT / "data" / "sample_prices.csv"
QUEUE_PATH = ROOT / "runtime" / "approval_queue.json"


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": "research_paper_order_intent_review",
        "live_trading_enabled": False,
        "kill_switch_active": False,
        "refresh_interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS,
    }


@router.get("/owner/summary")
def owner_summary() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    pending = [item for item in queue.list_tickets() if item.get("status") == "pending_owner_approval"]
    return {
        "system_mode": "research_paper_order_intent_review",
        "strategies": {"research": 1, "paper": 1, "live_order_review": len(pending)},
        "required_owner_actions": ["review_order_tickets"] if pending else [],
        "pending_order_tickets": len(pending),
    }


@router.post("/strategy/validate")
def strategy_validate(payload: dict) -> dict:
    strategy = validate_strategy(payload)
    return {"valid": True, "normalized_strategy": strategy.model_dump(mode="json"), "warnings": []}


@router.post("/backtest/run")
def backtest_run(payload: dict | None = None) -> dict:
    payload = payload or {}
    metrics = run_buy_and_hold_fixture(DATA_PATH, initial_capital=float(payload.get("initial_capital", 10000)))
    return {"run_id": "fixture_bt_001", "metrics": metrics}


@router.post("/paper/run-once")
def paper_run_once() -> dict:
    loop = build_default_loop(queue_path=QUEUE_PATH)
    return loop.run_once()


@router.get("/orders/approval-queue")
def approval_queue() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    return {"tickets": queue.latest(), "count": len(queue.list_tickets())}


@router.get("/agent/status")
def agent_status() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    return {
        "agent_id": "paper_trading_loop",
        "status": "ready",
        "refresh_interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS,
        "capabilities": ["paper_trading", "risk_check", "approval_queue", "broker_ready_order_ticket"],
        "pending_tickets": len(queue.list_tickets()),
    }


@router.get("/dashboard/state")
def dashboard_state() -> dict:
    return {
        "health": health(),
        "owner_summary": owner_summary(),
        "agent_status": agent_status(),
        "approval_queue": approval_queue(),
    }


@router.post("/live/order-intent")
def live_order_intent(payload: dict) -> dict:
    policy = GovernorPolicy.load(POLICY_PATH)
    broker = FailClosedLiveBroker()
    intent = LiveOrderIntent(
        idempotency_key=payload.get("idempotency_key", ""),
        symbol=payload.get("symbol", "SPY"),
        side=payload.get("side", "buy"),
        quantity=float(payload.get("quantity", 1)),
        notional_aud=float(payload.get("notional_aud", 999999)),
    )
    return broker.submit_order_intent(intent, policy, broker_health_ok=False)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alpha Dashboard</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f7f7f4; color: #1d1f21; }
    header { padding: 20px 28px; border-bottom: 1px solid #d9d9d2; background: #ffffff; display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    h1 { margin: 0; font-size: 22px; font-weight: 700; }
    main { padding: 24px 28px; display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    section { background: #ffffff; border: 1px solid #d9d9d2; border-radius: 8px; padding: 16px; min-height: 132px; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    button { border: 1px solid #1d1f21; background: #1d1f21; color: #fff; border-radius: 6px; padding: 9px 12px; cursor: pointer; }
    button.secondary { background: #fff; color: #1d1f21; }
    pre { white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.45; margin: 0; }
    .status { font-size: 13px; color: #555; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Alpha Dashboard</h1>
      <div class="status" id="lastUpdated">Loading</div>
    </div>
    <div>
      <button onclick="runCycle()">Run Paper Cycle</button>
      <button class="secondary" onclick="loadState()">Refresh</button>
    </div>
  </header>
  <main>
    <section><h2>Agent Status</h2><pre id="agent"></pre></section>
    <section><h2>Owner Summary</h2><pre id="summary"></pre></section>
    <section><h2>Approval Queue</h2><pre id="queue"></pre></section>
    <section><h2>System Health</h2><pre id="health"></pre></section>
  </main>
  <script>
    async function loadState() {
      const response = await fetch('/dashboard/state');
      const data = await response.json();
      document.getElementById('health').textContent = JSON.stringify(data.health, null, 2);
      document.getElementById('summary').textContent = JSON.stringify(data.owner_summary, null, 2);
      document.getElementById('agent').textContent = JSON.stringify(data.agent_status, null, 2);
      document.getElementById('queue').textContent = JSON.stringify(data.approval_queue, null, 2);
      document.getElementById('lastUpdated').textContent = 'Last updated: ' + new Date().toLocaleString();
    }
    async function runCycle() {
      await fetch('/paper/run-once', { method: 'POST' });
      await loadState();
    }
    loadState();
    setInterval(loadState, 300000);
  </script>
</body>
</html>
"""
