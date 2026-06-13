from backend.app.services.app_entry import (
    collect_app_entry_readiness,
    format_app_entry_readiness_summary_zh,
)
from tests.app_bundle_helper import make_alpha_launcher_sources, make_minimal_alpha_app


def test_app_entry_readiness_passes_for_complete_alpha_apps(tmp_path):
    make_alpha_launcher_sources(tmp_path)
    app_paths = [
        make_minimal_alpha_app(tmp_path / "outputs" / "applications" / "Alpha.app"),
        make_minimal_alpha_app(tmp_path / "Downloads" / "Alpha.app"),
        make_minimal_alpha_app(tmp_path / "Applications" / "Alpha.app"),
        make_minimal_alpha_app(tmp_path / "SystemApplications" / "Alpha.app"),
    ]

    report = collect_app_entry_readiness(root=tmp_path, app_paths=app_paths)
    summary = format_app_entry_readiness_summary_zh(report)

    assert report["status"] == "pass"
    assert report["status_zh"] == "通过"
    assert report["fail_count"] == 0
    assert report["pass_count"] == report["check_count"]
    assert len(report["bundle_reports"]) == 4
    assert all(item["status"] == "pass" for item in report["bundle_reports"])
    assert report["launcher_sources"]["applescript_starts_dashboard"] is True
    assert report["launcher_sources"]["command_starts_dashboard"] is True
    assert "Alpha 本地应用入口验收" in summary
    assert "完整" in summary
    assert "App Bundle" not in summary


def test_app_entry_readiness_fails_for_incomplete_app_bundle(tmp_path):
    app_path = tmp_path / "Alpha.app"
    app_path.mkdir()

    report = collect_app_entry_readiness(
        root=tmp_path,
        app_paths=[app_path],
        require_launcher_sources=False,
    )

    assert report["status"] == "fail"
    assert report["fail_count"] == 1
    bundle_check = {item["id"]: item for item in report["checks"]}["app_bundle_integrity"]
    assert bundle_check["status"] == "fail"
    assert bundle_check["title_zh"] == "应用包完整性"
    assert bundle_check["evidence"]["bundles"][0]["missing_files"]


def test_custom_app_entry_readiness_accepts_minimal_valid_bundle(tmp_path):
    app_path = make_minimal_alpha_app(tmp_path / "Alpha.app")

    report = collect_app_entry_readiness(
        root=tmp_path,
        app_paths=[app_path],
        require_launcher_sources=False,
    )

    assert report["status"] == "pass"
    assert report["bundle_reports"][0]["plist_valid"] is True
    assert report["bundle_reports"][0]["applet_executable"] is True
