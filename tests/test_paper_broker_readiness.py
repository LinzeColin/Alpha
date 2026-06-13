from pathlib import Path

from backend.app.services.paper_broker_readiness import (
    collect_paper_broker_readiness,
    format_paper_broker_readiness_summary_zh,
    write_paper_broker_readiness_report,
)


def _write_config(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_paper_broker_readiness_reports_local_sandbox_ready_with_external_gap(tmp_path):
    config = _write_config(
        tmp_path / "paper_broker.yaml",
        "\n".join(
            [
                "paper_broker:",
                "  provider: local_sandbox",
                "  allow_external_paper_api: false",
                "  safety:",
                "    live_order_submission_enabled: false",
                "    require_paper_mode: true",
            ]
        ),
    )

    report = collect_paper_broker_readiness(config_path=config, paper_state_path=tmp_path / "paper_portfolio.json")
    summary = format_paper_broker_readiness_summary_zh(report)

    assert report["status"] == "warn"
    assert report["overall_status"] == "local_paper_ready_external_pending"
    assert report["overall_status_zh"] == "本地模拟可用，外部纸面账户待接入"
    assert report["local_sandbox_ready"] is True
    assert report["external_paper_e2e_ready"] is False
    assert report["fail_count"] == 0
    assert report["warn_count"] == 2
    assert "6月15日自动模拟交易" in report["summary_zh"]
    assert "Alpha 纸面交易提供方预检" in summary
    assert "外部纸面账户端到端验证：否" in summary
    assert report["safety_boundary"]["live_order_submission_enabled"] is False


def test_paper_broker_readiness_fails_when_config_enables_live_order_submission(tmp_path):
    config = _write_config(
        tmp_path / "paper_broker.yaml",
        "\n".join(
            [
                "paper_broker:",
                "  provider: local_sandbox",
                "  safety:",
                "    live_order_submission_enabled: true",
                "    require_paper_mode: true",
            ]
        ),
    )

    report = collect_paper_broker_readiness(config_path=config, paper_state_path=tmp_path / "paper_portfolio.json")

    assert report["status"] == "fail"
    assert report["overall_status_zh"] == "不可用"
    config_check = {item["id"]: item for item in report["checks"]}["paper_broker_config"]
    assert config_check["status"] == "fail"
    assert "真实资金下单" in config_check["message_zh"]


def test_paper_broker_readiness_accepts_injected_external_paper_e2e(tmp_path):
    config = _write_config(
        tmp_path / "paper_broker.yaml",
        "\n".join(
            [
                "paper_broker:",
                "  provider: alpaca_paper",
                "  allow_external_paper_api: true",
                "  safety:",
                "    live_order_submission_enabled: false",
                "    require_paper_mode: true",
            ]
        ),
    )
    status = {
        "provider": "alpaca_paper",
        "provider_zh": "Alpaca 纸面交易 API",
        "mode": "paper",
        "adapter_readiness": "ready",
        "adapter_readiness_zh": "就绪",
        "connected": True,
        "paper_order_submission_enabled": True,
        "paper_order_submission_enabled_zh": "是",
        "supports_market_orders": True,
        "paper_base_url_allowed": True,
        "credentials_present": True,
        "read_only_sync_enabled": True,
        "read_only_sync_ready": True,
        "live_order_submission_enabled": False,
        "supports_real_broker_place_order": False,
        "execution_model_zh": "Alpaca Paper API 模拟撮合",
    }
    snapshot = {
        "status": "ready",
        "status_zh": "已同步",
        "provider": "alpaca_paper",
        "provider_zh": "Alpaca 纸面交易 API",
        "read_only_sync_enabled": True,
        "read_only_sync_enabled_zh": "是",
        "position_count": 1,
        "recent_order_count": 2,
        "live_order_submission_enabled": False,
        "live_order_submission_enabled_zh": "否",
        "summary_zh": "Alpaca 纸面账户同步完成。",
    }

    report = collect_paper_broker_readiness(
        config_path=config,
        paper_state_path=tmp_path / "paper_portfolio.json",
        paper_broker_status=status,
        external_snapshot=snapshot,
    )

    assert report["status"] == "pass"
    assert report["overall_status"] == "external_paper_ready"
    assert report["overall_status_zh"] == "外部纸面账户就绪"
    assert report["external_paper_e2e_ready"] is True
    assert report["pass_count"] == report["check_count"]
    assert report["external_snapshot_summary"]["position_count"] == 1
    assert "真实下单仍保持禁用" in report["summary_zh"]


def test_paper_broker_readiness_summary_write_result_is_chinese(tmp_path):
    report = collect_paper_broker_readiness(
        config_path=tmp_path / "missing.yaml",
        paper_state_path=tmp_path / "paper_portfolio.json",
    )

    write_result = write_paper_broker_readiness_report(report, tmp_path / "paper_broker_readiness.json")

    assert write_result["status_zh"] == "已写入"
    assert Path(write_result["path"]).exists()
