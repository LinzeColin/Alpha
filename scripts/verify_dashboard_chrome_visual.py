from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_dashboard_http_smoke import (
    REQUIRED_DASHBOARD_TEXT,
    REQUIRED_LAYOUT_CONTRACTS,
    BANNED_DASHBOARD_TEXT,
)


DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VIEWPORTS = {
    "desktop": (1440, 1000),
    "mobile": (390, 844),
}
MIN_SCREENSHOT_BYTES = 20_000
MIN_UNIQUE_PIXEL_SAMPLES = 24
REQUIRED_VISIBLE_RENDERED_TEXT = [
    "最近更新：",
    "模拟权益",
    "有效候选单",
    "允许真实下单",
    "允许纸面下单",
    "纸面交易提供方",
    "纸面交易提供方预检",
    "外部纸面账户端到端验证",
    "外部账户同步",
    "外部持仓数",
    "队列存储",
    "安全边界",
    "本地应用入口",
    "应用包完整性",
    "模拟交易循环智能体",
    "本地沙盒模拟经纪商适配器",
]
BANNED_VISIBLE_TEXT = [
    "Alpha Dashboard",
    "Run Paper Cycle",
    "System Snapshot",
    "Approval Queue",
    "No pending tickets",
    "Broker-ready",
    "broker-ready",
    "Moomoo OpenD",
    " bps",
    "cash_rebalance_",
    "target_rebalance_",
    "App Bundle",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="使用本机 Chrome headless 验证 Alpha 控制台截图和布局。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Alpha API 根地址。")
    parser.add_argument("--chrome-path", default=DEFAULT_CHROME_PATH, help="Chrome 可执行文件路径。")
    parser.add_argument("--output-dir", default="outputs/visual_acceptance", help="截图和报告输出目录。")
    parser.add_argument("--timeout", type=float, default=30.0, help="单个 Chrome 命令超时秒数。")
    parser.add_argument("--virtual-time-budget-ms", type=int, default=6000, help="等待页面脚本执行的虚拟时间。")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chrome_path = _resolve_chrome_path(args.chrome_path)

    errors: list[str] = []
    viewport_reports = []
    for name, (width, height) in VIEWPORTS.items():
        screenshot_path = output_dir / f"dashboard_{name}.png"
        dom_path = output_dir / f"dashboard_{name}.html"
        try:
            report = capture_viewport(
                chrome_path=chrome_path,
                url=f"{base_url}/dashboard",
                viewport_name=name,
                width=width,
                height=height,
                screenshot_path=screenshot_path,
                dom_path=dom_path,
                timeout=args.timeout,
                virtual_time_budget_ms=args.virtual_time_budget_ms,
            )
        except Exception as exc:
            errors.append(f"{name} 视口截图失败：{exc}")
            continue
        viewport_reports.append(report)
        errors.extend(report["errors"])

    report = {
        "status": "pass" if not errors else "fail",
        "status_zh": "通过" if not errors else "失败",
        "base_url": base_url,
        "chrome_path": chrome_path,
        "output_dir": str(output_dir),
        "viewport_count": len(VIEWPORTS),
        "checked_viewport_count": len(viewport_reports),
        "error_count": len(errors),
        "errors": errors,
        "viewports": viewport_reports,
    }
    report_path = output_dir / "dashboard_chrome_visual_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


