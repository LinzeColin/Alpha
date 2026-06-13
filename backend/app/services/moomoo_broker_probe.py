from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import os
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable


DEFAULT_MOOMOO_OPEND_HOST = "127.0.0.1"
DEFAULT_MOOMOO_OPEND_PORT = 11111
DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS = 0.25
DEFAULT_MOOMOO_API_HOME = Path(__file__).resolve().parents[3] / "runtime" / "moomoo_api_home"
DEFAULT_MOOMOO_QUOTE_SYMBOLS = ("US.SPY", "US.QQQ", "US.TLT")
_HOME_LOCK = RLock()

PACKAGE_CANDIDATES = (
    {"import_name": "moomoo", "distribution_names": ("moomoo", "moomoo-api")},
    {"import_name": "futu", "distribution_names": ("futu", "futu-api")},
)

STATUS_ZH = {
    "ready_read_only": "只读探测就绪",
    "api_missing": "API 包未安装",
    "api_import_error": "API 包导入失败",
    "opend_unreachable": "OpenD 未连接",
    "not_configured": "未就绪",
    "probe_error": "探测异常",
}

MESSAGE_ZH = {
    "ready_read_only": "Moomoo API 包和本机 OpenD 端口均可用；当前仅允许只读探测，不会解锁交易或提交真实资金订单。",
    "api_missing": "检测到本机 OpenD 端口，但当前 Python 环境未安装可导入的 moomoo/futu API 包。",
    "api_import_error": "检测到 Moomoo/Futu API 包，但 SDK 导入失败；系统不会继续打开行情或交易上下文。",
    "opend_unreachable": "当前 Python 环境可导入 Moomoo API 包，但未能连接本机 OpenD 端口。",
    "not_configured": "当前 Python 环境未发现 Moomoo API 包，也未能连接本机 OpenD 端口。",
    "probe_error": "Moomoo OpenD 探测过程中发生异常；系统保持只读与真实下单禁用状态。",
}

NEXT_STEP_ZH = {
    "ready_read_only": "下一步：只接入只读行情和账户状态探测，继续保持真实下单禁用。",
    "api_missing": "下一步：在项目虚拟环境中安装 Moomoo/Futu OpenAPI Python 包后重新探测。",
    "api_import_error": "下一步：检查 Moomoo SDK 日志目录权限或运行环境 HOME；修复前保持只读和真实下单禁用。",
    "opend_unreachable": "下一步：启动本机 Moomoo OpenD，并确认监听地址和端口配置。",
    "not_configured": "下一步：安装 Moomoo/Futu OpenAPI Python 包并启动本机 OpenD。",
    "probe_error": "下一步：查看探测异常和本机 OpenD 状态；修复前保持只读和真实下单禁用。",
}


@dataclass(frozen=True)
class MoomooOpenDProbeConfig:
    host: str = DEFAULT_MOOMOO_OPEND_HOST
    port: int = DEFAULT_MOOMOO_OPEND_PORT
    timeout_seconds: float = DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS
    api_home: Path = DEFAULT_MOOMOO_API_HOME

    @classmethod
    def from_env(cls) -> "MoomooOpenDProbeConfig":
        return cls(
            host=os.getenv("MOOMOO_OPEND_HOST", DEFAULT_MOOMOO_OPEND_HOST),
            port=_int_env("MOOMOO_OPEND_PORT", DEFAULT_MOOMOO_OPEND_PORT),
            timeout_seconds=_float_env("MOOMOO_OPEND_TIMEOUT_SECONDS", DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS),
            api_home=Path(os.getenv("MOOMOO_API_HOME", str(DEFAULT_MOOMOO_API_HOME))),
        )


