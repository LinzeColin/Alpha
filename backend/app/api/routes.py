from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from backend.app.schemas.strategy_dsl import validate_strategy
from backend.app.services.agent_runtime import AUTO_PAPER_AGENT
from backend.app.services.backtest import run_buy_and_hold_fixture
from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter
from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent
from backend.app.services.market_data_gateway import MarketDataGateway, MarketDataSnapshot
from backend.app.services.ops_health import collect_ops_health, create_runtime_backup
from backend.app.services.ops_runtime import AUTO_OPS_MAINTENANCE
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, build_default_loop, latest_mark_prices
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.strategy_iteration import run_strategy_tournament

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "configs" / "trading_governor_policy.yaml"
DATA_PATH = ROOT / "data" / "sample_prices.csv"
MARKET_DATA_CONFIG_PATH = ROOT / "configs" / "market_data.yaml"
QUEUE_PATH = ROOT / "runtime" / "approval_queue.sqlite3"
PAPER_STATE_PATH = ROOT / "runtime" / "paper_portfolio.json"
PID_PATH = ROOT / "runtime" / "alpha_dashboard.pid"
LOG_PATH = ROOT / "runtime" / "alpha_dashboard.log"


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "status_zh": "正常",
        "mode": "research_paper_order_intent_review",
        "mode_zh": "研究、模拟交易与候选订单人工复核模式",
        "live_trading_enabled": False,
        "live_trading_enabled_zh": "否",
        "kill_switch_active": False,
        "kill_switch_active_zh": "否",
        "refresh_interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS,
    }


def build_market_data_gateway() -> MarketDataGateway:
    return MarketDataGateway(root=ROOT, config_path=MARKET_DATA_CONFIG_PATH)


def resolve_market_data() -> MarketDataSnapshot:
    return build_market_data_gateway().resolve_price_path()


@router.get("/owner/summary")
def owner_summary() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    queue_summary = queue.summary()
    return {
        "system_mode": "research_paper_order_intent_review",
        "strategies": {"research": 1, "paper": 1, "live_order_review": queue_summary["fresh_pending_count"]},
        "required_owner_actions": ["review_order_tickets"] if queue_summary["fresh_pending_count"] else [],
        "pending_order_tickets": queue_summary["fresh_pending_count"],
        "expired_order_tickets": queue_summary["expired_pending_count"],
        "approval_queue_storage": queue.storage_status(),
    }


@router.post("/strategy/validate")
def strategy_validate(payload: dict) -> dict:
    strategy = validate_strategy(payload)
    return {"valid": True, "normalized_strategy": strategy.model_dump(mode="json"), "warnings": []}


@router.post("/backtest/run")
def backtest_run(payload: dict | None = None) -> dict:
    payload = payload or {}
    market_data = resolve_market_data()
    metrics = run_buy_and_hold_fixture(market_data.price_path, initial_capital=float(payload.get("initial_capital", 10000)))
    metrics["market_data"] = market_data.status
    return {"run_id": "fixture_bt_001", "metrics": metrics}


@router.post("/paper/run-once")
def paper_run_once() -> dict:
    loop = build_default_loop(queue_path=QUEUE_PATH, paper_state_path=PAPER_STATE_PATH)
    return loop.run_once()


@router.get("/orders/approval-queue")
def approval_queue() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    summary = queue.summary()
    return {
        "tickets": queue.latest_with_freshness(),
        "count": summary["fresh_pending_count"],
        "summary": summary,
        "storage": queue.storage_status(),
    }


