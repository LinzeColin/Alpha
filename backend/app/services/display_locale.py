from __future__ import annotations


STATUS_TEXT_ZH = {
    "ok": "正常",
    "ready": "就绪",
    "starting": "正在启动",
    "sleeping": "等待下次运行",
    "running_cycle": "正在运行周期",
    "error_sleeping": "错误后等待",
    "stopped": "已停止",
    "completed": "已完成",
    "queued": "已入队",
    "duplicate": "重复候选单",
    "skipped": "已跳过",
    "written": "已写入",
    "empty": "暂无记录",
    "filled": "模拟成交",
    "pending_owner_approval": "待人工确认",
    "fresh_pending_owner_approval": "有效，待人工确认",
    "expired_owner_approval": "已过期，需重新生成",
    "blocked_by_risk": "风控阻止",
    "approved_for_owner_review": "已通过风控，待人工确认",
    "promote_to_paper": "可进入模拟交易",
    "hold_research": "继续研究观察",
    "reject": "拒绝",
    "rejected": "已拒绝",
    "owner_reviewed": "已人工复核",
    "owner_rejected": "已拒绝",
    "broker_ticket_exported": "工单已导出",
    "paper": "模拟交易",
    "fresh": "有效",
    "expired": "已过期",
    "invalid": "无效",
    "not_found": "未找到",
    "blocked": "已阻止",
    "unchanged": "未变化",
    "updated": "已更新",
    "healthy": "健康",
    "degraded": "需关注",
    "unhealthy": "不可用",
    "pass": "通过",
    "warn": "需关注",
    "fail": "失败",
    "pruned": "已轮转",
    "running_maintenance": "正在维护",
    "maintenance_sleeping": "等待下次维护",
    "maintenance_error_sleeping": "维护错误后等待",
    "unknown": "未知",
}

CAPABILITY_TEXT_ZH = {
    "paper_trading": "全自动模拟交易",
    "risk_check": "自动风控检查",
    "approval_queue": "自动进入审批队列",
    "broker_ready_order_ticket": "经纪商就绪订单工单",
    "broker_paper_adapter": "模拟交易执行适配器",
}

SIDE_TEXT_ZH = {
    "buy": "买入",
    "sell": "卖出",
}

ORDER_TYPE_TEXT_ZH = {
    "market": "市价单",
}

TIME_IN_FORCE_TEXT_ZH = {
    "day": "当日有效",
}

STORAGE_BACKEND_TEXT_ZH = {
    "sqlite": "SQLite 数据库",
    "json": "JSON 文件",
    "memory": "内存",
}

MARKET_DATA_PROVIDER_TEXT_ZH = {
    "cache_or_fixture": "本地缓存优先",
    "stooq": "Stooq 公共延迟行情",
    "direct_file": "直接文件",
}

MARKET_DATA_SOURCE_TEXT_ZH = {
    "public_cache": "公共延迟行情缓存",
    "local_cache": "本地行情缓存",
    "fixture": "样例数据",
    "local_file": "本地文件",
}

DATA_QUALITY_TEXT_ZH = {
    "fresh": "新鲜",
    "stale": "过期",
    "sample": "样例",
    "missing": "缺失",
}

AGENT_ID_TEXT_ZH = {
    "paper_trading_loop": "模拟交易循环智能体",
}

ADAPTER_ID_TEXT_ZH = {
    "local_sandbox_paper_broker": "本地沙盒模拟经纪商适配器",
}

BROKER_NAME_TEXT_ZH = {
    "Alpha Local Sandbox": "Alpha 本地沙盒",
}

ACCOUNT_REF_TEXT_ZH = {
    "local_paper_account": "本地模拟账户",
}