@dataclass(frozen=True)
class MoomooQuoteSnapshotConfig(MoomooOpenDProbeConfig):
    symbols: tuple[str, ...] = DEFAULT_MOOMOO_QUOTE_SYMBOLS

    @classmethod
    def from_env(cls) -> "MoomooQuoteSnapshotConfig":
        return cls(
            host=os.getenv("MOOMOO_OPEND_HOST", DEFAULT_MOOMOO_OPEND_HOST),
            port=_int_env("MOOMOO_OPEND_PORT", DEFAULT_MOOMOO_OPEND_PORT),
            timeout_seconds=_float_env("MOOMOO_OPEND_TIMEOUT_SECONDS", DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS),
            api_home=Path(os.getenv("MOOMOO_API_HOME", str(DEFAULT_MOOMOO_API_HOME))),
            symbols=_symbols_env("MOOMOO_QUOTE_SYMBOLS", DEFAULT_MOOMOO_QUOTE_SYMBOLS),
        )


def probe_moomoo_opend(
    config: MoomooOpenDProbeConfig | None = None,
    *,
    package_detector: Callable[[], dict] | None = None,
    connection_probe: Callable[[str, int, float], dict] | None = None,
) -> dict:
    cfg = config or MoomooOpenDProbeConfig.from_env()
    try:
        detected_package = (package_detector or detect_moomoo_api_package)()
        connection = (connection_probe or probe_tcp_connection)(cfg.host, cfg.port, cfg.timeout_seconds)
    except Exception as exc:
        detected_package = {
            "available": False,
            "import_name": None,
            "distribution_name": None,
            "version": None,
            "message_zh": "Moomoo API 包检测失败。",
        }
        connection = {"connected": False, "error": exc.__class__.__name__, "error_zh": _connection_error_zh(exc)}
        status = "probe_error"
        return _probe_status(cfg, detected_package=detected_package, connection=connection, status=status)
    status = _status(detected_package=detected_package, opend_connected=connection["connected"])
    return _probe_status(cfg, detected_package=detected_package, connection=connection, status=status)


def probe_moomoo_quote_snapshot(
    config: MoomooQuoteSnapshotConfig | None = None,
    *,
    readiness_probe: Callable[[], dict] | None = None,
    quote_fetcher: Callable[[MoomooQuoteSnapshotConfig], dict] | None = None,
) -> dict:
    cfg = config or MoomooQuoteSnapshotConfig.from_env()
    readiness = (readiness_probe or (lambda: probe_moomoo_opend(cfg)))()
    if not readiness.get("read_only_ready"):
        return {
            "provider_id": "moomoo_opend",
            "mode": "read_only_quote_snapshot",
            "mode_zh": "只读行情快照",
            "status": "blocked",
            "status_zh": "未执行",
            "message_zh": "Moomoo 只读连接未就绪，未执行行情快照探测。",
            "readiness_status": readiness.get("status"),
            "readiness_status_zh": readiness.get("status_zh"),
            "symbols": list(cfg.symbols),
            "quotes": [],
            "row_count": 0,
            "generated_at": _utc_now_iso(),
            "trade_context_enabled": False,
            "trade_context_enabled_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
        }
    try:
        quote_result = (quote_fetcher or _fetch_moomoo_quote_snapshot)(cfg)
    except Exception as exc:
        return {
            "provider_id": "moomoo_opend",
            "mode": "read_only_quote_snapshot",
            "mode_zh": "只读行情快照",
            "status": "error",
            "status_zh": "探测异常",
            "message_zh": f"Moomoo 只读行情快照失败：{_exception_zh(exc)}",
            "error": exc.__class__.__name__,
            "symbols": list(cfg.symbols),
            "quotes": [],
            "row_count": 0,
            "generated_at": _utc_now_iso(),
            "trade_context_enabled": False,
            "trade_context_enabled_zh": "否",
            "live_order_submission_enabled": False,
            "live_order_submission_enabled_zh": "否",
        }
    return {
        "provider_id": "moomoo_opend",
        "mode": "read_only_quote_snapshot",
        "mode_zh": "只读行情快照",
        "status": quote_result["status"],
        "status_zh": "已获取" if quote_result["status"] == "ready" else "获取失败",
        "message_zh": quote_result["message_zh"],
        "symbols": list(cfg.symbols),
        "quotes": quote_result["quotes"],
        "row_count": quote_result["row_count"],
        "generated_at": _utc_now_iso(),
        "trade_context_enabled": False,
        "trade_context_enabled_zh": "否",
        "live_order_submission_enabled": False,
        "live_order_submission_enabled_zh": "否",
        "safe_operations_zh": ["打开只读行情连接", "读取市场快照", "关闭只读行情连接"],
        "forbidden_operations_zh": ["创建交易上下文", "解锁交易", "提交真实资金订单"],
    }