@router.post("/orders/approval-queue/{ticket_id}/owner-review")
def approval_queue_owner_review(ticket_id: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    result = ApprovalQueue(QUEUE_PATH).mark_owner_reviewed(
        ticket_id,
        actor_id=str(payload.get("actor_id", "owner_dashboard")),
        note=payload.get("note"),
    )
    return _queue_transition_response(result)


@router.post("/orders/approval-queue/{ticket_id}/reject")
def approval_queue_reject(ticket_id: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    result = ApprovalQueue(QUEUE_PATH).reject(
        ticket_id,
        actor_id=str(payload.get("actor_id", "owner_dashboard")),
        note=payload.get("note"),
    )
    return _queue_transition_response(result)


@router.post("/orders/approval-queue/{ticket_id}/mark-exported")
def approval_queue_mark_exported(ticket_id: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    result = ApprovalQueue(QUEUE_PATH).mark_exported(
        ticket_id,
        actor_id=str(payload.get("actor_id", "owner_dashboard")),
        note=payload.get("note"),
    )
    return _queue_transition_response(result)


def _queue_transition_response(result: dict) -> dict:
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="ticket_not_found")
    if result.get("status") == "blocked":
        raise HTTPException(status_code=409, detail=result.get("reason", "ticket_transition_blocked"))
    return result


@router.get("/agent/status")
def agent_status() -> dict:
    queue = ApprovalQueue(QUEUE_PATH)
    queue_summary = queue.summary()
    return {
        "agent_id": "paper_trading_loop",
        "status": "ready",
        "refresh_interval_seconds": DEFAULT_REFRESH_INTERVAL_SECONDS,
        "capabilities": [
            "paper_trading",
            "risk_check",
            "approval_queue",
            "broker_ready_order_ticket",
            "broker_paper_adapter",
        ],
        "pending_tickets": queue_summary["fresh_pending_count"],
        "expired_tickets": queue_summary["expired_pending_count"],
        "latest_ticket_created_at": queue_summary["latest_ticket_created_at"],
        "latest_fresh_ticket_created_at": queue_summary["latest_fresh_ticket_created_at"],
        "approval_queue_storage": queue.storage_status(),
        "loop": AUTO_PAPER_AGENT.snapshot(),
    }


@router.get("/agent/loop/status")
def agent_loop_status() -> dict:
    return AUTO_PAPER_AGENT.snapshot()


@router.get("/paper/portfolio")
def paper_portfolio() -> dict:
    market_data = resolve_market_data()
    return PaperBroker.load(PAPER_STATE_PATH).portfolio_snapshot(latest_mark_prices(market_data.price_path))


@router.get("/paper/broker/status")
def paper_broker_status() -> dict:
    return LocalSandboxPaperBrokerAdapter(PaperBroker.load(PAPER_STATE_PATH)).status()


@router.post("/strategy/tournament/run")
def strategy_tournament_run() -> dict:
    return run_strategy_tournament(resolve_market_data().price_path)


@router.get("/market-data/status")
def market_data_status() -> dict:
    return resolve_market_data().status


@router.post("/market-data/refresh")
def market_data_refresh() -> dict:
    gateway = build_market_data_gateway()
    try:
        return gateway.refresh_public_stooq_cache()
    except Exception as exc:
        status = gateway.resolve_price_path(force_refresh=False).status
        status["refresh_attempted"] = True
        status["refresh_succeeded"] = False
        status["refresh_error"] = str(exc)
        return status


@router.get("/ops/health")
def ops_health() -> dict:
    return collect_ops_health(
        root=ROOT,
        queue_path=QUEUE_PATH,
        paper_state_path=PAPER_STATE_PATH,
        pid_path=PID_PATH,
        log_path=LOG_PATH,
        market_data_gateway=build_market_data_gateway(),
        loop_snapshot=AUTO_PAPER_AGENT.snapshot(),
    )


@router.post("/ops/backup")
def ops_backup() -> dict:
    backup = create_runtime_backup(
        root=ROOT,
        queue_path=QUEUE_PATH,
        paper_state_path=PAPER_STATE_PATH,
        market_data_cache_path=build_market_data_gateway().cache_path,
        pid_path=PID_PATH,
        log_path=LOG_PATH,
    )
    backup["health_after_backup"] = ops_health()
    backup["maintenance"] = AUTO_OPS_MAINTENANCE.snapshot()
    return backup


@router.get("/ops/maintenance/status")
def ops_maintenance_status() -> dict:
    return AUTO_OPS_MAINTENANCE.snapshot()


@router.get("/dashboard/state")
def dashboard_state() -> dict:
    return {
        "health": health(),
        "market_data": market_data_status(),
        "ops_health": ops_health(),
        "ops_maintenance": ops_maintenance_status(),
        "owner_summary": owner_summary(),
        "agent_status": agent_status(),
        "paper_portfolio": paper_portfolio(),
        "paper_broker_status": paper_broker_status(),
        "strategy_tournament": strategy_tournament_run(),
        "approval_queue": approval_queue(),
    }


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alpha 控制台</title>
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
    th { color: #5c6258; font-size: 12px; letter-spacing: 0; }
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
      <h1>Alpha 控制台</h1>
      <div class="status" id="lastUpdated">正在加载</div>
    </div>
    <div>
      <button onclick="runCycle()">运行模拟交易周期</button>
      <button class="secondary" onclick="backupRuntime()">生成运行备份</button>
      <button class="secondary" onclick="refreshMarketData()">刷新公共行情</button>
      <button class="secondary" onclick="loadState()">刷新</button>
    </div>
  </header>
  <main>
    <section>
      <h2>系统快照</h2>
      <div class="metric-grid" id="metrics"></div>
    </section>
    <div class="grid-two">
      <section><h2>模拟组合</h2><div id="portfolio"></div></section>
      <section><h2>智能体状态</h2><div id="agent"></div></section>
      <section><h2>模拟交易执行层</h2><div id="broker"></div></section>
      <section><h2>行情数据</h2><div id="marketData"></div></section>
      <section><h2>运行健康</h2><div id="opsHealth"></div></section>
    </div>
    <section><h2>策略锦标赛</h2><div id="tournament"></div></section>
    <section><h2>审批队列</h2><div id="queue"></div></section>
  </main>
  <script>
    const STATUS_TEXT = {
      ready: '就绪',
      sleeping: '等待下次运行',
      running_cycle: '正在运行周期',
      error_sleeping: '错误后等待',
      stopped: '已停止',
      completed: '已完成',
      queued: '已入队',
      duplicate: '重复候选单',
      skipped: '已跳过',
      filled: '模拟成交',
      pending_owner_approval: '待人工确认',
      fresh_pending_owner_approval: '有效，待人工确认',
      expired_owner_approval: '已过期，需重新生成',
      blocked_by_risk: '风控阻止',
      approved_for_owner_review: '已通过风控，待人工确认',
      promote_to_paper: '可进入模拟交易',
      hold_research: '继续研究观察',
      reject: '拒绝',
      rejected: '已拒绝',
      owner_reviewed: '已人工复核',
      owner_rejected: '已拒绝',
      broker_ticket_exported: '工单已导出',
      paper: '模拟交易',
      fresh: '有效',
      expired: '已过期',
      invalid: '无效',
      starting: '正在启动',
      blocked: '已阻止',
      unchanged: '未变化',
      updated: '已更新',
      healthy: '健康',
      degraded: '需关注',
      unhealthy: '不可用',
      pass: '通过',
      warn: '需关注',
      fail: '失败',
      pruned: '已轮转',
      running_maintenance: '正在维护',
      maintenance_sleeping: '等待下次维护',
      maintenance_error_sleeping: '维护错误后等待',
      unknown: '未知'
    };
    const CAPABILITY_TEXT = {
      paper_trading: '全自动模拟交易',
      risk_check: '自动风控检查',
      approval_queue: '自动进入审批队列',
      broker_ready_order_ticket: '经纪商就绪订单工单',
      broker_paper_adapter: '模拟交易执行适配器'
    };
    const AGENT_TEXT = {
      paper_trading_loop: '模拟交易循环智能体'
    };
    const ADAPTER_TEXT = {
      local_sandbox_paper_broker: '本地沙盒模拟经纪商适配器'
    };
    const BROKER_TEXT = {
      'Alpha Local Sandbox': 'Alpha 本地沙盒'
    };
    const ACCOUNT_TEXT = {
      local_paper_account: '本地模拟账户'
    };
    const SIDE_TEXT = { buy: '买入', sell: '卖出' };
    const ORDER_TYPE_TEXT = { market: '市价单' };
    const TIME_IN_FORCE_TEXT = { day: '当日有效' };
    const MARKET_DATA_PROVIDER_TEXT = {
      cache_or_fixture: '本地缓存优先',
      stooq: 'Stooq 公共延迟行情',
      direct_file: '直接文件'
    };
    const MARKET_DATA_SOURCE_TEXT = {
      public_cache: '公共延迟行情缓存',
      local_cache: '本地行情缓存',
      fixture: '样例数据',
      local_file: '本地文件'
    };
    const DATA_QUALITY_TEXT = {
      fresh: '新鲜',
      stale: '过期',
      sample: '样例',
      missing: '缺失'
    };
    const REASON_TEXT = {
      'pre-trade risk checks passed': '下单前风控检查通过',
      'kill switch active': '总开关已触发',
      'missing idempotency key': '缺少幂等键',
      'invalid side': '方向无效',
      'invalid quantity, price, or notional': '数量、价格或名义金额无效',
      'max order value not configured': '最大订单金额未配置',
      'max order value exceeded': '超过最大订单金额',
      ticket_not_found: '未找到工单',
      ticket_transition_blocked: '工单状态流转被阻止',
      ticket_must_be_owner_reviewed_before_export: '导出前必须先完成所有者复核',
      risk_blocked_ticket_cannot_be_owner_reviewed_or_exported: '风控阻止的工单不能复核或导出',
      ticket_already_in_requested_state: '工单已处于目标状态'
    };
    function displayStatus(value, fallback = '无') {
      if (value === null || value === undefined || value === '') return fallback;
      return STATUS_TEXT[value] || '未知状态';
    }
    function displayCapability(value) {
      return CAPABILITY_TEXT[value] || '未知能力';
    }
    function displayAgentId(value) {
      return AGENT_TEXT[value] || '未知智能体';
    }
    function displayAdapterId(value) {
      return ADAPTER_TEXT[value] || '未知适配器';
    }
    function displayBrokerName(value) {
      return BROKER_TEXT[value] || displayValue(value, '未知执行层');
    }
    function displayAccount(value) {
      return ACCOUNT_TEXT[value] || '本地账户';
    }
    function displaySide(value) {
      return SIDE_TEXT[value] || '未知方向';
    }
    function displayOrderType(value) {
      return ORDER_TYPE_TEXT[value] || '未知订单类型';
    }
    function displayTimeInForce(value) {
      return TIME_IN_FORCE_TEXT[value] || '未知有效期';
    }
    function displayReason(value) {
      if (value === null || value === undefined || value === '') return '无';
      return REASON_TEXT[value] || '未知原因';
    }
    function displayMarketDataProvider(value) {
      return MARKET_DATA_PROVIDER_TEXT[value] || '未知行情源';
    }
    function displayMarketDataSource(value) {
      return MARKET_DATA_SOURCE_TEXT[value] || '未知数据源';
    }
    function displayDataQuality(value) {
      return DATA_QUALITY_TEXT[value] || '未知质量';
    }
    function displayStrategyId(value) {
      if (!value) return '无';
      const raw = String(value);
      const match = raw.match(/^momentum_([^_]+)_(\\d+)d$/);
      if (match) return `动量策略 ${match[1]} ${match[2]}日`;
      if (raw.startsWith('fixture_momentum_')) return `样例动量策略 ${raw.replace('fixture_momentum_', '')}`;
      return raw;
    }
    function displayValue(value, fallback = '无') {
      return value === null || value === undefined || value === '' ? fallback : value;
    }
    function displayBool(value) {
      return value ? '是' : '否';
    }
    function displayStorageBackend(value) {
      if (value === 'sqlite') return 'SQLite 数据库';
      if (value === 'json') return 'JSON 文件';
      if (value === 'memory') return '内存';
      return '未知存储';
    }
    function pill(text, kind) {
      return `<span class="pill ${kind}">${text}</span>`;
    }
    function metric(label, value) {
      return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
    }
    function renderMetrics(data) {
      const portfolio = data.paper_portfolio || {};
      const queue = data.approval_queue || {};
      const queueSummary = queue.summary || {};
      const health = data.health || {};
      const agent = data.agent_status || {};
      const loop = agent.loop || {};
      const marketData = data.market_data || {};
      const opsHealth = data.ops_health || {};
      const opsMaintenance = data.ops_maintenance || {};
      document.getElementById('metrics').innerHTML = [
        metric('智能体', pill(displayStatus(agent.status), 'ok')),
        metric('循环', pill(displayStatus(loop.status, '未知'), loop.error_count ? 'danger' : 'ok')),
        metric('运行健康', pill(displayStatus(opsHealth.overall_status, '未知'), opsHealth.fail_count ? 'danger' : (opsHealth.warn_count ? 'warn' : 'ok'))),
        metric('自动维护', pill(displayStatus(opsMaintenance.status, '未知'), opsMaintenance.error_count ? 'danger' : (opsMaintenance.task_running ? 'ok' : 'warn'))),
        metric('行情源', displayMarketDataSource(marketData.source_kind)),
        metric('行情质量', pill(displayDataQuality(marketData.data_quality), marketData.real_market_data ? 'ok' : 'warn')),
        metric('最新行情日', displayValue(marketData.latest_date)),
        metric('模拟权益', Number(portfolio.total_equity || 0).toFixed(2)),
        metric('模拟交易数', portfolio.trade_count || 0),
        metric('有效候选单', queueSummary.fresh_pending_count || queue.count || 0),
        metric('过期候选单', queueSummary.expired_pending_count || 0),
        metric('已复核', queueSummary.owner_reviewed_count || 0),
        metric('已导出工单', queueSummary.broker_ticket_exported_count || 0),
        metric('队列存储', displayStorageBackend((queue.storage || {}).backend)),
        metric('刷新间隔', `${health.refresh_interval_seconds || 300} 秒`)
      ].join('');
    }
    function renderPortfolio(portfolio) {
      const positions = portfolio.positions || [];
      const rows = positions.map(row => `<tr><td>${row.symbol}</td><td>${row.quantity}</td><td>${row.mark_price}</td><td>${row.market_value}</td></tr>`).join('');
      document.getElementById('portfolio').innerHTML = `
        <div class="metric-grid">
          ${metric('现金', Number(portfolio.cash || 0).toFixed(2))}
          ${metric('持仓市值', Number(portfolio.positions_value || 0).toFixed(2))}
          ${metric('总权益', Number(portfolio.total_equity || 0).toFixed(2))}
        </div>
        <table><thead><tr><th>标的</th><th>数量</th><th>标记价</th><th>市值</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">暂无模拟持仓</td></tr>'}</tbody></table>
      `;
    }
    function renderOpsHealth(opsHealth) {
      const checks = opsHealth.checks || [];
      const rows = checks.map(check => {
        const kind = check.status === 'fail' ? 'danger' : (check.status === 'warn' ? 'warn' : 'ok');
        return `<tr><td>${check.title_zh || '未知检查'}</td><td>${pill(displayStatus(check.status), kind)}</td><td>${check.message_zh || ''}</td></tr>`;
      }).join('');
      const latestBackup = opsHealth.latest_backup || {};
      document.getElementById('opsHealth').innerHTML = `
        <div class="metric-grid">
          ${metric('总体状态', pill(displayStatus(opsHealth.overall_status), opsHealth.fail_count ? 'danger' : (opsHealth.warn_count ? 'warn' : 'ok')))}
          ${metric('通过', opsHealth.pass_count || 0)}
          ${metric('需关注', opsHealth.warn_count || 0)}
          ${metric('失败', opsHealth.fail_count || 0)}
        </div>
        <table>
          <tbody>
            <tr><th>最近备份</th><td>${displayValue(latestBackup.backup_path)}</td></tr>
            <tr><th>备份时间</th><td>${displayValue(latestBackup.created_at)}</td></tr>
            <tr><th>安全边界</th><td>${displayValue(opsHealth.safety_boundary && opsHealth.safety_boundary.message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无健康检查结果</td></tr>'}</tbody></table>
      `;
    }
    function renderOpsMaintenance(opsMaintenance) {
      const summary = opsMaintenance.last_result_summary || {};
      const kind = opsMaintenance.error_count ? 'danger' : (opsMaintenance.task_running ? 'ok' : 'warn');
      return `
        <table>
          <tbody>
            <tr><th>自动维护</th><td>${pill(displayStatus(opsMaintenance.status, '未知'), kind)}</td></tr>
            <tr><th>运行次数</th><td>${opsMaintenance.run_count || 0}</td></tr>
            <tr><th>自动备份次数</th><td>${opsMaintenance.backup_count || 0}</td></tr>
            <tr><th>健康采样间隔</th><td>${opsMaintenance.interval_seconds || 0} 秒</td></tr>
            <tr><th>备份间隔</th><td>${opsMaintenance.backup_interval_seconds || 0} 秒</td></tr>
            <tr><th>备份保留数</th><td>${opsMaintenance.max_backup_count || 0}</td></tr>
            <tr><th>上次维护</th><td>${displayValue(opsMaintenance.last_run_completed_at)}</td></tr>
            <tr><th>下次维护</th><td>${displayValue(opsMaintenance.next_run_at)}</td></tr>
            <tr><th>健康历史</th><td>${displayValue(opsMaintenance.history_path)}</td></tr>
            <tr><th>备份目录</th><td>${displayValue(opsMaintenance.backup_dir)}</td></tr>
            <tr><th>最近自动备份</th><td>${displayValue(summary.backup_path)}</td></tr>
            <tr><th>轮转状态</th><td>${displayStatus(summary.rotation_status, '无')}</td></tr>
            <tr><th>维护错误</th><td>${opsMaintenance.error_count || 0}${opsMaintenance.last_error ? '：' + displayReason(opsMaintenance.last_error) : ''}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderMarketData(marketData) {
      const latestPrices = marketData.latest_prices || {};
      const priceRows = Object.entries(latestPrices).map(([symbol, price]) => `<tr><td>${symbol}</td><td>${price}</td></tr>`).join('');
      const refreshStatus = marketData.refresh_attempted
        ? (marketData.refresh_succeeded ? '刷新成功' : '刷新失败：公共行情源不可用，已回退到本地数据。')
        : '尚未尝试刷新';
      document.getElementById('marketData').innerHTML = `
        <table>
          <tbody>
            <tr><th>提供方</th><td>${displayMarketDataProvider(marketData.provider)}</td></tr>
            <tr><th>来源</th><td>${displayMarketDataSource(marketData.source_kind)}</td></tr>
            <tr><th>质量</th><td>${pill(displayDataQuality(marketData.data_quality), marketData.real_market_data ? 'ok' : 'warn')}</td></tr>
            <tr><th>真实市场数据</th><td>${displayBool(marketData.real_market_data)}</td></tr>
            <tr><th>最新日期</th><td>${displayValue(marketData.latest_date)}</td></tr>
            <tr><th>标的数量</th><td>${marketData.symbol_count || 0}</td></tr>
            <tr><th>缓存年龄</th><td>${marketData.cache_age_seconds === null || marketData.cache_age_seconds === undefined ? '无缓存' : marketData.cache_age_seconds + ' 秒'}</td></tr>
            <tr><th>价格文件</th><td>${displayValue(marketData.price_path)}</td></tr>
            <tr><th>刷新状态</th><td>${refreshStatus}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>标的</th><th>最新收盘价</th></tr></thead><tbody>${priceRows || '<tr><td colspan="2" class="muted">暂无行情价格</td></tr>'}</tbody></table>
      `;
    }
    function renderAgent(agent) {
      const loop = agent.loop || {};
      const summary = loop.last_result_summary || {};
      const loopKind = loop.error_count ? 'danger' : (loop.task_running ? 'ok' : 'warn');
      document.getElementById('agent').innerHTML = `
        <table>
          <tbody>
            <tr><th>智能体</th><td>${displayAgentId(agent.agent_id)}</td></tr>
            <tr><th>状态</th><td>${pill(displayStatus(agent.status), 'ok')}</td></tr>
            <tr><th>循环</th><td>${pill(displayStatus(loop.status, '未知'), loopKind)}</td></tr>
            <tr><th>运行次数</th><td>${loop.run_count || 0}</td></tr>
            <tr><th>刷新间隔</th><td>${agent.refresh_interval_seconds} 秒</td></tr>
            <tr><th>上次运行</th><td>${loop.last_run_completed_at || '尚未运行'}</td></tr>
            <tr><th>下次运行</th><td>${loop.next_run_at || '等待中'}</td></tr>
            <tr><th>最新候选单</th><td>${agent.latest_ticket_created_at || '无'}</td></tr>
            <tr><th>最新有效候选单</th><td>${agent.latest_fresh_ticket_created_at || '无'}</td></tr>
            <tr><th>过期候选单</th><td>${agent.expired_tickets || 0}</td></tr>
            <tr><th>最新结果</th><td>${displayValue(summary.intent_symbol)} / ${displayStrategyId(summary.intent_strategy_id)} / ${displayStatus(summary.ticket_status)} / ${displayStatus(summary.paper_order_status)} / ${displayStatus(summary.broker_paper_order_status)}</td></tr>
            <tr><th>最新模拟经纪商订单</th><td>${displayValue(summary.broker_paper_order_id)}</td></tr>
            <tr><th>错误</th><td>${loop.error_count || 0}${loop.last_error ? '：' + displayReason(loop.last_error) : ''}</td></tr>
            <tr><th>能力</th><td>${(agent.capabilities || []).map(displayCapability).join('，')}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderBroker(broker) {
      const latest = broker.latest_trade || {};
      const latestLine = latest.symbol ? `${latest.symbol} / ${displaySide(latest.side)} / ${displayValue(latest.quantity)} @ ${displayValue(latest.price)}` : '暂无';
      document.getElementById('broker').innerHTML = `
        <table>
          <tbody>
            <tr><th>适配器</th><td>${displayAdapterId(broker.adapter_id)}</td></tr>
            <tr><th>名称</th><td>${displayBrokerName(broker.broker_name)}</td></tr>
            <tr><th>账户</th><td>${displayAccount(broker.account_ref)}</td></tr>
            <tr><th>模式</th><td>${displayStatus(broker.mode)}</td></tr>
            <tr><th>连接</th><td>${displayBool(broker.connected)}</td></tr>
            <tr><th>需要凭据</th><td>${displayBool(broker.credential_required)}</td></tr>
            <tr><th>允许真实下单</th><td>${displayBool(broker.live_order_submission_enabled)}</td></tr>
            <tr><th>交易次数</th><td>${broker.paper_trade_count || 0}</td></tr>
            <tr><th>最近模拟成交</th><td>${latestLine}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderTournament(tournament) {
      const rows = (tournament.candidates || []).slice(0, 8).map(row => `
        <tr>
          <td>${displayStrategyId(row.strategy_id)}</td><td>${row.symbol}</td><td>${row.lookback_days}</td>
          <td>${Number((row.total_return || 0) * 100).toFixed(2)}%</td><td>${Number((row.oos_return || 0) * 100).toFixed(2)}%</td>
          <td>${Number((row.hit_rate || 0) * 100).toFixed(2)}%</td><td>${row.validation_windows || 0}</td>
          <td>${Number((row.max_drawdown || 0) * 100).toFixed(2)}%</td><td>${Number(row.score || 0).toFixed(4)}</td><td>${displayStatus(row.decision)}</td>
        </tr>`).join('');
      document.getElementById('tournament').innerHTML = `
        <div class="status">当前胜出：${displayStrategyId(tournament.winner && tournament.winner.strategy_id)}</div>
        <table><thead><tr><th>策略</th><th>标的</th><th>回看天数</th><th>收益</th><th>样本外收益</th><th>命中率</th><th>验证窗口</th><th>回撤</th><th>分数</th><th>决策</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }
    function renderQueue(queue) {
      const storage = queue.storage || {};
      const rows = (queue.tickets || []).map(ticket => {
        const payload = ticket.broker_payload || {};
        const risk = ticket.risk_check || {};
        return `<tr>
          <td>${ticket.ticket_id}</td><td>${displayStatus(ticket.actionability || ticket.status)}</td><td>${payload.symbol || ''}</td>
          <td>${displaySide(payload.side)}</td><td>${payload.quantity || ''}</td>
          <td>${payload.estimated_price || ''}<br><span class="muted">${displayOrderType(payload.order_type)} / ${displayTimeInForce(payload.time_in_force)}</span></td>
          <td>${displayStatus(risk.status, '未知')}<br><span class="muted">${displayReason(risk.reason)}</span></td>
          <td>${displayStatus(ticket.freshness && ticket.freshness.status, '未知')}</td>
          <td>${(ticket.freshness && ticket.freshness.seconds_until_expiry) ?? '不适用'}</td>
          <td>${renderTicketActions(ticket)}</td>
        </tr>`;
      }).join('');
      document.getElementById('queue').innerHTML = `
        <div class="status">队列存储：${displayStorageBackend(storage.backend)} / 持久化：${displayBool(storage.durable)} / 文件：${displayValue(storage.path)}</div>
        <table><thead><tr><th>候选单</th><th>可操作性</th><th>标的</th><th>方向</th><th>数量</th><th>价格</th><th>风控</th><th>时效性</th><th>剩余秒数</th><th>操作</th></tr></thead><tbody>${rows || '<tr><td colspan="10" class="muted">暂无待审批候选单</td></tr>'}</tbody></table>
      `;
    }
    function renderTicketActions(ticket) {
      const ticketId = ticket.ticket_id || '';
      if (!ticketId) return '';
      if (ticket.status === 'pending_owner_approval' && ticket.actionability === 'fresh_pending_owner_approval') {
        return `<button class="secondary" onclick="ticketAction('${ticketId}', 'owner-review')">标记已复核</button> <button class="secondary" onclick="ticketAction('${ticketId}', 'reject')">拒绝</button>`;
      }
      if (ticket.status === 'owner_reviewed') {
        return `<button class="secondary" onclick="ticketAction('${ticketId}', 'mark-exported')">标记已导出</button> <button class="secondary" onclick="ticketAction('${ticketId}', 'reject')">拒绝</button>`;
      }
      if (ticket.status === 'pending_owner_approval') {
        return `<button class="secondary" onclick="ticketAction('${ticketId}', 'reject')">拒绝</button>`;
      }
      return '';
    }
    async function loadState() {
      try {
        const response = await fetch('/dashboard/state');
        const data = await response.json();
        renderMetrics(data);
        renderPortfolio(data.paper_portfolio || {});
        renderAgent(data.agent_status || {});
        renderBroker(data.paper_broker_status || {});
        renderMarketData(data.market_data || {});
        renderOpsHealth(data.ops_health || {});
        document.getElementById('opsHealth').insertAdjacentHTML('beforeend', renderOpsMaintenance(data.ops_maintenance || {}));
        renderTournament(data.strategy_tournament || {});
        renderQueue(data.approval_queue || {});
        document.getElementById('lastUpdated').textContent = '最近更新：' + new Date().toLocaleString('zh-CN');
      } catch (error) {
        document.getElementById('lastUpdated').textContent = '最近更新失败：请查看后台日志。';
      }
    }
    async function runCycle() {
      await fetch('/paper/run-once', { method: 'POST' });
      await loadState();
    }
    async function refreshMarketData() {
      document.getElementById('lastUpdated').textContent = '正在刷新公共行情...';
      await fetch('/market-data/refresh', { method: 'POST' });
      await loadState();
    }
    async function backupRuntime() {
      document.getElementById('lastUpdated').textContent = '正在生成运行备份...';
      const response = await fetch('/ops/backup', { method: 'POST' });
      if (!response.ok) {
        document.getElementById('lastUpdated').textContent = '运行备份失败：请查看后台日志。';
        return;
      }
      await loadState();
    }
    async function ticketAction(ticketId, action) {
      const response = await fetch(`/orders/approval-queue/${encodeURIComponent(ticketId)}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actor_id: 'owner_dashboard' })
      });
      if (!response.ok) {
        document.getElementById('lastUpdated').textContent = '审批操作失败：请刷新后重试，详情见后台日志。';
        return;
      }
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
