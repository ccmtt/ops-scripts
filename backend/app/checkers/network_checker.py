from typing import Any, Dict, Optional

from app.checkers.legacy_imports import load_legacy_module


def run_network_diagnostic(
    host: str,
    *,
    port: Optional[int] = None,
    timeout: float = 3.0,
    include_ping: bool = True,
    include_trace: bool = False,
) -> Dict[str, Any]:
    legacy = load_legacy_module("ip_check.py")
    target = host.strip()

    result: Dict[str, Any] = {
        "target": target,
        "status": "success",
    }

    try:
        result["ip_classification"] = legacy.classify_ip(target)
    except ValueError:
        result["ip_classification"] = {"error": "目标不是直接 IPv4/IPv6 地址，跳过 IP 分类"}

    if include_ping:
        result["ping"] = legacy.ping_host(target, 2, timeout)

    if port is not None:
        result["tcp"] = legacy.scan_tcp_port(target, port, timeout)
    else:
        result["tcp_80"] = legacy.scan_tcp_port(target, 80, timeout)
        result["tcp_443"] = legacy.scan_tcp_port(target, 443, timeout)

    if include_trace:
        result["trace"] = legacy.trace_route(target, timeout)

    if any(item.get("error") for item in result.values() if isinstance(item, dict)):
        result["status"] = "warn"

    return result
