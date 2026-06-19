from typing import Any, Dict

from app.checkers.legacy_imports import load_legacy_module


def _status_from_errors(payload: Dict[str, Any]) -> str:
    errors = payload.get("errors") or []
    if errors and not payload.get("records"):
        return "error"
    if errors:
        return "warn"
    return "success"


def run_domain_diagnostic(
    domain: str,
    *,
    include_whois: bool = False,
    include_ssl: bool = True,
    compare_dns: bool = False,
) -> Dict[str, Any]:
    legacy = load_legacy_module("domain_tool.py")
    target = domain.strip()

    dns_result = legacy.resolve_with_dns(target)
    result: Dict[str, Any] = {
        "target": target,
        "dns": dns_result,
        "status": _status_from_errors(dns_result),
    }

    if include_ssl:
        result["ssl"] = legacy.get_ssl_info(target)

    if include_whois:
        result["whois"] = legacy.get_whois(target)

    if compare_dns:
        result["dns_compare"] = legacy.compare_dns_all(target)

    return result
