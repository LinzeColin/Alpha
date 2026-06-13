from backend.app.services.moomoo_broker_probe import (
    MoomooOpenDProbeConfig,
    MoomooQuoteSnapshotConfig,
    probe_moomoo_opend,
    probe_moomoo_quote_snapshot,
)


def _config() -> MoomooOpenDProbeConfig:
    return MoomooOpenDProbeConfig(host="127.0.0.1", port=11111, timeout_seconds=0.01)


def test_moomoo_probe_reports_not_configured_without_package_or_opend():
    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": False,
            "import_name": None,
            "distribution_name": None,
            "version": None,
            "message_zh": "当前 Python 环境未发现可导入的富途牛牛接口包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": False, "error": "ConnectionRefusedError", "error_zh": "本机开放网关端口拒绝连接。"},
    )

    assert status["status"] == "not_configured"
    assert status["status_zh"] == "未就绪"
    assert status["next_step_zh"] == "下一步：安装富途牛牛开放接口 Python 包并启动本机开放网关。"
    assert status["mode_zh"] == "只读连接探测"
    assert status["package_available"] is False
    assert status["opend_connected"] is False
    assert status["read_only_ready"] is False
    assert status["credential_required_for_probe"] is False
    assert status["trade_unlock_required"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["supports_real_broker_place_order"] is False
    assert "提交真实资金订单" in status["forbidden_operations_zh"]


def test_moomoo_probe_reports_api_missing_when_opend_port_is_reachable():
    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": False,
            "import_name": None,
            "distribution_name": None,
            "version": None,
            "message_zh": "当前 Python 环境未发现可导入的富途牛牛接口包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": True, "error": None, "error_zh": None},
    )

    assert status["status"] == "api_missing"
    assert status["status_zh"] == "接口包未安装"
    assert status["next_step_zh"] == "下一步：在项目虚拟环境中安装富途牛牛开放接口 Python 包后重新探测。"
    assert status["opend_connected_zh"] == "是"
    assert status["read_only_ready_zh"] == "否"
    assert status["live_order_submission_enabled_zh"] == "否"


def test_moomoo_probe_reports_api_import_error_when_package_cannot_import():
    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": False,
            "installed": True,
            "importable": False,
            "import_name": "moomoo",
            "distribution_name": "moomoo-api",
            "version": "10.7.6708",
            "import_error": "PermissionError",
            "import_error_zh": "运行环境没有权限访问富途牛牛软件开发包日志目录或本机端口。",
            "message_zh": "当前 Python 环境已安装富途牛牛接口包，但导入失败。",
        },
        connection_probe=lambda host, port, timeout: {"connected": True, "error": None, "error_zh": None},
    )

    assert status["status"] == "api_import_error"
    assert status["status_zh"] == "接口包导入失败"
    assert status["package_installed"] is True
    assert status["package_importable"] is False
    assert status["read_only_ready"] is False
    assert status["live_order_submission_enabled"] is False


def test_moomoo_probe_reports_ready_read_only_when_package_and_opend_are_available():
    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": True,
            "import_name": "moomoo",
            "distribution_name": "moomoo-api",
            "version": "1.0.0",
            "message_zh": "当前 Python 环境可导入富途牛牛接口包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": True, "error": None, "error_zh": None},
    )

    assert status["status"] == "ready_read_only"
    assert status["status_zh"] == "只读探测就绪"
    assert status["next_step_zh"] == "下一步：只接入只读行情和账户状态探测，继续保持真实下单禁用。"
    assert status["read_only_ready"] is True
    assert status["read_only_ready_zh"] == "是"
    assert status["package"]["import_name"] == "moomoo"
    assert status["message_zh"].startswith("富途牛牛接口包和本机开放网关端口均可用")
    assert status["trade_context_enabled"] is False
    assert status["live_order_submission_enabled"] is False


def test_moomoo_quote_snapshot_blocks_until_read_only_probe_is_ready():
    snapshot = probe_moomoo_quote_snapshot(
        MoomooQuoteSnapshotConfig(host="127.0.0.1", port=11111, timeout_seconds=0.01, symbols=("US.SPY",)),
        readiness_probe=lambda: {"status": "opend_unreachable", "status_zh": "开放网关未连接", "read_only_ready": False},
    )

    assert snapshot["status"] == "blocked"
    assert snapshot["status_zh"] == "未执行"
    assert snapshot["row_count"] == 0
    assert snapshot["trade_context_enabled"] is False
    assert snapshot["live_order_submission_enabled"] is False


def test_moomoo_quote_snapshot_returns_read_only_market_snapshot():
    snapshot = probe_moomoo_quote_snapshot(
        MoomooQuoteSnapshotConfig(host="127.0.0.1", port=11111, timeout_seconds=0.01, symbols=("US.SPY",)),
        readiness_probe=lambda: {"status": "ready_read_only", "status_zh": "只读探测就绪", "read_only_ready": True},
        quote_fetcher=lambda config: {
            "status": "ready",
            "message_zh": "已通过富途牛牛开放网关只读行情连接获取 1 条市场快照。",
            "quotes": [{"code": "US.SPY", "name": "SPDR S&P 500 ETF", "last_price": 741.75}],
            "row_count": 1,
        },
    )

    assert snapshot["status"] == "ready"
    assert snapshot["status_zh"] == "已获取"
    assert snapshot["row_count"] == 1
    assert snapshot["quotes"][0]["code"] == "US.SPY"
    assert snapshot["trade_context_enabled"] is False
    assert snapshot["live_order_submission_enabled"] is False
    assert "创建交易上下文" in snapshot["forbidden_operations_zh"]


def test_moomoo_probe_fails_closed_on_probe_exception():
    def broken_connection(host, port, timeout):
        raise RuntimeError("boom")

    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": True,
            "import_name": "moomoo",
            "distribution_name": "moomoo-api",
            "version": "1.0.0",
            "message_zh": "当前 Python 环境可导入富途牛牛接口包。",
        },
        connection_probe=broken_connection,
    )

    assert status["status"] == "probe_error"
    assert status["status_zh"] == "探测异常"
    assert status["next_step_zh"] == "下一步：查看探测异常和本机开放网关状态；修复前保持只读和真实下单禁用。"
    assert status["read_only_ready"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["supports_real_broker_place_order"] is False
