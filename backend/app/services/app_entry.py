from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_PATH = DEFAULT_ROOT / "outputs" / "app_entry" / "app_entry_readiness_latest.json"
REQUIRED_BUNDLE_FILES = [
    "Contents/Info.plist",
    "Contents/MacOS/applet",
    "Contents/PkgInfo",
    "Contents/Resources/Scripts/main.scpt",
]
FINGERPRINT_FILES = [
    "Contents/Info.plist",
    "Contents/MacOS/applet",
    "Contents/PkgInfo",
    "Contents/Resources/Scripts/main.scpt",
]
REQUIRED_PLIST_VALUES = {
    "CFBundleName": "Alpha",
    "CFBundlePackageType": "APPL",
    "CFBundleExecutable": "applet",
}


def default_alpha_app_paths(root: str | Path = DEFAULT_ROOT) -> list[Path]:
    root = Path(root)
    return [
        root / "outputs" / "applications" / "Alpha.app",
        Path.home() / "Downloads" / "Alpha.app",
        Path.home() / "Applications" / "Alpha.app",
        Path("/Applications/Alpha.app"),
    ]


def collect_app_entry_readiness(
    *,
    root: str | Path = DEFAULT_ROOT,
    app_paths: list[str | Path] | None = None,
    require_launcher_sources: bool = True,
) -> dict:
    root = Path(root)
    paths = [Path(path) for path in (app_paths or default_alpha_app_paths(root))]
    reference = root / "outputs" / "applications" / "Alpha.app"
    reference_fingerprint = _bundle_fingerprint(reference) if reference.exists() else {}
    bundle_reports = [
        _inspect_app_bundle(
            path,
            reference_fingerprint=reference_fingerprint if path != reference else None,
        )
        for path in paths
    ]
    launcher_report = _inspect_launcher_sources(root) if require_launcher_sources else _skipped_launcher_sources(root)
    checks = [_check_launcher_sources(launcher_report), _check_bundles(bundle_reports)]
    status = _overall_status(checks)
    return {
        "status": status,
        "status_zh": _status_zh(status),
        "generated_at": _utc_now_iso(),
        "check_count": len(checks),
        "pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "warn_count": sum(1 for item in checks if item["status"] == "warn"),
        "fail_count": sum(1 for item in checks if item["status"] == "fail"),
        "checks": checks,
        "bundle_reports": bundle_reports,
        "launcher_sources": launcher_report,
        "summary_zh": _summary_zh(checks),
    }


def format_app_entry_readiness_summary_zh(report: dict) -> str:
    lines = [
        "Alpha 本地应用入口验收",
        f"总体状态：{report.get('status_zh', '未知')}",
        f"生成时间：{report.get('generated_at', '无')}",
        f"通过/关注/失败：{report.get('pass_count', 0)} / {report.get('warn_count', 0)} / {report.get('fail_count', 0)}",
        f"结论：{report.get('summary_zh', '无')}",
        "检查项：",
    ]
    for check in report.get("checks", []):
        lines.append(f"- {check.get('title_zh', '未知检查')}：{check.get('status_zh', '未知')} - {check.get('message_zh', '')}")
    return "\n".join(lines)


def write_app_entry_readiness_report(report: dict, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "status": "written",
        "status_zh": "已写入",
        "path": str(path),
        "file_size_bytes": path.stat().st_size,
    }


def _inspect_launcher_sources(root: Path) -> dict:
    applescript_path = root / "outputs" / "applications" / "Alpha.applescript"
    command_path = root / "outputs" / "applications" / "Alpha.command"
    applescript_text = _read_text(applescript_path)
    command_text = _read_text(command_path)
    expected_root = str(root)
    return {
        "required": True,
        "applescript_path": str(applescript_path),
        "applescript_exists": applescript_path.exists(),
        "applescript_points_to_root": expected_root in applescript_text,
        "applescript_starts_dashboard": "scripts/start_alpha_dashboard.sh" in applescript_text,
        "applescript_opens_browser": "ALPHA_OPEN_BROWSER=1" in applescript_text,
        "command_path": str(command_path),
        "command_exists": command_path.exists(),
        "command_executable": os.access(command_path, os.X_OK),
        "command_points_to_root": expected_root in command_text,
        "command_starts_dashboard": "scripts/start_alpha_dashboard.sh" in command_text,
    }


def _skipped_launcher_sources(root: Path) -> dict:
    return {
        "required": False,
        "status_zh": "已跳过",
        "reason_zh": "调用方传入自定义应用路径，仅验证应用包结构。",
        "root": str(root),
    }


