from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from backend.app.schemas.strategy_dsl import validate_strategy
from backend.app.services.agent_runtime import AUTO_PAPER_AGENT
from backend.app.services.backtest import run_buy_and_hold_fixture
from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, build_default_loop, latest_mark_prices
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.strategy_iteration import run_strategy_tournament

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "configs" / "trading_governor_policy.yaml"
DATA_PATH = ROOT / "data" / "sample_prices.csv"
QUEUE_PATH = ROOT / "runtime" / "approval_queue.json"
PAPER_STATE_PATH = ROOT / "runtime" / "paper_portfolio.json"


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
    loop = build_default_loop(queue_path=QUEUE_PATH, paper_state_path=PAPER_STATE_PATH)
    return loop.run_once()


@router.get("/orders/approval-queue")
def approval_queue() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    return {"tickets": queue.latest(), "count": len(queue.list_tickets())}


@router.get("/agent/status")
def agent_status() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    tickets = queue.list_tickets()
    pending = [item for item in tickets if item.get("status") == "pending_owner_approval"]
    latest_ticket = tickets[-1] if tickets else None
    return {
        "agent_id": "paper_trading_loop",
        "status": "ready",
        "refresh_interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS,
        "capabilities": [
            "paper_trading",
            "risk_check",
            "approval_queue",
            "broker_ready_order_ticket",
        ],
        "pending_tickets": len(pending),
        "latest_ticket_created_at": latest_ticket.get("created_at") if latest_ticket else None,
        "loop": AUTO_PAPER_AGENT.snapshot(),
    }


@router.get("/agent/loop/status")
def agent_loop_status() -> dict:
    return AUTO_PAPER_AGENT.snapshot()


@router.get("/paper/portfolio")
def paper_portfolio() -> dict:
    return PaperBroker.load(PAPER_STATE_PATH).portfolio_snapshot(latest_mark_prices(DATA_PATH))


@router.post("/strategy/tournament/run")
def strategy_tournament_run() -> dict:
    return run_strategy_tournament(DATA_PATH)


