from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from backend.app.schemas.strategy_dsl import validate_strategy
from backend.app.services.agent_runtime import AUTO_PAPER_AGENT
from backend.app.services.app_entry import collect_app_entry_readiness
from backend.app.services.backtest import run_buy_and_hold_fixture
from backend.app.services.broker_paper_adapter import build_paper_broker_adapter
from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.broker_ticket_export import (
    build_broker_ready_order_export,
    format_broker_ready_order_csv,
    format_broker_ready_order_html_zh,
)
from backend.app.services.display_locale import zh_owner_action, zh_reason, zh_system_mode
from backend.app.services.policy import GovernorPolicy
from backend.app.services.live_broker import FailClosedLiveBroker, LiveOrderIntent
from backend.app.services.market_data_gateway import MarketDataGateway, MarketDataSnapshot, zh_market_data_refresh_error
from backend.app.services.moomoo_broker_probe import probe_moomoo_opend, probe_moomoo_quote_snapshot
from backend.app.services.ops_health import collect_ops_health, create_runtime_backup
from backend.app.services.ops_runtime import AUTO_OPS_MAINTENANCE
from backend.app.services.paper_readiness import collect_paper_trading_readiness
from backend.app.services.paper_trading_loop import DEFAULT_REFRESH_INTERVAL_SECONDS, build_default_loop, latest_mark_prices
from backend.app.services.paper_broker import PaperBroker
from backend.app.services.paper_broker_readiness import collect_paper_broker_readiness
from backend.app.services.paper_performance import summarize_paper_performance_history
from backend.app.services.soak_history import summarize_soak_readiness_history
from backend.app.services.soak_readiness import collect_soak_readiness
from backend.app.services.strategy_journal import summarize_strategy_tournament_history
from backend.app.services.strategy_iteration import run_strategy_tournament

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "configs" / "trading_governor_policy.yaml"
DATA_PATH = ROOT / "data" / "sample_prices.csv"
MARKET_DATA_CONFIG_PATH = ROOT / "configs" / "market_data.yaml"
PAPER_BROKER_CONFIG_PATH = ROOT / "configs" / "paper_broker.yaml"
QUEUE_PATH = ROOT / "runtime" / "approval_queue.sqlite3"
PAPER_STATE_PATH = ROOT / "runtime" / "paper_portfolio.json"
STRATEGY_HISTORY_PATH = ROOT / "runtime" / "strategy_tournament_history.jsonl"
PAPER_PERFORMANCE_PATH = ROOT / "runtime" / "paper_performance_history.jsonl"
SOAK_HISTORY_PATH = ROOT / "runtime" / "soak_readiness_history.jsonl"
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
    system_mode = "research_paper_order_intent_review"
    required_actions = ["review_order_tickets"] if queue_summary["fresh_pending_count"] else []
    return {
        "system_mode": system_mode,
        "system_mode_zh": zh_system_mode(system_mode),
        "strategies": {"research": 1, "paper": 1, "live_order_review": queue_summary["fresh_pending_count"]},
        "strategies_zh": {
            "research": "研究策略 1 个",
            "paper": "模拟交易策略 1 个",
            "live_order_review": f"待人工复核候选单 {queue_summary['fresh_pending_count']} 张",
        },
        "required_owner_actions": required_actions,
        "required_owner_actions_zh": [zh_owner_action(action) for action in required_actions],
        "pending_order_tickets": queue_summary["fresh_pending_count"],
        "expired_order_tickets": queue_summary["expired_pending_count"],
        "approval_queue_storage": queue.storage_status(),
        "message_zh": queue_summary["message_zh"],
    }


@router.post("/strategy/validate")
def strategy_validate(payload: dict) -> dict:
    try:
        strategy = validate_strategy(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "strategy_validation_failed", "message_zh": _strategy_validation_message_zh(exc)},
        ) from exc
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
    loop = build_default_loop(
        queue_path=QUEUE_PATH,
        paper_state_path=PAPER_STATE_PATH,
        strategy_history_path=STRATEGY_HISTORY_PATH,
        performance_history_path=PAPER_PERFORMANCE_PATH,
        market_data_gateway=build_market_data_gateway(),
    )
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


@router.get("/orders/approval-queue/{ticket_id}/broker-ticket")
def approval_queue_broker_ticket(ticket_id: str) -> dict:
    ticket = ApprovalQueue(QUEUE_PATH).get_ticket(ticket_id)
    if not ticket:
        raise _http_error(404, "ticket_not_found")
    return build_broker_ready_order_export(ticket)


@router.get("/orders/approval-queue/{ticket_id}/broker-ticket/view", response_class=HTMLResponse)
def approval_queue_broker_ticket_view(ticket_id: str) -> HTMLResponse:
    ticket = ApprovalQueue(QUEUE_PATH).get_ticket(ticket_id)
    if not ticket:
        raise _http_error(404, "ticket_not_found")
    export_package = build_broker_ready_order_export(ticket)
    return HTMLResponse(format_broker_ready_order_html_zh(export_package))


@router.get("/orders/approval-queue/{ticket_id}/broker-ticket.csv", response_class=PlainTextResponse)
def approval_queue_broker_ticket_csv(ticket_id: str) -> PlainTextResponse:
    ticket = ApprovalQueue(QUEUE_PATH).get_ticket(ticket_id)
    if not ticket:
        raise _http_error(404, "ticket_not_found")
    export_package = build_broker_ready_order_export(ticket)
    return PlainTextResponse(format_broker_ready_order_csv(export_package), media_type="text/csv; charset=utf-8")


def _queue_transition_response(result: dict) -> dict:
    if result.get("status") == "not_found":
        raise _http_error(404, "ticket_not_found")
    if result.get("status") == "blocked":
        raise _http_error(409, str(result.get("reason", "ticket_transition_blocked")))
    return result


def _http_error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message_zh": zh_reason(code)})


def _strategy_validation_message_zh(exc: Exception) -> str:
    text = str(exc)
    if "MVP 禁止使用杠杆" in text:
        return "策略定义校验失败：MVP 禁止使用杠杆。"
    if "MVP 禁止卖空" in text:
        return "策略定义校验失败：MVP 禁止卖空。"
    if "MVP 禁止期权" in text:
        return "策略定义校验失败：MVP 禁止期权。"
    if "MVP 禁止加密货币提现" in text:
        return "策略定义校验失败：MVP 禁止加密货币提现。"
    if "标的列表不能重复" in text:
        return "策略定义校验失败：标的列表不能重复。"
    return "策略定义校验失败：请检查资产类别、调仓频率、信号、标的列表和安全约束。"


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