def _inspect_app_bundle(path: Path, *, reference_fingerprint: dict[str, str] | None = None) -> dict:
    report: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_app": path.suffix == ".app",
        "missing_files": [],
        "plist_valid": False,
        "plist_values": {},
        "plist_mismatches": {},
        "applet_executable": False,
        "fingerprint_matches_reference": None,
        "status": "fail",
        "status_zh": "失败",
    }
    if not path.exists() or not path.is_dir() or path.suffix != ".app":
        return report

    missing_files = [relative for relative in REQUIRED_BUNDLE_FILES if not (path / relative).exists()]
    report["missing_files"] = missing_files
    plist_values, plist_error = _read_plist_values(path / "Contents" / "Info.plist")
    report["plist_valid"] = plist_error is None
    report["plist_error"] = plist_error
    report["plist_values"] = plist_values
    report["plist_mismatches"] = {
        key: {"expected": expected, "actual": plist_values.get(key)}
        for key, expected in REQUIRED_PLIST_VALUES.items()
        if plist_values.get(key) != expected
    }
    report["applet_executable"] = os.access(path / "Contents" / "MacOS" / "applet", os.X_OK)
    if reference_fingerprint:
        fingerprint = _bundle_fingerprint(path)
        report["fingerprint_matches_reference"] = fingerprint == reference_fingerprint
        report["fingerprint_mismatches"] = sorted(
            relative
            for relative in set(fingerprint) | set(reference_fingerprint)
            if fingerprint.get(relative) != reference_fingerprint.get(relative)
        )

    ok = (
        not missing_files
        and report["plist_valid"]
        and not report["plist_mismatches"]
        and report["applet_executable"]
        and report["fingerprint_matches_reference"] is not False
    )
    report["status"] = "pass" if ok else "fail"
    report["status_zh"] = "通过" if ok else "失败"
    return report


def _read_plist_values(path: Path) -> tuple[dict, str | None]:
    try:
        data = plistlib.loads(path.read_bytes())
    except Exception as exc:
        return {}, f"{exc.__class__.__name__}: {exc}"
    return {key: data.get(key) for key in REQUIRED_PLIST_VALUES}, None


def _bundle_fingerprint(path: Path) -> dict[str, str]:
    return {
        relative: _sha256(path / relative)
        for relative in FINGERPRINT_FILES
        if (path / relative).exists()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _check_launcher_sources(report: dict) -> dict:
    if not report.get("required"):
        return _check("app_launcher_sources", "应用启动源文件", "pass", "自定义应用路径验收已跳过仓库启动源文件检查。", report)
    required_keys = [
        "applescript_exists",
        "applescript_points_to_root",
        "applescript_starts_dashboard",
        "applescript_opens_browser",
        "command_exists",
        "command_executable",
        "command_points_to_root",
        "command_starts_dashboard",
    ]
    failed = [key for key in required_keys if not report.get(key)]
    if failed:
        return _check("app_launcher_sources", "应用启动源文件", "fail", "仓库应用启动源文件不完整或没有指向当前控制台启动脚本。", {**report, "failed_keys": failed})
    return _check("app_launcher_sources", "应用启动源文件", "pass", "AppleScript 启动脚本和命令入口均指向当前仓库控制台启动脚本。", report)


def _check_bundles(bundle_reports: list[dict]) -> dict:
    failed = [item for item in bundle_reports if item.get("status") != "pass"]
    evidence = {"bundle_count": len(bundle_reports), "failed_count": len(failed), "bundles": bundle_reports}
    if failed:
        return _check("app_bundle_integrity", "应用包完整性", "fail", "至少一个 Alpha.app 缺失、结构不完整、plist 无效或与仓库应用不一致。", evidence)
    return _check("app_bundle_integrity", "应用包完整性", "pass", "仓库、Downloads、用户 Applications 和系统 Applications 的 Alpha.app 均为有效应用包。", evidence)


def _check(check_id: str, title_zh: str, status: str, message_zh: str, evidence: dict | None = None) -> dict:
    return {
        "id": check_id,
        "title_zh": title_zh,
        "status": status,
        "status_zh": {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(status, "未知"),
        "message_zh": message_zh,
        "evidence": evidence or {},
    }


def _overall_status(checks: list[dict]) -> str:
    if any(item["status"] == "fail" for item in checks):
        return "fail"
    if any(item["status"] == "warn" for item in checks):
        return "warn"
    return "pass"


def _status_zh(status: str) -> str:
    return {"pass": "通过", "warn": "需关注", "fail": "失败"}.get(status, "未知")


def _summary_zh(checks: list[dict]) -> str:
    fail_count = sum(1 for item in checks if item["status"] == "fail")
    warn_count = sum(1 for item in checks if item["status"] == "warn")
    if fail_count:
        return f"本地应用入口仍有 {fail_count} 个失败项，不能声明 6月17日应用入口稳定。"
    if warn_count:
        return f"本地应用入口可用但仍有 {warn_count} 个关注项。"
    return "仓库、Downloads、用户 Applications 和系统 Applications 的 Alpha.app 入口完整，启动源文件指向当前控制台。"


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 Alpha 本地应用入口完整性。")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON；默认输出中文摘要。")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="JSON 报告输出路径。")
    args = parser.parse_args()
    report = collect_app_entry_readiness()
    write_result = write_app_entry_readiness_report(report, args.output)
    report["write_result"] = write_result
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_app_entry_readiness_summary_zh(report))
        print(f"报告路径：{write_result['path']}")
    raise SystemExit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
