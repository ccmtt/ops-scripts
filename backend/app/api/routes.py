from fastapi import APIRouter

from app.core.config import settings
from app.checkers.capture_checker import get_capture_environment, run_short_capture
from app.checkers.domain_checker import run_domain_diagnostic
from app.checkers.network_checker import run_network_diagnostic
from app.schemas.capture import CaptureEnvironment, CaptureRunRequest, CaptureRunResult
from app.schemas.diagnostics import (
    DiagnosticRequest,
    DiagnosticResult,
    DomainDiagnosticRequest,
    NetworkDiagnosticRequest,
)
from app.schemas.module import ToolModule
from app.services.diagnostic_service import run_quick_diagnostic
from app.services.module_registry import list_modules

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@router.get("/modules", response_model=list[ToolModule])
def modules() -> list[ToolModule]:
    return list_modules()


@router.post("/diagnostics/quick", response_model=DiagnosticResult)
def quick_diagnostic(request: DiagnosticRequest) -> DiagnosticResult:
    return run_quick_diagnostic(request)


@router.post("/tools/domain")
def domain_diagnostic(request: DomainDiagnosticRequest) -> dict:
    return run_domain_diagnostic(
        request.domain,
        include_whois=request.include_whois,
        include_ssl=request.include_ssl,
        compare_dns=request.compare_dns,
    )


@router.post("/tools/network")
def network_diagnostic(request: NetworkDiagnosticRequest) -> dict:
    return run_network_diagnostic(
        request.host,
        port=request.port,
        timeout=request.timeout,
        include_ping=request.include_ping,
        include_trace=request.include_trace,
    )


@router.get("/tools/capture/environment", response_model=CaptureEnvironment)
def capture_environment() -> dict:
    return get_capture_environment()


@router.post("/tools/capture/run", response_model=CaptureRunResult)
def capture_run(request: CaptureRunRequest) -> dict:
    return run_short_capture(
        request.interface,
        bpf_filter=request.bpf_filter,
        duration_seconds=request.duration_seconds,
        packet_count=request.packet_count,
    )