@router.get("/paper/performance/history")
def paper_performance_history() -> dict:
    return summarize_paper_performance_history(PAPER_PERFORMANCE_PATH)


@router.get("/paper/broker/status")
def paper_broker_status() -> dict:
    paper_broker = PaperBroker.load(PAPER_STATE_PATH)
    return build_paper_broker_adapter(paper_broker, config_path=PAPER_BROKER_CONFIG_PATH).status()


@router.get("/paper/broker/external-snapshot")
def paper_broker_external_snapshot() -> dict:
    paper_broker = PaperBroker.load(PAPER_STATE_PATH)
    return build_paper_broker_adapter(paper_broker, config_path=PAPER_BROKER_CONFIG_PATH).external_snapshot()


@router.get("/readiness/paper-broker")
def paper_broker_readiness() -> dict:
    broker_status = paper_broker_status()
    external_snapshot = paper_broker_external_snapshot()
    return collect_paper_broker_readiness(
        root=ROOT,
        config_path=PAPER_BROKER_CONFIG_PATH,
        paper_state_path=PAPER_STATE_PATH,
        paper_broker_status=broker_status,
        external_snapshot=external_snapshot,
    )


@router.get("/broker/moomoo/status")
def moomoo_broker_status() -> dict:
    return probe_moomoo_opend()


@router.get("/broker/moomoo/quote-snapshot")
def moomoo_quote_snapshot() -> dict:
    return probe_moomoo_quote_snapshot()


@router.post("/strategy/tournament/run")
def strategy_tournament_run() -> dict:
    return run_strategy_tournament(resolve_market_data().price_path)


@router.get("/strategy/tournament/history")
def strategy_tournament_history() -> dict:
    return summarize_strategy_tournament_history(STRATEGY_HISTORY_PATH)


@router.get("/market-data/status")
def market_data_status() -> dict:
    return resolve_market_data().status


@router.post("/market-data/refresh")
def market_data_refresh() -> dict:
    gateway = build_market_data_gateway()
    try:
        return gateway.refresh_cache()
    except Exception as exc:
        status = gateway.resolve_price_path(force_refresh=False).status
        status["refresh_attempted"] = True
        status["refresh_attempted_zh"] = "是"
        status["refresh_succeeded"] = False
        status["refresh_succeeded_zh"] = "否"
        status["refresh_error"] = str(exc)
        status["refresh_error_zh"] = zh_market_data_refresh_error(exc)
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


@router.get("/readiness/paper-trading")
def paper_trading_readiness() -> dict:
    return collect_paper_trading_readiness(
        root=ROOT,
        queue_path=QUEUE_PATH,
        paper_state_path=PAPER_STATE_PATH,
        strategy_history_path=STRATEGY_HISTORY_PATH,
        performance_history_path=PAPER_PERFORMANCE_PATH,
        loop_snapshot=AUTO_PAPER_AGENT.snapshot(),
    )


@router.get("/readiness/soak")
def soak_readiness() -> dict:
    return collect_soak_readiness(
        root=ROOT,
        ops_health_report=ops_health(),
        paper_readiness_report=paper_trading_readiness(),
        maintenance_snapshot=AUTO_OPS_MAINTENANCE.snapshot(),
    )


@router.get("/readiness/soak/history")
def soak_readiness_history() -> dict:
    return summarize_soak_readiness_history(SOAK_HISTORY_PATH)


@router.get("/readiness/app-entry")
def app_entry_readiness() -> dict:
    return collect_app_entry_readiness(root=ROOT)