def _probe_status(
    cfg: MoomooOpenDProbeConfig,
    *,
    detected_package: dict,
    connection: dict,
    status: str,
) -> dict:
    return {
        "provider_id": "moomoo_opend",
        "provider_name": "Moomoo OpenD",
        "provider_name_zh": "Moomoo OpenD",
        "mode": "read_only_probe",
        "mode_zh": "只读连接探测",
        "status": status,
        "status_zh": STATUS_ZH[status],
        "message_zh": MESSAGE_ZH[status],
        "next_step_zh": NEXT_STEP_ZH[status],
        "generated_at": _utc_now_iso(),
        "host": cfg.host,
        "port": cfg.port,
        "timeout_seconds": cfg.timeout_seconds,
        "package": detected_package,
        "package_available": detected_package["available"],
        "package_available_zh": "是" if detected_package["available"] else "否",
        "package_installed": detected_package.get("installed", detected_package["available"]),
        "package_installed_zh": "是" if detected_package.get("installed", detected_package["available"]) else "否",
        "package_importable": detected_package.get("importable", detected_package["available"]),
        "package_importable_zh": "是" if detected_package.get("importable", detected_package["available"]) else "否",
        "opend_connection": connection,
        "opend_connected": connection["connected"],
        "opend_connected_zh": "是" if connection["connected"] else "否",
        "read_only_ready": detected_package["available"] and connection["connected"],
        "read_only_ready_zh": "是" if detected_package["available"] and connection["connected"] else "否",
        "credential_required_for_probe": False,
        "credential_required_for_probe_zh": "否",
        "trade_unlock_required": False,
        "trade_unlock_required_zh": "否",
        "trade_context_enabled": False,
        "trade_context_enabled_zh": "否",
        "live_order_submission_enabled": False,
        "live_order_submission_enabled_zh": "否",
        "supports_real_broker_place_order": False,
        "supports_real_broker_place_order_zh": "否",
        "safe_operations_zh": ["检测 API 包", "检测本机 OpenD 端口", "读取连接就绪状态"],
        "forbidden_operations_zh": ["解锁交易", "提交真实资金订单", "修改真实账户"],
    }


def detect_moomoo_api_package() -> dict:
    for candidate in PACKAGE_CANDIDATES:
        import_name = candidate["import_name"]
        if importlib.util.find_spec(import_name) is None:
            continue
        version = _package_version(import_name, candidate["distribution_names"])
        api_home = Path(os.getenv("MOOMOO_API_HOME", str(DEFAULT_MOOMOO_API_HOME)))
        import_status = _safe_import_module(import_name, api_home)
        return {
            "available": import_status["importable"],
            "available_zh": "是" if import_status["importable"] else "否",
            "installed": True,
            "installed_zh": "是",
            "importable": import_status["importable"],
            "importable_zh": "是" if import_status["importable"] else "否",
            "import_name": import_name,
            "distribution_name": version["distribution_name"],
            "version": version["version"],
            "import_error": import_status["error"],
            "import_error_zh": import_status["error_zh"],
            "api_home": str(api_home),
            "message_zh": (
                "当前 Python 环境可导入 Moomoo API 包。"
                if import_status["importable"]
                else f"当前 Python 环境已安装 Moomoo API 包，但导入失败：{import_status['error_zh']}"
            ),
        }
    return {
        "available": False,
        "available_zh": "否",
        "installed": False,
        "installed_zh": "否",
        "importable": False,
        "importable_zh": "否",
        "import_name": None,
        "distribution_name": None,
        "version": None,
        "import_error": None,
        "import_error_zh": None,
        "api_home": str(DEFAULT_MOOMOO_API_HOME),
        "message_zh": "当前 Python 环境未发现可导入的 moomoo 或 futu API 包。",
    }


