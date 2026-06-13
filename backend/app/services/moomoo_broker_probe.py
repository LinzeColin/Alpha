from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


DEFAULT_MOOMOO_OPEND_HOST = "127.0.0.1"
DEFAULT_MOOMOO_OPEND_PORT = 11111
DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS = 0.25

PACKAGE_CANDIDATES = (
    {"import_name": "moomoo", "distribution_names": ("moomoo", "moomoo-api")},
    {"import_name": "futu", "distribution_names": ("futu", "futu-api")},
)

STATUS_ZH = {
    "ready_read_only": "只读探测就绪",
    "api_missing": "API 包未安装",
    "opend_unreachable": "OpenD 未连接",
    "not_configured": "未就绪",
    "probe_error": "探测异常",
}

MESSAGE_ZH = {
    "ready_read_only": "Moomoo API 包和本机 OpenD 端口均可用；当前仅允许只读探测，不会解锁交易或提交真实资金订单。",
    "api_missing": "检测到本机 OpenD 端口，但当前 Python 环境未安装可导入的 moomoo/futu API 包。",
    "opend_unreachable": "当前 Python 环境可导入 Moomoo API 包，但未能连接本机 OpenD 端口。",
    "not_configured": "当前 Python 环境未发现 Moomoo API 包，也未能连接本机 OpenD 端口。",
    "probe_error": "Moomoo OpenD 探测过程中发生异常；系统保持只读与真实下单禁用状态。",
}

NEXT_STEP_ZH = {
    "ready_read_only": "下一步：只接入只读行情和账户状态探测，继续保持真实下单禁用。",
    "api_missing": "下一步：在项目虚拟环境中安装 Moomoo/Futu OpenAPI Python 包后重新探测。",
    "opend_unreachable": "下一步：启动本机 Moomoo OpenD，并确认监听地址和端口配置。",
    "not_configured": "下一步：安装 Moomoo/Futu OpenAPI Python 包并启动本机 OpenD。",
    "probe_error": "下一步：查看探测异常和本机 OpenD 状态；修复前保持只读和真实下单禁用。",
}


@dataclass(frozen=True)
class MoomooOpenDProbeConfig:
    host: str = DEFAULT_MOOMOO_OPEND_HOST
    port: int = DEFAULT_MOOMOO_OPEND_PORT
    timeout_seconds: float = DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "MoomooOpenDProbeConfig":
        return cls(
            host=os.getenv("MOOMOO_OPEND_HOST", DEFAULT_MOOMOO_OPEND_HOST),
            port=_int_env("MOOMOO_OPEND_PORT", DEFAULT_MOOMOO_OPEND_PORT),
            timeout_seconds=_float_env("MOOMOO_OPEND_TIMEOUT_SECONDS", DEFAULT_MOOMOO_OPEND_TIMEOUT_SECONDS),
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
    status = _status(package_available=detected_package["available"], opend_connected=connection["connected"])
    return _probe_status(cfg, detected_package=detected_package, connection=connection, status=status)


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
        return {
            "available": True,
            "available_zh": "是",
            "import_name": import_name,
            "distribution_name": version["distribution_name"],
            "version": version["version"],
            "message_zh": "当前 Python 环境可导入 Moomoo API 包。",
        }
    return {
        "available": False,
        "available_zh": "否",
        "import_name": None,
        "distribution_name": None,
        "version": None,
        "message_zh": "当前 Python 环境未发现可导入的 moomoo 或 futu API 包。",
    }


def probe_tcp_connection(host: str, port: int, timeout_seconds: float) -> dict:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout_seconds)):
            return {"connected": True, "error": None, "error_zh": None}
    except Exception as exc:
        return {"connected": False, "error": exc.__class__.__name__, "error_zh": _connection_error_zh(exc)}


def _status(*, package_available: bool, opend_connected: bool) -> str:
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