@router.get("/dashboard/state")
def dashboard_state() -> dict:
    return {
        "health": health(),
        "owner_summary": owner_summary(),
        "agent_status": agent_status(),
        "paper_portfolio": paper_portfolio(),
        "strategy_tournament": strategy_tournament_run(),
        "approval_queue": approval_queue(),
    }


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
    body { margin: 0; background: #f5f6f3; color: #1d1f21; }
    header { padding: 18px 28px; border-bottom: 1px solid #d8ddd2; background: #ffffff; display: flex; justify-content: space-between; gap: 16px; align-items: center; position: sticky; top: 0; z-index: 2; }
    h1 { margin: 0; font-size: 22px; font-weight: 750; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    main { padding: 20px 28px 28px; display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr); }
    section { background: #ffffff; border: 1px solid #d8ddd2; border-radius: 8px; padding: 16px; }
    button { border: 1px solid #1d1f21; background: #1d1f21; color: #fff; border-radius: 6px; padding: 9px 12px; cursor: pointer; font-weight: 650; }
    button.secondary { background: #fff; color: #1d1f21; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid #eceee8; text-align: left; vertical-align: top; }
    th { color: #5c6258; font-size: 12px; text-transform: uppercase; letter-spacing: 0; }
    pre { white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.45; margin: 0; }
    .status { font-size: 13px; color: #555; }
    .metric-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
    .metric { border: 1px solid #eceee8; border-radius: 8px; padding: 12px; background: #fbfbf8; }
    .metric .label { color: #666d61; font-size: 12px; }
    .metric .value { font-size: 22px; font-weight: 760; margin-top: 5px; }
    .pill { display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }
    .ok { background: #e6f5ec; color: #176c3a; }
    .warn { background: #fff3d6; color: #8a5b00; }
    .danger { background: #fde7e7; color: #9b1c1c; }
    .grid-two { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    .muted { color: #6a7166; }
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
    <section>
      <h2>System Snapshot</h2>
      <div class="metric-grid" id="metrics"></div>
    </section>
    <div class="grid-two">
      <section><h2>Paper Portfolio</h2><div id="portfolio"></div></section>
      <section><h2>Agent Status</h2><div id="agent"></div></section>
    </div>
    <section><h2>Strategy Tournament</h2><div id="tournament"></div></section>
    <section><h2>Approval Queue</h2><div id="queue"></div></section>
  </main>
  <script>
    function pill(text, kind) {
      return `<span class="pill ${kind}">${text}</span>`;
    }
    function metric(label, value) {
      return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
    }
    function renderMetrics(data) {
      const portfolio = data.paper_portfolio || {};
      const queue = data.approval_queue || {};
      const health = data.health || {};
      const loop = (data.agent_status && data.agent_status.loop) || {};
      document.getElementById('metrics').innerHTML = [
        metric('Agent', pill(data.agent_status.status, 'ok')),
        metric('Loop', pill(loop.status || 'unknown', loop.error_count ? 'danger' : 'ok')),
        metric('Paper Equity', Number(portfolio.total_equity || 0).toFixed(2)),
        metric('Paper Trades', portfolio.trade_count || 0),
        metric('Pending Tickets', queue.count || 0),
        metric('Refresh', `${health.refresh_interval_seconds || 300}s`)
      ].join('');
    }
    function renderPortfolio(portfolio) {
      const positions = portfolio.positions || [];
      const rows = positions.map(row => `<tr><td>${row.symbol}</td><td>${row.quantity}</td><td>${row.mark_price}</td><td>${row.market_value}</td></tr>`).join('');
      document.getElementById('portfolio').innerHTML = `
        <div class="metric-grid">
          ${metric('Cash', Number(portfolio.cash || 0).toFixed(2))}
          ${metric('Positions Value', Number(portfolio.positions_value || 0).toFixed(2))}
          ${metric('Total Equity', Number(portfolio.total_equity || 0).toFixed(2))}
        </div>
        <table><thead><tr><th>Symbol</th><th>Qty</th><th>Mark</th><th>Value</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">No paper positions yet</td></tr>'}</tbody></table>
      `;
    }
    function renderAgent(agent) {
      const loop = agent.loop || {};
      const summary = loop.last_result_summary || {};
      const loopKind = loop.error_count ? 'danger' : (loop.task_running ? 'ok' : 'warn');
      document.getElementById('agent').innerHTML = `
        <table>
          <tbody>
            <tr><th>ID</th><td>${agent.agent_id}</td></tr>
            <tr><th>Status</th><td>${pill(agent.status, 'ok')}</td></tr>
            <tr><th>Loop</th><td>${pill(loop.status || 'unknown', loopKind)}</td></tr>
            <tr><th>Run Count</th><td>${loop.run_count || 0}</td></tr>
            <tr><th>Refresh</th><td>${agent.refresh_interval_seconds}s</td></tr>
            <tr><th>Last Run</th><td>${loop.last_run_completed_at || 'Not yet'}</td></tr>
            <tr><th>Next Run</th><td>${loop.next_run_at || 'Pending'}</td></tr>
            <tr><th>Latest Ticket</th><td>${agent.latest_ticket_created_at || 'None'}</td></tr>
            <tr><th>Last Result</th><td>${summary.intent_symbol || 'None'} / ${summary.ticket_status || 'None'} / ${summary.paper_order_status || 'None'}</td></tr>
            <tr><th>Errors</th><td>${loop.error_count || 0}${loop.last_error ? ': ' + loop.last_error : ''}</td></tr>
            <tr><th>Capabilities</th><td>${(agent.capabilities || []).join(', ')}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderTournament(tournament) {
      const rows = (tournament.candidates || []).slice(0, 8).map(row => `
        <tr>
          <td>${row.strategy_id}</td><td>${row.symbol}</td><td>${row.lookback_days}</td>
          <td>${Number(row.total_return * 100).toFixed(2)}%</td><td>${Number(row.max_drawdown * 100).toFixed(2)}%</td>
          <td>${Number(row.score).toFixed(4)}</td><td>${row.decision}</td>
        </tr>`).join('');
      document.getElementById('tournament').innerHTML = `
        <div class="status">Winner: ${(tournament.winner && tournament.winner.strategy_id) || 'None'}</div>
        <table><thead><tr><th>Strategy</th><th>Symbol</th><th>Lookback</th><th>Return</th><th>Drawdown</th><th>Score</th><th>Decision</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }
    function renderQueue(queue) {
      const rows = (queue.tickets || []).map(ticket => `
        <tr>
          <td>${ticket.ticket_id}</td><td>${ticket.status}</td><td>${ticket.broker_payload.symbol}</td>
          <td>${ticket.broker_payload.side}</td><td>${ticket.broker_payload.quantity}</td>
          <td>${ticket.broker_payload.estimated_price}</td><td>${ticket.risk_check.status}</td>
        </tr>`).join('');
      document.getElementById('queue').innerHTML = `<table><thead><tr><th>Ticket</th><th>Status</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Risk</th></tr></thead><tbody>${rows || '<tr><td colspan="7" class="muted">No pending tickets</td></tr>'}</tbody></table>`;
    }
    async function loadState() {
      const response = await fetch('/dashboard/state');
      const data = await response.json();
      renderMetrics(data);
      renderPortfolio(data.paper_portfolio || {});
      renderAgent(data.agent_status || {});
      renderTournament(data.strategy_tournament || {});
      renderQueue(data.approval_queue || {});
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