@router.get("/dashboard/state")
def dashboard_state() -> dict:
    return {
        "health": health(),
        "market_data": market_data_status(),
        "ops_health": ops_health(),
        "ops_maintenance": ops_maintenance_status(),
        "paper_readiness": paper_trading_readiness(),
        "soak_readiness": soak_readiness(),
        "soak_readiness_history": soak_readiness_history(),
        "app_entry_readiness": app_entry_readiness(),
        "owner_summary": owner_summary(),
        "agent_status": agent_status(),
        "paper_portfolio": paper_portfolio(),
        "paper_performance": paper_performance_history(),
        "paper_broker_status": paper_broker_status(),
        "paper_broker_external_snapshot": paper_broker_external_snapshot(),
        "paper_broker_readiness": paper_broker_readiness(),
        "moomoo_broker_status": moomoo_broker_status(),
        "moomoo_quote_snapshot": moomoo_quote_snapshot(),
        "strategy_tournament": strategy_tournament_run(),
        "strategy_journal": strategy_tournament_history(),
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
    * { box-sizing: border-box; }
    body { margin: 0; background: #f5f6f3; color: #1d1f21; overflow-x: hidden; }
    header { padding: 18px 28px; border-bottom: 1px solid #d8ddd2; background: #ffffff; display: flex; justify-content: space-between; gap: 16px; align-items: center; position: sticky; top: 0; z-index: 2; flex-wrap: wrap; }
    .header-title { min-width: 220px; }
    .header-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
    h1 { margin: 0; font-size: 22px; font-weight: 750; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    main { padding: 20px 28px 28px; display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr); }
    section { background: #ffffff; border: 1px solid #d8ddd2; border-radius: 8px; padding: 16px; min-width: 0; overflow-x: auto; }
    button { border: 1px solid #1d1f21; background: #1d1f21; color: #fff; border-radius: 6px; padding: 9px 12px; cursor: pointer; font-weight: 650; min-height: 38px; max-width: 100%; }
    button.secondary { background: #fff; color: #1d1f21; }
    table { width: 100%; min-width: 620px; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid #eceee8; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
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
    @media (max-width: 720px) {
      header { padding: 14px; align-items: stretch; }
      .header-title { width: 100%; min-width: 0; }
      .header-actions { width: 100%; justify-content: stretch; }
      .header-actions button { flex: 1 1 140px; }
      main { padding: 12px; gap: 12px; }
      section { padding: 12px; }
      .grid-two { grid-template-columns: minmax(0, 1fr); }
      .metric-grid { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
      .metric .value { font-size: 18px; line-height: 1.25; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-title">
      <h1>Alpha 控制台</h1>
      <div class="status" id="lastUpdated">正在加载</div>
    </div>
    <div class="header-actions">
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
      <section><h2>模拟绩效</h2><div id="paperPerformance"></div></section>
      <section><h2>智能体运行状态</h2><div id="agent"></div></section>
      <section><h2>模拟交易状态（模拟交易执行层）</h2><div id="broker"></div></section>
      <section><h2>纸面交易提供方预检</h2><div id="paperBrokerReadiness"></div></section>
      <section><h2>富途牛牛开放网关（只读）</h2><div id="moomooBroker"></div></section>
      <section><h2>行情数据</h2><div id="marketData"></div></section>
      <section><h2>运行健康</h2><div id="opsHealth"></div></section>
      <section><h2>本地应用入口</h2><div id="appEntry"></div></section>
      <section><h2>交付就绪</h2><div id="paperReadiness"></div></section>
      <section><h2>长运行预检</h2><div id="soakReadiness"></div></section>
      <section><h2>长运行历史</h2><div id="soakHistory"></div></section>
    </div>
    <section><h2>策略锦标赛</h2><div id="tournament"></div></section>
    <section><h2>审批队列</h2><div id="queue"></div></section>
  </main>
  <script>
    const STATUS_TEXT = {
      ready: '就绪',
      not_ready: '未完全就绪',
      sleeping: '等待下次运行',
      running_cycle: '正在运行周期',
      error_sleeping: '错误后等待',
      stopped: '已停止',
      completed: '已完成',
      queued: '已入队',
      duplicate: '重复候选单',
      skipped: '已跳过',
      written: '已写入',
      empty: '暂无记录',
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
      read_only_probe: '只读连接探测',
      ready_read_only: '只读探测就绪',
      api_missing: '接口包未安装',
      api_import_error: '接口包导入失败',
      opend_unreachable: '开放网关未连接',
      not_configured: '未就绪',
      probe_error: '探测异常',
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
    const PAPER_BROKER_PROVIDER_TEXT = {
      local_sandbox: '本地沙盒模拟交易',
      external_paper_api: '外部纸面交易 API',
      alpaca_paper: 'Alpaca 纸面交易 API',
      ibkr_paper: 'IBKR 纸面交易 API',
      moomoo_paper: '富途牛牛纸面交易 API'
    };
    const ACCOUNT_TEXT = {
      local_paper_account: '本地模拟账户'
    };
    const SIDE_TEXT = { buy: '买入', sell: '卖出' };
    const ORDER_TYPE_TEXT = { market: '市价单' };
    const TIME_IN_FORCE_TEXT = { day: '当日有效' };
    const MARKET_DATA_PROVIDER_TEXT = {
      cache_or_fixture: '本地缓存优先',
      moomoo_opend: '富途牛牛只读行情',
      stooq: 'Stooq 公共延迟行情',
      direct_file: '直接文件'
    };
    const MARKET_DATA_SOURCE_TEXT = {
      broker_quote_cache: '经纪商只读行情缓存',
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
    const SIGNAL_TEXT = {
      momentum: '动量'
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
      expired_ticket_cannot_be_owner_reviewed_or_exported: '工单已过期，不能复核或导出',
      rejected_ticket_cannot_be_reopened_or_exported: '已拒绝工单不能重新打开或导出',
      exported_ticket_cannot_transition_except_rejection: '已导出工单只能转为拒绝状态',
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
    function displayPaperBrokerProvider(value) {
      return PAPER_BROKER_PROVIDER_TEXT[value] || '未知纸面交易提供方';
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
    function displaySignalType(value) {
      return SIGNAL_TEXT[value] || '未知信号';
    }
    function displayRefreshError(valueZh, value) {
      if (valueZh && valueZh !== '无') return valueZh;
      if (!value) return '行情源不可用，已回退到本地数据。';
      const raw = String(value);
      if (raw.includes('Moomoo')) return raw.replaceAll('Moomoo', '富途牛牛');
      if (raw.includes('public provider returned no usable market data')) return '公共行情源没有返回可用市场数据，已回退到本地数据。';
      if (raw.includes('public provider response missing columns')) return '公共行情源返回字段不完整，已回退到本地数据。';
      if (raw.toLowerCase().includes('timeout') || raw.toLowerCase().includes('timed out')) return '行情源连接超时，已回退到本地数据。';
      if (raw.toLowerCase().includes('connection') || raw.toLowerCase().includes('urlopen error')) return '行情源连接失败，已回退到本地数据。';
      return '行情刷新失败，已回退到本地数据。';
    }
    function displayStrategyId(value) {
      if (!value) return '无';
      const raw = String(value);
      const match = raw.match(/^momentum_([^_]+)_(\\d+)d$/);
      if (match) return `动量策略 ${match[1]} ${match[2]}日`;
      if (raw.startsWith('fixture_momentum_')) return `样例动量策略 ${raw.replace('fixture_momentum_', '')}`;
      if (raw.startsWith('cash_rebalance_')) return `现金回收减仓 ${raw.replace('cash_rebalance_', '')}`;
      if (raw.startsWith('target_rebalance_')) return `目标仓位再平衡 ${raw.replace('target_rebalance_', '')}`;
      return raw;
    }
    function displayValue(value, fallback = '无') {
      return value === null || value === undefined || value === '' ? fallback : value;
    }
    function displayTime(value, fallback = '无') {
      if (value === null || value === undefined || value === '') return fallback;
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return displayValue(value, fallback);
      return parsed.toLocaleString('zh-CN');
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
      const moomoo = data.moomoo_broker_status || {};
      const opsHealth = data.ops_health || {};
      const opsMaintenance = data.ops_maintenance || {};
      const paperReadiness = data.paper_readiness || {};
      const soakReadiness = data.soak_readiness || {};
      const soakHistory = data.soak_readiness_history || {};
      const appEntry = data.app_entry_readiness || {};
      const moomooQuote = data.moomoo_quote_snapshot || {};
      const strategyJournal = data.strategy_journal || {};
      const paperPerformance = data.paper_performance || {};
      const paperBrokerReadiness = data.paper_broker_readiness || {};
      document.getElementById('metrics').innerHTML = [
        metric('智能体', pill(displayStatus(agent.status), 'ok')),
        metric('循环', pill(displayStatus(loop.status, '未知'), loop.error_count ? 'danger' : 'ok')),
        metric('运行健康', pill(displayStatus(opsHealth.overall_status, '未知'), opsHealth.fail_count ? 'danger' : (opsHealth.warn_count ? 'warn' : 'ok'))),
        metric('本地应用入口', pill(appEntry.status_zh || displayStatus(appEntry.status, '未知'), appEntry.fail_count ? 'danger' : (appEntry.warn_count ? 'warn' : 'ok'))),
        metric('交付就绪', pill(paperReadiness.overall_status_zh || displayStatus(paperReadiness.overall_status, '未知'), paperReadiness.fail_count ? 'danger' : (paperReadiness.warn_count ? 'warn' : 'ok'))),
        metric('长运行预检', pill(soakReadiness.overall_status_zh || displayStatus(soakReadiness.overall_status, '未知'), soakReadiness.fail_count ? 'danger' : (soakReadiness.warn_count ? 'warn' : 'ok'))),
        metric('连续无失败采样', soakHistory.consecutive_no_fail_count || 0),
        metric('观察覆盖', soakHistory.target_coverage_zh || '0.00%'),
        metric('自动维护', pill(displayStatus(opsMaintenance.status, '未知'), opsMaintenance.error_count ? 'danger' : (opsMaintenance.task_running ? 'ok' : 'warn'))),
        metric('行情源', displayMarketDataSource(marketData.source_kind)),
        metric('富途牛牛开放网关', pill(moomoo.status_zh || displayStatus(moomoo.status, '未知'), moomoo.read_only_ready ? 'ok' : 'warn')),
        metric('富途行情', pill(moomooQuote.status_zh || displayStatus(moomooQuote.status, '未知'), moomooQuote.status === 'ready' ? 'ok' : 'warn')),
        metric('行情质量', pill(displayDataQuality(marketData.data_quality), marketData.real_market_data ? 'ok' : 'warn')),
        metric('最新行情日', displayValue(marketData.latest_date)),
        metric('模拟权益', Number(portfolio.total_equity || 0).toFixed(2)),
        metric('模拟收益率', paperPerformance.total_return_zh || '0.00%'),
        metric('纸面提供方预检', pill(paperBrokerReadiness.overall_status_zh || displayStatus(paperBrokerReadiness.overall_status, '未知'), paperBrokerReadiness.fail_count ? 'danger' : (paperBrokerReadiness.warn_count ? 'warn' : 'ok'))),
        metric('当前回撤', paperPerformance.current_drawdown_zh || '0.00%'),
        metric('模拟交易数', portfolio.trade_count || 0),
        metric('有效候选单', queueSummary.fresh_pending_count || queue.count || 0),
        metric('过期候选单', queueSummary.expired_pending_count || 0),
        metric('已复核', queueSummary.owner_reviewed_count || 0),
        metric('已导出工单', queueSummary.broker_ticket_exported_count || 0),
        metric('策略稳定度', strategyJournal.stability_ratio_zh || '0.00%'),
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
    function renderPaperPerformance(performance) {
      const rows = (performance.recent || []).slice(-8).reverse().map(row => `
        <tr>
          <td>${displayTime(row.generated_at)}</td>
          <td>${Number(row.total_equity || 0).toFixed(2)}</td>
          <td>${row.total_return_zh || '0.00%'}</td>
          <td>${displayStrategyId(row.strategy_id)}</td>
          <td>${displayValue(row.latest_trade_symbol)}</td>
          <td>${row.latest_trade_side_zh || displaySide(row.latest_trade_side)}</td>
          <td>${Number(row.latest_trade_commission || 0).toFixed(2)}</td>
          <td>${row.execution_model_zh || '未知执行模型'}</td>
          <td>${displayValue(row.trade_count)}</td>
        </tr>
      `).join('');
      document.getElementById('paperPerformance').innerHTML = `
        <div class="metric-grid">
          ${metric('记录次数', performance.run_count || 0)}
          ${metric('累计收益率', performance.total_return_zh || '0.00%')}
          ${metric('最新权益变化', performance.latest_change_zh || '0.00')}
          ${metric('最大回撤', performance.max_drawdown_zh || '0.00%')}
          ${metric('当前回撤', performance.current_drawdown_zh || '0.00%')}
          ${metric('累计佣金', Number(performance.latest_total_commission || 0).toFixed(2))}
          ${metric('执行模型', performance.latest_execution_model_zh || '未知执行模型')}
          ${metric('权益高水位', Number(performance.equity_high_watermark || 0).toFixed(2))}
        </div>
        <table><thead><tr><th>时间</th><th>总权益</th><th>累计收益率</th><th>策略</th><th>标的</th><th>方向</th><th>佣金</th><th>执行模型</th><th>交易次数</th></tr></thead><tbody>${rows || '<tr><td colspan="9" class="muted">暂无模拟绩效历史</td></tr>'}</tbody></table>
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
            <tr><th>备份时间</th><td>${displayTime(latestBackup.created_at)}</td></tr>
            <tr><th>安全边界</th><td>${displayValue(opsHealth.safety_boundary && opsHealth.safety_boundary.message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无健康检查结果</td></tr>'}</tbody></table>
      `;
    }
    function renderAppEntry(readiness) {
      const checks = readiness.checks || [];
      const bundles = readiness.bundle_reports || [];
      const rows = checks.map(check => {
        const kind = check.status === 'fail' ? 'danger' : (check.status === 'warn' ? 'warn' : 'ok');
        return `<tr><td>${check.title_zh || '未知检查'}</td><td>${pill(check.status_zh || displayStatus(check.status), kind)}</td><td>${check.message_zh || ''}</td></tr>`;
      }).join('');
      const bundleRows = bundles.map(bundle => {
        const kind = bundle.status === 'pass' ? 'ok' : 'danger';
        return `
          <tr>
            <td>${displayValue(bundle.path)}</td>
            <td>${pill(bundle.status_zh || displayStatus(bundle.status, '未知'), kind)}</td>
            <td>${displayBool(bundle.exists)}</td>
            <td>${displayBool(bundle.plist_valid)}</td>
            <td>${displayBool(bundle.applet_executable)}</td>
            <td>${bundle.fingerprint_matches_reference === null || bundle.fingerprint_matches_reference === undefined ? '仓库源包' : displayBool(bundle.fingerprint_matches_reference)}</td>
          </tr>
        `;
      }).join('');
      document.getElementById('appEntry').innerHTML = `
        <div class="metric-grid">
          ${metric('总体状态', pill(readiness.status_zh || displayStatus(readiness.status, '未知'), readiness.fail_count ? 'danger' : (readiness.warn_count ? 'warn' : 'ok')))}
          ${metric('通过', readiness.pass_count || 0)}
          ${metric('需关注', readiness.warn_count || 0)}
          ${metric('失败', readiness.fail_count || 0)}
        </div>
        <table>
          <tbody>
            <tr><th>生成时间</th><td>${displayTime(readiness.generated_at)}</td></tr>
            <tr><th>结论</th><td>${readiness.summary_zh || '无'}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无应用入口验收结果</td></tr>'}</tbody></table>
        <table><thead><tr><th>应用路径</th><th>状态</th><th>存在</th><th>plist 有效</th><th>可执行</th><th>文件指纹一致</th></tr></thead><tbody>${bundleRows || '<tr><td colspan="6" class="muted">暂无应用包记录</td></tr>'}</tbody></table>
      `;
    }
    function renderPaperReadiness(readiness) {
      const checks = readiness.checks || [];
      const rows = checks.map(check => {
        const kind = check.status === 'fail' ? 'danger' : (check.status === 'warn' ? 'warn' : 'ok');
        return `<tr><td>${check.title_zh || '未知检查'}</td><td>${pill(check.status_zh || displayStatus(check.status), kind)}</td><td>${check.message_zh || ''}</td></tr>`;
      }).join('');
      document.getElementById('paperReadiness').innerHTML = `
        <div class="metric-grid">
          ${metric('总体状态', pill(readiness.overall_status_zh || displayStatus(readiness.overall_status), readiness.fail_count ? 'danger' : (readiness.warn_count ? 'warn' : 'ok')))}
          ${metric('通过', readiness.pass_count || 0)}
          ${metric('需关注', readiness.warn_count || 0)}
          ${metric('失败', readiness.fail_count || 0)}
        </div>
        <table>
          <tbody>
            <tr><th>模拟交易交付日期</th><td>${readiness.deadline_zh || '2026年6月15日'}</td></tr>
            <tr><th>网页与本地应用交付日期</th><td>${readiness.dashboard_app_deadline_zh || '2026年6月17日'}</td></tr>
            <tr><th>结论</th><td>${readiness.summary_zh || '无'}</td></tr>
            <tr><th>安全边界</th><td>${displayValue(readiness.safety_boundary && readiness.safety_boundary.message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>交付项</th><th>状态</th><th>证据说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无就绪检查结果</td></tr>'}</tbody></table>
      `;
    }
    function renderSoakReadiness(readiness, history) {
      const checks = readiness.checks || [];
      const rows = checks.map(check => {
        const kind = check.status === 'fail' ? 'danger' : (check.status === 'warn' ? 'warn' : 'ok');
        return `<tr><td>${check.title_zh || '未知预检'}</td><td>${pill(check.status_zh || displayStatus(check.status), kind)}</td><td>${check.message_zh || ''}</td></tr>`;
      }).join('');
      const recentRows = ((history || {}).recent || []).slice(0, 8).map(row => `
        <tr>
          <td>${displayTime(row.generated_at)}</td>
          <td>${row.overall_status_zh || displayStatus(row.overall_status, '未知')}</td>
          <td>${row.pass_count || 0} / ${row.warn_count || 0} / ${row.fail_count || 0}</td>
          <td>${displayValue(row.latest_fresh_ticket_id)}</td>
          <td>${row.summary_zh || '无'}</td>
        </tr>
      `).join('');
      document.getElementById('soakReadiness').innerHTML = `
        <div class="metric-grid">
          ${metric('总体状态', pill(readiness.overall_status_zh || displayStatus(readiness.overall_status), readiness.fail_count ? 'danger' : (readiness.warn_count ? 'warn' : 'ok')))}
          ${metric('目标周期', readiness.target_days_zh || '30 天')}
          ${metric('通过', readiness.pass_count || 0)}
          ${metric('需关注', readiness.warn_count || 0)}
          ${metric('失败', readiness.fail_count || 0)}
          ${metric('历史采样数', (history || {}).run_count || 0)}
          ${metric('连续无失败采样', (history || {}).consecutive_no_fail_count || 0)}
          ${metric('连续完全通过采样', (history || {}).consecutive_healthy_count || 0)}
          ${metric('观察覆盖', (history || {}).target_coverage_zh || '0.00%')}
        </div>
        <table>
          <tbody>
            <tr><th>结论</th><td>${readiness.summary_zh || '无'}</td></tr>
            <tr><th>历史结论</th><td>${(history || {}).summary_zh || '尚无长运行采样历史'}</td></tr>
            <tr><th>历史文件</th><td>${displayValue((history || {}).path)}</td></tr>
            <tr><th>最近采样</th><td>${displayTime((history || {}).latest_generated_at)}</td></tr>
            <tr><th>最近失败时间</th><td>${displayTime((history || {}).last_failure_at, '无')}</td></tr>
            <tr><th>已覆盖天数</th><td>${(history || {}).observed_days_zh || '0.00 天'}</td></tr>
            <tr><th>安全边界</th><td>${displayValue(readiness.safety_boundary && readiness.safety_boundary.message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>预检项</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无长运行预检结果</td></tr>'}</tbody></table>
        <table><thead><tr><th>采样时间</th><th>状态</th><th>通过/关注/失败</th><th>有效工单</th><th>摘要</th></tr></thead><tbody>${recentRows || '<tr><td colspan="5" class="muted">暂无长运行采样历史</td></tr>'}</tbody></table>
      `;
    }
    function renderSoakHistory(history) {
      const recentRows = (history.recent || []).slice(0, 12).map(row => `
        <tr>
          <td>${displayTime(row.generated_at)}</td>
          <td>${row.overall_status_zh || displayStatus(row.overall_status, '未知')}</td>
          <td>${row.pass_count || 0} / ${row.warn_count || 0} / ${row.fail_count || 0}</td>
          <td>${displayValue(row.latest_fresh_ticket_id)}</td>
          <td>${row.ops_health_status_zh || '未知'}</td>
          <td>${row.paper_readiness_status_zh || '未知'}</td>
        </tr>
      `).join('');
      document.getElementById('soakHistory').innerHTML = `
        <div class="metric-grid">
          ${metric('采样次数', history.run_count || 0)}
          ${metric('连续无失败', history.consecutive_no_fail_count || 0)}
          ${metric('连续完全通过', history.consecutive_healthy_count || 0)}
          ${metric('已覆盖', history.observed_days_zh || '0.00 天')}
          ${metric('目标覆盖率', history.target_coverage_zh || '0.00%')}
          ${metric('完成状态', history.completion_status_zh || '尚未开始')}
        </div>
        <table>
          <tbody>
            <tr><th>历史文件</th><td>${displayValue(history.path)}</td></tr>
            <tr><th>首次采样</th><td>${displayTime(history.first_generated_at)}</td></tr>
            <tr><th>最近采样</th><td>${displayTime(history.latest_generated_at)}</td></tr>
            <tr><th>最近失败时间</th><td>${displayTime(history.last_failure_at, '无')}</td></tr>
            <tr><th>历史结论</th><td>${history.summary_zh || '尚无长运行采样历史'}</td></tr>
            <tr><th>安全边界</th><td>${displayValue(history.safety_boundary && history.safety_boundary.message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>采样时间</th><th>状态</th><th>通过/关注/失败</th><th>有效工单</th><th>运行健康</th><th>模拟交易交付</th></tr></thead><tbody>${recentRows || '<tr><td colspan="6" class="muted">暂无长运行采样历史</td></tr>'}</tbody></table>
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
            <tr><th>上次维护</th><td>${displayTime(opsMaintenance.last_run_completed_at)}</td></tr>
            <tr><th>下次维护</th><td>${displayTime(opsMaintenance.next_run_at)}</td></tr>
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
        ? (marketData.refresh_succeeded ? '刷新成功' : `刷新失败：${displayRefreshError(marketData.refresh_error_zh, marketData.refresh_error)}`)
        : '尚未尝试刷新';
      document.getElementById('marketData').innerHTML = `
        <table>
          <tbody>
            <tr><th>提供方</th><td>${marketData.provider_zh || displayMarketDataProvider(marketData.provider)}</td></tr>
            <tr><th>来源</th><td>${marketData.source_kind_zh || displayMarketDataSource(marketData.source_kind)}</td></tr>
            <tr><th>质量</th><td>${pill(marketData.data_quality_zh || displayDataQuality(marketData.data_quality), marketData.real_market_data ? 'ok' : 'warn')}</td></tr>
            <tr><th>真实市场数据</th><td>${marketData.real_market_data_zh || displayBool(marketData.real_market_data)}</td></tr>
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
            <tr><th>上次运行</th><td>${displayTime(loop.last_run_completed_at, '尚未运行')}</td></tr>
            <tr><th>下次运行</th><td>${displayTime(loop.next_run_at, '等待中')}</td></tr>
            <tr><th>最新候选单</th><td>${displayTime(agent.latest_ticket_created_at)}</td></tr>
            <tr><th>最新有效候选单</th><td>${displayTime(agent.latest_fresh_ticket_created_at)}</td></tr>
            <tr><th>过期候选单</th><td>${agent.expired_tickets || 0}</td></tr>
            <tr><th>最新结果</th><td>${displayValue(summary.intent_symbol)} / ${displayStrategyId(summary.intent_strategy_id)} / ${displayStatus(summary.ticket_status)} / ${displayStatus(summary.paper_order_status)} / ${displayStatus(summary.broker_paper_order_status)}</td></tr>
            <tr><th>最新模拟经纪商订单</th><td>${displayValue(summary.broker_paper_order_id)}</td></tr>
            <tr><th>错误</th><td>${loop.error_count || 0}${loop.last_error ? '：' + displayReason(loop.last_error) : ''}</td></tr>
            <tr><th>能力</th><td>${(agent.capabilities || []).map(displayCapability).join('，')}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderBroker(broker, externalSnapshot = {}) {
      const latest = broker.latest_trade || {};
      const externalAccount = externalSnapshot.account || {};
      const latestLine = latest.symbol ? `${latest.symbol} / ${displaySide(latest.side)} / 数量 ${displayValue(latest.quantity)} / 成交价 ${displayValue(latest.price)}` : '暂无';
      const latestCostLine = latest.symbol ? `佣金 ${Number(latest.commission || 0).toFixed(2)} / 滑点 ${Number(latest.slippage_bps || 0).toFixed(2)} 基点` : '暂无';
      document.getElementById('broker').innerHTML = `
        <table>
          <tbody>
            <tr><th>适配器</th><td>${broker.adapter_id_zh || displayAdapterId(broker.adapter_id)}</td></tr>
            <tr><th>纸面交易提供方</th><td>${broker.provider_zh || displayPaperBrokerProvider(broker.provider)}</td></tr>
            <tr><th>适配器就绪</th><td>${broker.adapter_readiness_zh || displayStatus(broker.adapter_readiness, '未知')}</td></tr>
            <tr><th>名称</th><td>${broker.broker_name_zh || displayBrokerName(broker.broker_name)}</td></tr>
            <tr><th>账户</th><td>${broker.account_ref_zh || displayAccount(broker.account_ref)}</td></tr>
            <tr><th>模式</th><td>${broker.mode_zh || displayStatus(broker.mode)}</td></tr>
            <tr><th>连接</th><td>${broker.connected_zh || displayBool(broker.connected)}</td></tr>
            <tr><th>需要凭据</th><td>${broker.credential_required_zh || displayBool(broker.credential_required)}</td></tr>
            <tr><th>允许纸面下单</th><td>${broker.paper_order_submission_enabled_zh || displayBool(broker.paper_order_submission_enabled)}</td></tr>
            <tr><th>外部纸面 API</th><td>${broker.external_paper_api_enabled_zh || displayBool(broker.external_paper_api_enabled)}</td></tr>
            <tr><th>外部账户同步</th><td>${externalSnapshot.status_zh || '未配置'}</td></tr>
            <tr><th>同步说明</th><td>${externalSnapshot.summary_zh || externalSnapshot.reason_zh || '无'}</td></tr>
            <tr><th>外部账户权益</th><td>${externalAccount.equity === null || externalAccount.equity === undefined ? '无' : Number(externalAccount.equity).toFixed(2)}</td></tr>
            <tr><th>外部持仓数</th><td>${externalSnapshot.position_count || 0}</td></tr>
            <tr><th>外部订单数</th><td>${externalSnapshot.recent_order_count || 0}</td></tr>
            <tr><th>外部同步时间</th><td>${displayTime(externalSnapshot.generated_at)}</td></tr>
            <tr><th>允许真实下单</th><td>${broker.live_order_submission_enabled_zh || displayBool(broker.live_order_submission_enabled)}</td></tr>
            <tr><th>未就绪原因</th><td>${broker.reason_zh || '无'}</td></tr>
            <tr><th>下一步</th><td>${broker.next_step_zh || '无'}</td></tr>
            <tr><th>执行模型</th><td>${broker.execution_model_zh || '未知执行模型'}</td></tr>
            <tr><th>模拟滑点</th><td>${Number(broker.slippage_bps || 0).toFixed(2)} 基点</td></tr>
            <tr><th>单笔佣金</th><td>${Number(broker.commission_per_order || 0).toFixed(2)}</td></tr>
            <tr><th>累计佣金</th><td>${Number(broker.total_commission || 0).toFixed(2)}</td></tr>
            <tr><th>交易次数</th><td>${broker.paper_trade_count || 0}</td></tr>
            <tr><th>最近模拟成交</th><td>${latestLine}</td></tr>
            <tr><th>最近成交成本</th><td>${latestCostLine}</td></tr>
          </tbody>
        </table>
      `;
    }
    function renderPaperBrokerReadiness(readiness) {
      const checks = readiness.checks || [];
      const status = readiness.paper_broker_status || {};
      const snapshot = readiness.external_snapshot_summary || {};
      const rows = checks.map(check => {
        const kind = check.status === 'fail' ? 'danger' : (check.status === 'warn' ? 'warn' : 'ok');
        return `<tr><td>${check.title_zh || '未知检查'}</td><td>${pill(check.status_zh || displayStatus(check.status), kind)}</td><td>${check.message_zh || ''}</td></tr>`;
      }).join('');
      document.getElementById('paperBrokerReadiness').innerHTML = `
        <div class="metric-grid">
          ${metric('总体状态', pill(readiness.overall_status_zh || displayStatus(readiness.overall_status, '未知'), readiness.fail_count ? 'danger' : (readiness.warn_count ? 'warn' : 'ok')))}
          ${metric('当前提供方', readiness.provider_zh || '未知')}
          ${metric('本地沙盒可用', readiness.local_sandbox_ready_zh || '否')}
          ${metric('外部纸面账户端到端验证', readiness.external_paper_e2e_ready_zh || '否')}
          ${metric('通过', readiness.pass_count || 0)}
          ${metric('需关注', readiness.warn_count || 0)}
          ${metric('失败', readiness.fail_count || 0)}
        </div>
        <table>
          <tbody>
            <tr><th>结论</th><td>${readiness.summary_zh || '无'}</td></tr>
            <tr><th>适配器就绪</th><td>${status.adapter_readiness_zh || displayStatus(status.adapter_readiness, '未知')}</td></tr>
            <tr><th>允许纸面下单</th><td>${status.paper_order_submission_enabled_zh || displayBool(status.paper_order_submission_enabled)}</td></tr>
            <tr><th>外部账户同步</th><td>${snapshot.status_zh || '未配置'}</td></tr>
            <tr><th>外部持仓数</th><td>${snapshot.position_count || 0}</td></tr>
            <tr><th>外部最近订单数</th><td>${snapshot.recent_order_count || 0}</td></tr>
            <tr><th>允许真实下单</th><td>${displayBool((readiness.safety_boundary || {}).live_order_submission_enabled)}</td></tr>
            <tr><th>安全边界</th><td>${displayValue((readiness.safety_boundary || {}).message_zh)}</td></tr>
          </tbody>
        </table>
        <table><thead><tr><th>检查项</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">暂无纸面交易提供方预检结果</td></tr>'}</tbody></table>
      `;
    }
    function renderMoomooBroker(status, quoteSnapshot) {
      const packageInfo = status.package || {};
      const connection = status.opend_connection || {};
      const kind = status.read_only_ready ? 'ok' : 'warn';
      const quotes = quoteSnapshot.quotes || [];
      const quoteRows = quotes.map(quote => `<tr><td>${displayValue(quote.code)}</td><td>${displayValue(quote.name)}</td><td>${displayValue(quote.last_price)}</td><td>${displayValue(quote.update_time)}</td></tr>`).join('');
      const quoteKind = quoteSnapshot.status === 'ready' ? 'ok' : 'warn';
      document.getElementById('moomooBroker').innerHTML = `
        <table>
          <tbody>
            <tr><th>连接模式</th><td>${status.mode_zh || displayStatus(status.mode, '未知')}</td></tr>
            <tr><th>探测结果</th><td>${pill(status.status_zh || displayStatus(status.status, '未知'), kind)}</td></tr>
            <tr><th>说明</th><td>${status.message_zh || '暂无说明'}</td></tr>
            <tr><th>下一步</th><td>${status.next_step_zh || '暂无'}</td></tr>
            <tr><th>开放网关地址</th><td>${displayValue(status.host)}:${displayValue(status.port)}</td></tr>
            <tr><th>开放网关连接</th><td>${status.opend_connected_zh || displayBool(status.opend_connected)}</td></tr>
            <tr><th>接口包</th><td>${status.package_installed_zh || displayBool(status.package_installed)} / ${displayValue(packageInfo.import_name, '未发现')} / ${displayValue(packageInfo.version, '未知版本')}</td></tr>
            <tr><th>软件开发包可导入</th><td>${status.package_importable_zh || displayBool(status.package_importable)}</td></tr>
            <tr><th>只读就绪</th><td>${status.read_only_ready_zh || displayBool(status.read_only_ready)}</td></tr>
            <tr><th>探测需凭据</th><td>${status.credential_required_for_probe_zh || displayBool(status.credential_required_for_probe)}</td></tr>
            <tr><th>交易解锁</th><td>${status.trade_unlock_required_zh || displayBool(status.trade_unlock_required)}</td></tr>
            <tr><th>允许真实下单</th><td>${status.live_order_submission_enabled_zh || displayBool(status.live_order_submission_enabled)}</td></tr>
            <tr><th>安全操作</th><td>${(status.safe_operations_zh || []).join('，') || '无'}</td></tr>
            <tr><th>禁止操作</th><td>${(status.forbidden_operations_zh || []).join('，') || '无'}</td></tr>
            <tr><th>连接错误</th><td>${connection.error_zh || '无'}</td></tr>
          </tbody>
        </table>
        <table>
          <thead><tr><th colspan="4">只读行情快照 ${pill(quoteSnapshot.status_zh || displayStatus(quoteSnapshot.status, '未知'), quoteKind)}</th></tr></thead>
          <tbody>${quoteRows || `<tr><td colspan="4">${quoteSnapshot.message_zh || '暂无行情快照'}</td></tr>`}</tbody>
        </table>
      `;
    }
    function renderTournament(tournament) {
      const rows = (tournament.candidates || []).slice(0, 8).map(row => `
        <tr>
          <td>${row.strategy_id_zh || displayStrategyId(row.strategy_id)}</td><td>${row.symbol}</td><td>${row.signal_type_zh || displaySignalType(row.signal_type)}</td><td>${row.lookback_days}</td>
          <td>${Number((row.total_return || 0) * 100).toFixed(2)}%</td><td>${Number((row.oos_return || 0) * 100).toFixed(2)}%</td>
          <td>${Number((row.hit_rate || 0) * 100).toFixed(2)}%</td><td>${row.validation_windows || 0}</td>
          <td>${Number((row.max_drawdown || 0) * 100).toFixed(2)}%</td><td>${Number(row.score || 0).toFixed(4)}</td><td>${row.decision_zh || displayStatus(row.decision)}</td>
        </tr>`).join('');
      document.getElementById('tournament').innerHTML = `
        <div class="status">当前胜出：${displayStrategyId(tournament.winner && tournament.winner.strategy_id)}</div>
        <table><thead><tr><th>策略</th><th>标的</th><th>信号</th><th>回看天数</th><th>收益</th><th>样本外收益</th><th>命中率</th><th>验证窗口</th><th>回撤</th><th>分数</th><th>决策</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }
    function renderStrategyJournal(journal) {
      const rows = (journal.recent || []).slice(-8).reverse().map(row => `
        <tr>
          <td>${displayTime(row.generated_at)}</td>
          <td>${row.winner_strategy_id_zh || displayStrategyId(row.winner_strategy_id)}</td>
          <td>${displayValue(row.winner_symbol)}</td>
          <td>${Number((row.winner_oos_return || 0) * 100).toFixed(2)}%</td>
          <td>${Number((row.winner_hit_rate || 0) * 100).toFixed(2)}%</td>
          <td>${row.winner_decision_zh || displayStatus(row.winner_decision, '未知')}</td>
          <td>${row.market_data_quality_zh || displayDataQuality(row.market_data_quality)}</td>
        </tr>
      `).join('');
      return `
        <h2>策略迭代历史</h2>
        <div class="metric-grid">
          ${metric('记录次数', journal.run_count || 0)}
          ${metric('最近胜出策略', journal.latest_winner_strategy_id_zh || displayStrategyId(journal.latest_winner_strategy_id))}
          ${metric('连续胜出次数', journal.current_winner_streak || 0)}
          ${metric('最近稳定度', journal.stability_ratio_zh || '0.00%')}
        </div>
        <table><thead><tr><th>时间</th><th>胜出策略</th><th>标的</th><th>样本外收益</th><th>命中率</th><th>决策</th><th>行情质量</th></tr></thead><tbody>${rows || '<tr><td colspan="7" class="muted">暂无策略迭代历史</td></tr>'}</tbody></table>
      `;
    }
    function renderQueue(queue) {
      const storage = queue.storage || {};
      const rows = (queue.tickets || []).map(ticket => {
        const payload = ticket.broker_payload || {};
        const risk = ticket.risk_check || {};
        return `<tr>
          <td>${ticket.ticket_id}</td><td>${ticket.actionability_zh || ticket.status_zh || displayStatus(ticket.actionability || ticket.status)}</td><td>${payload.symbol || ''}</td>
          <td>${payload.side_zh || displaySide(payload.side)}</td><td>${payload.quantity || ''}</td>
          <td>${payload.estimated_price || ''}<br><span class="muted">${displayOrderType(payload.order_type)} / ${displayTimeInForce(payload.time_in_force)}</span></td>
          <td>${risk.status_zh || displayStatus(risk.status, '未知')}<br><span class="muted">${risk.reason_zh || displayReason(risk.reason)}</span></td>
          <td>${(ticket.freshness && ticket.freshness.status_zh) || displayStatus(ticket.freshness && ticket.freshness.status, '未知')}</td>
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
        return `<button class="secondary" onclick="ticketAction('${ticketId}', 'mark-exported')">标记已导出</button> <button class="secondary" onclick="openBrokerTicket('${ticketId}')">查看工单</button> <button class="secondary" onclick="downloadBrokerTicketCsv('${ticketId}')">下载工单表格</button> <button class="secondary" onclick="ticketAction('${ticketId}', 'reject')">拒绝</button>`;
      }
      if (ticket.status === 'broker_ticket_exported') {
        return `<button class="secondary" onclick="openBrokerTicket('${ticketId}')">查看工单</button> <button class="secondary" onclick="downloadBrokerTicketCsv('${ticketId}')">下载工单表格</button>`;
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
        renderPaperPerformance(data.paper_performance || {});
        renderAgent(data.agent_status || {});
        renderBroker(data.paper_broker_status || {}, data.paper_broker_external_snapshot || {});
        renderPaperBrokerReadiness(data.paper_broker_readiness || {});
        renderMoomooBroker(data.moomoo_broker_status || {}, data.moomoo_quote_snapshot || {});
        renderMarketData(data.market_data || {});
        renderOpsHealth(data.ops_health || {});
        renderAppEntry(data.app_entry_readiness || {});
        renderPaperReadiness(data.paper_readiness || {});
        renderSoakReadiness(data.soak_readiness || {}, data.soak_readiness_history || {});
        renderSoakHistory(data.soak_readiness_history || {});
        document.getElementById('opsHealth').insertAdjacentHTML('beforeend', renderOpsMaintenance(data.ops_maintenance || {}));
        renderTournament(data.strategy_tournament || {});
        document.getElementById('tournament').insertAdjacentHTML('beforeend', renderStrategyJournal(data.strategy_journal || {}));
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
    function openBrokerTicket(ticketId) {
      window.open(`/orders/approval-queue/${encodeURIComponent(ticketId)}/broker-ticket/view`, '_blank', 'noopener');
    }
    function downloadBrokerTicketCsv(ticketId) {
      window.open(`/orders/approval-queue/${encodeURIComponent(ticketId)}/broker-ticket.csv`, '_blank', 'noopener');
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
