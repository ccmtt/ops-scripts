import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from app.checkers.capture_checker import check_capture_permission, get_capture_environment, run_short_capture
from app.core.config import settings
from app.schemas.capture import CaptureRunRequest


def _agent_url(path: str) -> str:
    assert settings.capture_agent_url
    return f"{settings.capture_agent_url.rstrip('/')}/{path.lstrip('/')}"


def _get_json(path: str, timeout: float = 10.0) -> Dict[str, Any]:
    with urllib.request.urlopen(_agent_url(path), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(path: str, payload: Dict[str, Any], timeout: float = 40.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        _agent_url(path),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_capture_environment_via_agent_or_local() -> Dict[str, Any]:
    if not settings.capture_agent_url:
        result = get_capture_environment()
        result["source"] = "local-backend"
        return result

    try:
        result = _get_json("/environment")
        result["source"] = "capture-agent"
        return result
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result = get_capture_environment()
        result["source"] = "local-backend"
        result.setdefault("warnings", []).append(f"capture-agent 不可用，已回退到本地后端: {exc}")
        return result


def run_capture_via_agent_or_local(request: CaptureRunRequest) -> Dict[str, Any]:
    payload = request.model_dump()
    if not settings.capture_agent_url:
        result = run_short_capture(
            request.interface,
            bpf_filter=request.bpf_filter,
            duration_seconds=request.duration_seconds,
            packet_count=request.packet_count,
        )
        result["source"] = "local-backend"
        return result

    try:
        result = _post_json("/run", payload, timeout=request.duration_seconds + 10)
        result["source"] = "capture-agent"
        return result
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result = run_short_capture(
            request.interface,
            bpf_filter=request.bpf_filter,
            duration_seconds=request.duration_seconds,
            packet_count=request.packet_count,
        )
        result["source"] = "local-backend"
        result["error"] = f"capture-agent 不可用，已回退到本地后端: {exc}; {result.get('error') or ''}".strip()
        return result


def check_capture_permission_via_agent_or_local(interface: Optional[str] = None) -> Dict[str, Any]:
    path = "/permission"
    if interface:
        path = f"{path}?interface={interface}"

    if not settings.capture_agent_url:
        result = check_capture_permission(interface)
        result["source"] = "local-backend"
        return result

    try:
        result = _get_json(path)
        result["source"] = "capture-agent"
        return result
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result = check_capture_permission(interface)
        result["source"] = "local-backend"
        result["error"] = f"capture-agent 不可用，已回退到本地后端: {exc}; {result.get('error') or ''}".strip()
        return result