REASON_TEXT_ZH = {
    "pre-trade risk checks passed": "下单前风控检查通过",
    "kill switch active": "总开关已触发",
    "missing idempotency key": "缺少幂等键",
    "invalid side": "方向无效",
    "invalid quantity, price, or notional": "数量、价格或名义金额无效",
    "max order value not configured": "最大订单金额未配置",
    "max order value exceeded": "超过最大订单金额",
    "live trading disabled by policy": "策略已禁用真实资金交易",
    "audit sink unavailable": "审计写入不可用",
    "broker health check failed": "经纪商健康检查失败",
    "policy checks passed": "策略检查通过",
    "FailClosedLiveBroker never submits real orders": "失败即关闭真实经纪商适配器不会提交真实订单",
    "ticket_not_found": "未找到工单",
    "ticket_transition_blocked": "工单状态流转被阻止",
    "ticket_must_be_owner_reviewed_before_export": "导出前必须先完成所有者复核",
    "risk_blocked_ticket_cannot_be_owner_reviewed_or_exported": "风控阻止的工单不能复核或导出",
    "expired_ticket_cannot_be_owner_reviewed_or_exported": "工单已过期，不能复核或导出",
    "rejected_ticket_cannot_be_reopened_or_exported": "已拒绝工单不能重新打开或导出",
    "exported_ticket_cannot_transition_except_rejection": "已导出工单只能转为拒绝状态",
    "ticket_already_in_requested_state": "工单已处于目标状态",
}

WARNING_TEXT_ZH = {
    "max_drawdown_above_10pct": "最大回撤超过 10%",
    "low_trade_count": "交易次数偏少",
    "high_turnover": "换手率偏高",
}


def zh_status(value: object, fallback: str = "未知") -> str:
    if value is None or value == "":
        return fallback
    return STATUS_TEXT_ZH.get(str(value), "未知状态")


def zh_capability(value: object) -> str:
    if value is None or value == "":
        return "未知能力"
    return CAPABILITY_TEXT_ZH.get(str(value), "未知能力")


def zh_side(value: object) -> str:
    if value is None or value == "":
        return "未知方向"
    return SIDE_TEXT_ZH.get(str(value), "未知方向")


def zh_order_type(value: object) -> str:
    if value is None or value == "":
        return "未知订单类型"
    return ORDER_TYPE_TEXT_ZH.get(str(value), "未知订单类型")


def zh_time_in_force(value: object) -> str:
    if value is None or value == "":
        return "未知有效期"
    return TIME_IN_FORCE_TEXT_ZH.get(str(value), "未知有效期")


def zh_storage_backend(value: object) -> str:
    if value is None or value == "":
        return "未知存储"
    return STORAGE_BACKEND_TEXT_ZH.get(str(value), "未知存储")


def zh_market_data_provider(value: object) -> str:
    if value is None or value == "":
        return "未知行情源"
    return MARKET_DATA_PROVIDER_TEXT_ZH.get(str(value), "未知行情源")


def zh_market_data_source(value: object) -> str:
    if value is None or value == "":
        return "未知数据源"
    return MARKET_DATA_SOURCE_TEXT_ZH.get(str(value), "未知数据源")


def zh_data_quality(value: object) -> str:
    if value is None or value == "":
        return "未知质量"
    return DATA_QUALITY_TEXT_ZH.get(str(value), "未知质量")


def zh_agent_id(value: object) -> str:
    if value is None or value == "":
        return "未知智能体"
    return AGENT_ID_TEXT_ZH.get(str(value), "未知智能体")


def zh_adapter_id(value: object) -> str:
    if value is None or value == "":
        return "未知适配器"
    return ADAPTER_ID_TEXT_ZH.get(str(value), "未知适配器")


def zh_broker_name(value: object) -> str:
    if value is None or value == "":
        return "未知执行层"
    return BROKER_NAME_TEXT_ZH.get(str(value), str(value))


def zh_account_ref(value: object) -> str:
    if value is None or value == "":
        return "未知账户"
    return ACCOUNT_REF_TEXT_ZH.get(str(value), "本地账户")


def zh_reason(value: object) -> str:
    if value is None or value == "":
        return "无"
    return REASON_TEXT_ZH.get(str(value), "未知原因")


def zh_warning(value: object) -> str:
    if value is None or value == "":
        return "无"
    return WARNING_TEXT_ZH.get(str(value), "未知警告")


def zh_strategy_id(value: object) -> str:
    if value is None or value == "":
        return "无"
    raw = str(value)
    parts = raw.split("_")
    if len(parts) == 3 and parts[0] == "momentum" and parts[2].endswith("d"):
        return f"动量策略 {parts[1]} {parts[2][:-1]}日"
    if raw.startswith("fixture_momentum_"):
        return f"样例动量策略 {raw.removeprefix('fixture_momentum_')}"
    return raw


