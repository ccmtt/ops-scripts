from fastapi import FastAPI
from typing import Optional

from app.checkers.capture_checker import check_capture_permission, get_capture_environment, run_short_capture
from app.schemas.capture import CaptureEnvironment, CapturePermissionCheck, CaptureRunRequest, CaptureRunResult

app = FastAPI(title="Ops Capture Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "Ops Capture Agent", "version": "0.1.0"}


@app.get("/environment", response_model=CaptureEnvironment)
def environment() -> dict:
    return get_capture_environment()


@app.get("/permission", response_model=CapturePermissionCheck)
def permission(interface: Optional[str] = None) -> dict:
    return check_capture_permission(interface)


@app.post("/run", response_model=CaptureRunResult)
def run_capture(request: CaptureRunRequest) -> dict:
    return run_short_capture(
        request.interface,
        bpf_filter=request.bpf_filter,
        duration_seconds=request.duration_seconds,
        packet_count=request.packet_count,
    )
