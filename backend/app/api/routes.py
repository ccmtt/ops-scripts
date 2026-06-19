from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.checkers.domain_checker import run_domain_diagnostic
from app.checkers.network_checker import run_network_diagnostic
from app.schemas.capture import (
    CaptureEnvironment,
    CaptureFile,
    CapturePermissionCheck,
    CaptureRunRequest,
    CaptureRunResult,
    CaptureTask,
    OperationLog,
)
from app.services.capture_files import delete_capture_file, get_capture_file, get_capture_file_path, list_capture_files
from app.schemas.diagnostics import (
    DiagnosticRequest,
    DiagnosticResult,
    DomainDiagnosticRequest,
    NetworkDiagnosticRequest,
)
from app.schemas.module import ToolModule
from app.services.capture_proxy import (
    check_capture_permission_via_agent_or_local,
    get_capture_environment_via_agent_or_local,
    run_capture_via_agent_or_local,
)
from app.services.capture_tasks import create_capture_task, get_capture_task, list_capture_tasks
from app.services.diagnostic_service import run_quick_diagnostic
from app.services.module_registry import list_modules
from app.services.operation_logs import list_operation_logs, write_operation_log

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
    result = get_capture_environment_via_agent_or_local()
    write_operation_log(
        "capture.environment",
        status="success",
        message="检查抓包环境",
        metadata={"source": result.get("source"), "interfaces": len(result.get("interfaces", []))},
    )
    return result


@router.get("/tools/capture/permission", response_model=CapturePermissionCheck)
def capture_permission(interface: Optional[str] = None) -> dict:
    result = check_capture_permission_via_agent_or_local(interface)
    write_operation_log(
        "capture.permission",
        status="success" if result.get("can_capture") else "failed",
        message="检查抓包权限",
        metadata={"interface": result.get("interface"), "source": result.get("source"), "status": result.get("status")},
    )
    return result


@router.post("/tools/capture/run", response_model=CaptureRunResult)
def capture_run(request: CaptureRunRequest) -> dict:
    result = run_capture_via_agent_or_local(request)
    write_operation_log(
        "capture.run",
        status="success" if result.get("status") == "success" else "failed",
        message="执行短时抓包",
        metadata={"interface": request.interface, "pcap_path": result.get("pcap_path"), "source": result.get("source")},
    )
    return result


@router.post("/tools/capture/tasks", response_model=CaptureTask)
def capture_task_create(request: CaptureRunRequest) -> dict:
    task = create_capture_task(request)
    write_operation_log(
        "capture.task.create",
        status=task.get("status", "unknown"),
        message="创建抓包任务",
        metadata={"task_id": task.get("id"), "interface": task.get("interface"), "source": task.get("source")},
    )
    return task


@router.get("/tools/capture/tasks", response_model=list[CaptureTask])
def capture_task_list(limit: int = 20) -> list[dict]:
    result = list_capture_tasks(limit=max(1, min(limit, 100)))
    write_operation_log(
        "capture.task.list",
        status="success",
        message="查看抓包任务列表",
        metadata={"count": len(result)},
    )
    return result


@router.get("/tools/capture/tasks/{task_id}", response_model=CaptureTask)
def capture_task_get(task_id: str) -> dict:
    task = get_capture_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="capture task not found")
    return task


@router.get("/tools/capture/files", response_model=list[CaptureFile])
def capture_file_list() -> list[dict]:
    result = list_capture_files()
    write_operation_log(
        "capture.file.list",
        status="success",
        message="查看 pcap 文件列表",
        metadata={"count": len(result)},
    )
    return result


@router.get("/tools/capture/files/{file_id}", response_model=CaptureFile)
def capture_file_get(file_id: str) -> dict:
    file_info = get_capture_file(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="capture file not found")
    return file_info


@router.get("/tools/capture/files/{file_id}/download")
def capture_file_download(file_id: str) -> FileResponse:
    path = get_capture_file_path(file_id)
    if not path:
        write_operation_log(
            "capture.file.download",
            status="failed",
            message="下载 pcap 文件失败",
            metadata={"file_id": file_id},
        )
        raise HTTPException(status_code=404, detail="capture file not found")
    write_operation_log(
        "capture.file.download",
        status="success",
        message="下载 pcap 文件",
        metadata={"file_id": file_id, "path": str(path)},
    )
    return FileResponse(path, filename=path.name, media_type="application/vnd.tcpdump.pcap")


@router.delete("/tools/capture/files/{file_id}")
def capture_file_delete(file_id: str) -> dict[str, str]:
    if not delete_capture_file(file_id):
        write_operation_log(
            "capture.file.delete",
            status="failed",
            message="删除 pcap 文件失败",
            metadata={"file_id": file_id},
        )
        raise HTTPException(status_code=404, detail="capture file not found")
    write_operation_log(
        "capture.file.delete",
        status="success",
        message="删除 pcap 文件",
        metadata={"file_id": file_id},
    )
    return {"status": "deleted", "file_id": file_id}


@router.get("/operation-logs", response_model=list[OperationLog])
def operation_log_list(limit: int = 50, module: Optional[str] = None) -> list[dict]:
    return list_operation_logs(limit=max(1, min(limit, 200)), module=module)