def format_paper_cycle_summary_zh(result: dict) -> str:
    intent = result.get("intent", {}) or {}
    risk = result.get("risk_check", {}) or {}
    approval = result.get("approval_queue", {}) or {}
    ticket = approval.get("ticket", {}) or {}
    paper_order = result.get("paper_order", {}) or {}
    broker_order = result.get("broker_paper_order", {}) or {}
    portfolio = result.get("paper_portfolio", {}) or {}
    adapter = result.get("paper_broker_adapter", {}) or {}
    market_data = result.get("market_data", {}) or {}
    strategy_journal = result.get("strategy_journal", {}) or {}
    latest_strategy_record = strategy_journal.get("latest_record", {}) or {}
    paper_performance = result.get("paper_performance", {}) or {}
    performance_summary = paper_performance.get("summary", {}) or paper_performance

    lines = [
        "Alpha 模拟交易周期摘要",
        f"运行编号：{result.get('run_id', '无')}",
        f"状态：{zh_status(result.get('status'))}",
        f"生成时间：{result.get('generated_at', '无')}",
        f"刷新间隔：{result.get('refresh_interval_seconds', 0)} 秒",
        (
            "候选订单："
            f"{intent.get('symbol', '无')} / {zh_side(intent.get('side'))} / "
            f"{intent.get('quantity', 0)} @ {intent.get('estimated_price', 0)} / "
            f"{zh_order_type(intent.get('order_type'))} / {zh_time_in_force(intent.get('time_in_force'))}"
        ),
        f"策略：{zh_strategy_id(intent.get('strategy_id'))}",
        (
            "策略迭代："
            f"{zh_status(strategy_journal.get('status'))} / "
            f"胜出策略 {zh_strategy_id(latest_strategy_record.get('winner_strategy_id') or strategy_journal.get('latest_winner_strategy_id'))}"
        ),
        (
            "行情数据："
            f"{zh_market_data_provider(market_data.get('provider'))} / "
            f"{zh_market_data_source(market_data.get('source_kind'))} / "
            f"质量 {zh_data_quality(market_data.get('data_quality'))} / "
            f"真实市场数据 {'是' if market_data.get('real_market_data') else '否'} / "
            f"最新日期 {market_data.get('latest_date') or '无'}"
        ),
        f"风控：{zh_status(risk.get('status'))}（{zh_reason(risk.get('reason'))}）",
        (
            "审批队列："
            f"{zh_status(approval.get('status'))} / {zh_status(ticket.get('status'))} / "
            f"工单 {ticket.get('ticket_id', '无')}"
        ),
        (
            "模拟成交："
            f"{zh_status(paper_order.get('status'))} / "
            f"模拟经纪商订单 {broker_order.get('broker_order_id') or '无'}"
        ),
        (
            "模拟组合："
            f"总权益 {portfolio.get('total_equity', 0)} / "
            f"现金 {portfolio.get('cash', 0)} / "
            f"交易次数 {portfolio.get('trade_count', 0)}"
        ),
        (
            "模拟绩效："
            f"累计收益 {performance_summary.get('total_return_zh', '0.00%')} / "
            f"最新权益变化 {performance_summary.get('latest_change_zh', '0.00')} / "
            f"当前回撤 {performance_summary.get('current_drawdown_zh', '0.00%')} / "
            f"最大回撤 {performance_summary.get('max_drawdown_zh', '0.00%')} / "
            f"累计佣金 {performance_summary.get('latest_total_commission', 0)}"
        ),
        (
            "执行层："
            f"{zh_adapter_id(adapter.get('adapter_id'))} / "
            f"模式 {zh_status(adapter.get('mode'))} / "
            f"模型 {adapter.get('execution_model_zh', '未知执行模型')} / "
            f"滑点 {float(adapter.get('slippage_bps') or 0):.2f} bps / "
            f"单笔佣金 {float(adapter.get('commission_per_order') or 0):.2f} / "
            f"允许真实下单 {'是' if adapter.get('live_order_submission_enabled') else '否'}"
        ),
        "安全边界：本周期只执行模拟交易并生成待人工确认工单，不会提交真实资金订单。",
    ]
    return "\n".join(lines)
