from urllib.parse import urlparse

from app.checkers.domain_checker import run_domain_diagnostic
from app.checkers.network_checker import run_network_diagnostic
from app.schemas.diagnostics import DiagnosticRequest, DiagnosticResult


def detect_target_type(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return "url"
    if ":" in target and "/" not in target and " " not in target:
        return "host_port"
    if all(part.isdigit() for part in target.split(".")) and target.count(".") == 3:
        return "ip"
    return "domain"


def run_quick_diagnostic(request: DiagnosticRequest) -> DiagnosticResult:
    target = request.target.strip()
    target_type = detect_target_type(target)

    summaries = {
        "url": "已识别为 URL，并执行域名接入基础检查。",
        "host_port": "已识别为主机与端口，并执行 TCP 探测。",
        "ip": "已识别为 IP，并执行网络基础检查。",
        "domain": "已识别为域名，并执行 DNS 与 TLS 基础检查。",
    }

    raw_data = {"target_type": target_type}

    if target_type == "url":
        parsed = urlparse(target)
        host = parsed.hostname or target
        raw_data["domain_diagnostic"] = run_domain_diagnostic(host, include_ssl=parsed.scheme == "https")
    elif target_type == "domain":
        raw_data["domain_diagnostic"] = run_domain_diagnostic(target)
    elif target_type == "host_port":
        host, _, port_text = target.rpartition(":")
        port = int(port_text) if port_text.isdigit() else None
        raw_data["network_diagnostic"] = run_network_diagnostic(
            host or target,
            port=port,
            timeout=request.timeout,
            include_ping=request.include_trace,
            include_trace=request.include_trace,
        )
    elif target_type == "ip":
        raw_data["network_diagnostic"] = run_network_diagnostic(
            target,
            timeout=request.timeout,
            include_trace=request.include_trace,
        )

    return DiagnosticResult(
        module_key="quick-diagnostic",
        target=target,
        status="info",
        summary=summaries[target_type],
        suggestions=[
            "可从功能区进入对应专项模块查看更完整结果。",
            "后续可将结果持久化为历史任务。",
        ],
        raw_data=raw_data,
    )