def capture_viewport(
    *,
    chrome_path: str,
    url: str,
    viewport_name: str,
    width: int,
    height: int,
    screenshot_path: Path,
    dom_path: Path,
    timeout: float,
    virtual_time_budget_ms: int,
) -> dict:
    screenshot_path.unlink(missing_ok=True)
    dom_path.unlink(missing_ok=True)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix=f"alpha-chrome-{viewport_name}-") as user_data_dir:
        common_args = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-sync",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-dev-shm-usage",
            "--disable-features=Translate,MediaRouter",
            f"--user-data-dir={user_data_dir}",
            f"--window-size={width},{height}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
        ]
        screenshot_cmd = [
            *common_args,
            f"--screenshot={screenshot_path}",
            url,
        ]
        screenshot_result = _run_chrome(screenshot_cmd, timeout=timeout, artifact_path=screenshot_path)
        screenshot_timeout_recovered = bool(screenshot_result["timed_out"] and screenshot_path.exists())
        if screenshot_result["returncode"] != 0 and not screenshot_timeout_recovered:
            raise RuntimeError(_chrome_error(screenshot_result))
        dom_cmd = [
            *common_args,
            "--dump-dom",
            url,
        ]
        dom_result = _run_chrome(dom_cmd, timeout=timeout, stdout_ready_text="</html>")
        dom_timeout_recovered = bool(dom_result["timed_out"] and dom_result["stdout"])
        dom_fallback_used = False
        if dom_result["returncode"] != 0 and not dom_timeout_recovered:
            dom_result = {
                **dom_result,
                "stdout": _fetch_dashboard_html(url, timeout=timeout),
            }
            dom_fallback_used = True
            errors.append("Chrome DOM 导出失败，已使用 HTTP HTML 兜底；本次未完成渲染后可见文本验收。")

    dom_path.write_text(str(dom_result["stdout"]), encoding="utf-8")
    if not screenshot_path.exists():
        errors.append("截图文件未生成。")
        image_report = {}
    else:
        image_report = inspect_png(screenshot_path)
        if image_report["file_size_bytes"] < MIN_SCREENSHOT_BYTES:
            errors.append(f"截图文件过小：{image_report['file_size_bytes']} bytes。")
        if image_report["width"] != width:
            errors.append(f"截图宽度不符合视口：期望 {width}，实际 {image_report['width']}。")
        if image_report["height"] < min(600, height):
            errors.append(f"截图高度过小：{image_report['height']}。")
        if image_report["unique_sample_count"] < MIN_UNIQUE_PIXEL_SAMPLES:
            errors.append(f"截图像素多样性过低：{image_report['unique_sample_count']}。")

    dom_text = str(dom_result["stdout"])
    visible_text = extract_visible_text(dom_text)
    for text in REQUIRED_DASHBOARD_TEXT:
        if text not in dom_text:
            errors.append(f"DOM 缺少中文文案：{text}")
    for text in BANNED_DASHBOARD_TEXT:
        if text in dom_text:
            errors.append(f"DOM 仍包含旧英文文案：{text}")
    if not dom_fallback_used:
        for text in REQUIRED_VISIBLE_RENDERED_TEXT:
            if text not in visible_text:
                errors.append(f"渲染后可见文本缺少中文文案：{text}")
        for text in BANNED_VISIBLE_TEXT:
            if text in visible_text:
                errors.append(f"渲染后可见文本仍包含英文界面文案：{text}")
    for label, css in REQUIRED_LAYOUT_CONTRACTS:
        if css not in dom_text:
            errors.append(f"DOM 缺少布局规则：{label}")

    return {
        "viewport": viewport_name,
        "width": width,
        "height": height,
        "screenshot_path": str(screenshot_path),
        "dom_path": str(dom_path),
        "image": image_report,
        "chrome_timeout_recovered": screenshot_timeout_recovered or dom_timeout_recovered,
        "screenshot_timeout_recovered": screenshot_timeout_recovered,
        "dom_timeout_recovered": dom_timeout_recovered,
        "dom_fallback_used": dom_fallback_used,
        "visible_text_character_count": len(visible_text),
        "error_count": len(errors),
        "errors": errors,
    }