def probe_tcp_connection(host: str, port: int, timeout_seconds: float) -> dict:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_seconds)):
            return {"connected": True, "error": None, "error_zh": None}
    except Exception as exc:
        return {"connected": False, "error": exc.__class__.__name__, "error_zh": _connection_error_zh(exc)}


def _status(*, detected_package: dict, opend_connected: bool) -> str:
    package_available = bool(detected_package.get("available"))
    package_installed = bool(detected_package.get("installed", package_available))
    if package_installed and not package_available:
        return "api_import_error"
    if package_available and opend_connected:
        return "ready_read_only"
    if opend_connected and not package_available:
        return "api_missing"
    if package_available and not opend_connected:
        return "opend_unreachable"
    return "not_configured"


def _package_version(import_name: str, distribution_names: tuple[str, ...]) -> dict:
    for name in (import_name, *distribution_names):
        try:
            return {"distribution_name": name, "version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            continue
    return {"distribution_name": None, "version": None}


def _connection_error_zh(exc: Exception) -> str:
    if isinstance(exc, ConnectionRefusedError):
        return "本机 OpenD 端口拒绝连接。"
    if isinstance(exc, TimeoutError):
        return "连接本机 OpenD 端口超时。"
    if isinstance(exc, PermissionError):
        return "当前运行环境没有权限连接本机 OpenD 端口。"
    return "无法连接本机 OpenD 端口。"


def _fetch_moomoo_quote_snapshot(cfg: MoomooQuoteSnapshotConfig) -> dict:
    with _temporary_home(cfg.api_home):
        moomoo = importlib.import_module("moomoo")
        quote_context = moomoo.OpenQuoteContext(host=cfg.host, port=int(cfg.port))
        try:
            ret, data = quote_context.get_market_snapshot(list(cfg.symbols))
        finally:
            quote_context.close()
    if ret != getattr(moomoo, "RET_OK", 0):
        return {
            "status": "error",
            "message_zh": f"Moomoo OpenD 返回行情错误：{data}",
            "quotes": [],
            "row_count": 0,
        }
    records = data.to_dict(orient="records") if hasattr(data, "to_dict") else []
    quotes = [_sanitize_quote_record(record) for record in records]
    return {
        "status": "ready",
        "message_zh": f"已通过 Moomoo OpenD 只读行情连接获取 {len(quotes)} 条市场快照。",
        "quotes": quotes,
        "row_count": len(quotes),
    }


def _sanitize_quote_record(record: dict) -> dict:
    fields = [
        "code",
        "name",
        "update_time",
        "last_price",
        "open_price",
        "high_price",
        "low_price",
        "prev_close_price",
        "volume",
        "turnover",
        "ask_price",
        "bid_price",
        "sec_status",
    ]
    return {field: _json_safe_value(record.get(field)) for field in fields}


def _json_safe_value(value: object) -> object:
    try:
        if value != value:
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _safe_import_module(import_name: str, api_home: Path) -> dict:
    try:
        with _temporary_home(api_home):
            importlib.import_module(import_name)
        return {"importable": True, "error": None, "error_zh": None}
    except Exception as exc:
        return {"importable": False, "error": exc.__class__.__name__, "error_zh": _exception_zh(exc)}


@contextmanager
def _temporary_home(api_home: Path):
    api_home.mkdir(parents=True, exist_ok=True)
    with _HOME_LOCK:
        previous_home = os.environ.get("HOME")
        os.environ["HOME"] = str(api_home)
        try:
            yield
        finally:
            if previous_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous_home


def _exception_zh(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return "运行环境没有权限访问 Moomoo SDK 日志目录或本机端口。"
    if isinstance(exc, TimeoutError):
        return "连接 Moomoo OpenD 超时。"
    if isinstance(exc, ConnectionRefusedError):
        return "Moomoo OpenD 拒绝连接。"
    return str(exc) or "未知异常"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _symbols_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    symbols = tuple(item.strip() for item in raw.split(",") if item.strip())
    return symbols or default
