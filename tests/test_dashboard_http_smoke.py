from scripts.verify_dashboard_http_smoke import validate_dashboard_payloads, validate_safe_action_results


def test_dashboard_http_smoke_validation_accepts_chinese_safe_payloads():
    errors = validate_dashboard_payloads(
        health={"status": "ok", "status_zh": "正常", "live_trading_enabled": False, "refresh_interval_seconds": 300},
        dashboard_html=(
            "Alpha 控制台 运行模拟交易周期 生成运行备份 刷新公共行情 系统快照 长运行预检 长运行历史 "
            "审批队列 富途牛牛开放网关（只读） /dashboard/state /paper/run-once /ops/backup "
            "/market-data/refresh /orders/approval-queue/ owner-review reject mark-exported "
            "/broker-ticket/view /broker-ticket.csv"
        ),
        state={
            "health": {"status_zh": "正常"},
            "market_data": {"source_kind_zh": "本地行情缓存"},
            "paper_broker_status": {
                "mode_zh": "模拟交易",
                "live_order_submission_enabled": False,
                "live_order_submission_enabled_zh": "否",
                "supports_real_broker_place_order": False,
            },
            "moomoo_broker_status": {
                "mode_zh": "只读连接探测",
                "live_order_submission_enabled": False,
                "trade_context_enabled": False,
                "supports_real_broker_place_order": False,
            },
            "soak_readiness": {"summary_zh": "可观察运行"},
            "soak_readiness_history": {
                "summary_zh": "连续无失败采样 1 次",
                "safety_boundary": {"live_order_submission_enabled": False},
            },
            "owner_summary": {"message_zh": "当前有 1 张有效候选单需要人工复核。"},
        },
    )

    assert errors == []


def test_dashboard_http_smoke_validation_rejects_english_and_live_order_paths():
    errors = validate_dashboard_payloads(
        health={"status": "ok", "status_zh": "正常", "live_trading_enabled": False, "refresh_interval_seconds": 300},
        dashboard_html="Alpha Dashboard Alpha 控制台",
        state={
            "health": {"status_zh": "正常"},
            "market_data": {"source_kind_zh": "本地行情缓存"},
            "paper_broker_status": {
                "mode_zh": "模拟交易",
                "live_order_submission_enabled": True,
                "live_order_submission_enabled_zh": "是",
                "supports_real_broker_place_order": False,
            },
            "moomoo_broker_status": {
                "mode_zh": "只读连接探测",
                "live_order_submission_enabled": False,
                "trade_context_enabled": False,
                "supports_real_broker_place_order": False,
            },
            "soak_readiness": {"summary_zh": "可观察运行"},
            "soak_readiness_history": {
                "summary_zh": "连续无失败采样 1 次",
                "safety_boundary": {"live_order_submission_enabled": False},
            },
            "owner_summary": {"message_zh": "当前有 1 张有效候选单需要人工复核。"},
        },
    )

    assert any("旧英文文案" in error for error in errors)
    assert any("模拟经纪商状态没有明确禁用真实下单" in error for error in errors)


def test_dashboard_http_smoke_validation_accepts_safe_action_results():
    errors = validate_safe_action_results(
        {
            "paper_run_once": {
                "status": "completed",
                "paper_broker_adapter": {"live_order_submission_enabled": False},
                "approval_queue": {"ticket": {"status": "pending_owner_approval", "status_zh": "待人工确认"}},
            },
            "ops_backup": {
                "status": "completed",
                "backup_path": "runtime/backups/backup.json",
                "health_after_backup": {"safety_boundary": {"live_order_submission_enabled": False}},
            },
        }
    )

    assert errors == []


def test_dashboard_http_smoke_validation_rejects_unsafe_action_results():
    errors = validate_safe_action_results(
        {
            "paper_run_once": {
                "status": "completed",
                "paper_broker_adapter": {"live_order_submission_enabled": True},
                "approval_queue": {"ticket": {"status": "queued"}},
            },
            "ops_backup": {"status": "failed", "health_after_backup": {"safety_boundary": {"live_order_submission_enabled": True}}},
        }
    )

    assert any("模拟交易周期动作没有明确禁用真实下单" in error for error in errors)
    assert any("运行备份动作未返回 completed" in error for error in errors)