def inspect_png(path: Path) -> dict:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"{path} 不是 PNG 文件。")
    width = height = bit_depth = color_type = None
    idat = bytearray()
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk_data)
            if bit_depth != 8 or interlace != 0:
                raise RuntimeError(f"不支持的 PNG 格式：bit_depth={bit_depth}, interlace={interlace}")
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None:
        raise RuntimeError("PNG 缺少 IHDR。")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise RuntimeError(f"不支持的 PNG color_type={color_type}")
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    previous = bytearray(stride)
    rows: list[bytes] = []
    pos = 0
    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        scanline = bytearray(raw[pos : pos + stride])
        pos += stride
        recon = _unfilter(scanline, previous, filter_type, channels)
        rows.append(bytes(recon))
        previous = recon
    sample_colors = set()
    step_y = max(1, height // 80)
    step_x = max(1, width // 80)
    for y in range(0, height, step_y):
        row = rows[y]
        for x in range(0, width, step_x):
            start = x * channels
            sample_colors.add(bytes(row[start : start + min(channels, 3)]))
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "channels": channels,
        "file_size_bytes": path.stat().st_size,
        "unique_sample_count": len(sample_colors),
    }


def _unfilter(scanline: bytearray, previous: bytearray, filter_type: int, channels: int) -> bytearray:
    if filter_type == 0:
        return scanline
    result = bytearray(len(scanline))
    for index, value in enumerate(scanline):
        left = result[index - channels] if index >= channels else 0
        up = previous[index]
        up_left = previous[index - channels] if index >= channels else 0
        if filter_type == 1:
            result[index] = (value + left) & 0xFF
        elif filter_type == 2:
            result[index] = (value + up) & 0xFF
        elif filter_type == 3:
            result[index] = (value + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            result[index] = (value + _paeth(left, up, up_left)) & 0xFF
        else:
            raise RuntimeError(f"不支持的 PNG filter_type={filter_type}")
    return result


def _paeth(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left


def _resolve_chrome_path(path: str) -> str:
    if Path(path).exists():
        return path
    found = shutil.which(path)
    if found:
        return found
    raise RuntimeError(f"未找到 Chrome 可执行文件：{path}")


def _fetch_dashboard_html(url: str, *, timeout: float) -> str:
    with urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _run_chrome(
    command: list[str],
    *,
    timeout: float,
    artifact_path: Path | None = None,
    stdout_ready_text: str | None = None,
) -> dict:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", prefix="alpha-chrome-stdout-", delete=False) as stdout_file:
        stdout_path = Path(stdout_file.name)
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", prefix="alpha-chrome-stderr-", delete=False) as stderr_file:
        stderr_path = Path(stderr_file.name)
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
            process = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                start_new_session=True,
            )
            timed_out = False
            deadline = time.monotonic() + max(0.1, float(timeout))
            while process.poll() is None and time.monotonic() < deadline:
                stdout_handle.flush()
                if artifact_path and artifact_path.exists() and artifact_path.stat().st_size >= MIN_SCREENSHOT_BYTES:
                    timed_out = True
                    _terminate_process_group(process)
                    break
                if stdout_ready_text and _file_contains(stdout_path, stdout_ready_text):
                    timed_out = True
                    _terminate_process_group(process)
                    break
                time.sleep(0.1)
            if process.poll() is None:
                timed_out = True
                _terminate_process_group(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _kill_process_group(process)
                process.wait(timeout=5)
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        return {
            "returncode": process.returncode if process.returncode is not None else -9,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": timed_out,
            "command": command,
        }
    finally:
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return False


def _terminate_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        process.terminate()


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        process.kill()


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "template", "head"}:
            self._skip_stack.append(lowered)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._skip_stack and self._skip_stack[-1] == lowered:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def extract_visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _chrome_error(result: dict) -> str:
    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()
    details = stderr or stdout or "无输出"
    timeout_suffix = "（命令已超时并被终止）" if result.get("timed_out") else ""
    return f"Chrome 返回 {result.get('returncode')}{timeout_suffix}：{details[-1200:]}"


if __name__ == "__main__":
    raise SystemExit(main())
