from backend.app.services.moomoo_broker_probe import MoomooOpenDProbeConfig, probe_moomoo_opend


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
            "message_zh": "当前 Python 环境未发现可导入的 moomoo 或 futu API 包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": False, "error": "ConnectionRefusedError", "error_zh": "本机 OpenD 端口拒绝连接。"},
    )

    assert status["status"] == "not_configured"
    assert status["status_zh"] == "未就绪"
    assert status["next_step_zh"] == "下一步：安装 Moomoo/Futu OpenAPI Python 包并启动本机 OpenD。"
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
            "message_zh": "当前 Python 环境未发现可导入的 moomoo 或 futu API 包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": True, "error": None, "error_zh": None},
    )

    assert status["status"] == "api_missing"
    assert status["status_zh"] == "API 包未安装"
    assert status["next_step_zh"] == "下一步：在项目虚拟环境中安装 Moomoo/Futu OpenAPI Python 包后重新探测。"
    assert status["opend_connected_zh"] == "是"
    assert status["read_only_ready_zh"] == "否"
    assert status["live_order_submission_enabled_zh"] == "否"


def test_moomoo_probe_reports_ready_read_only_when_package_and_opend_are_available():
    status = probe_moomoo_opend(
        _config(),
        package_detector=lambda: {
            "available": True,
            "import_name": "moomoo",
            "distribution_name": "moomoo-api",
            "version": "1.0.0",
            "message_zh": "当前 Python 环境可导入 Moomoo API 包。",
        },
        connection_probe=lambda host, port, timeout: {"connected": True, "error": None, "error_zh": None},
    )

    assert status["status"] == "ready_read_only"
    assert status["status_zh"] == "只读探测就绪"
    assert status["next_step_zh"] == "下一步：只接入只读行情和账户状态探测，继续保持真实下单禁用。"
    assert status["read_only_ready"] is True
    assert status["read_only_ready_zh"] == "是"
    assert status["package"]["import_name"] == "moomoo"
    assert status["message_zh"].startswith("Moomoo API 包和本机 OpenD 端口均可用")
    assert status["trade_context_enabled"] is False
    assert status["live_order_submission_enabled"] is False


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
            "message_zh": "当前 Python 环境可导入 Moomoo API 包。",
        },
        connection_probe=broken_connection,
    )

    assert status["status"] == "probe_error"
    assert status["status_zh"] == "探测异常"
    assert status["next_step_zh"] == "下一步：查看探测异常和本机 OpenD 状态；修复前保持只读和真实下单禁用。"
    assert status["read_only_ready"] is False
    assert status["live_order_submission_enabled"] is False
    assert status["supports_real_broker_place_order"] is False
