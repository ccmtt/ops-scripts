from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CaptureToolStatus(BaseModel):
    name: str
    available: bool
    path: Optional[str] = None
    version_output: Optional[str] = None


class CaptureInterface(BaseModel):
    index: int
    name: str
    flags: List[str]
    source: str


class CaptureEnvironment(BaseModel):
    system: str
    tools: Dict[str, CaptureToolStatus]
    interfaces: List[CaptureInterface]
    can_list_interfaces: bool
    ready_for_capture: bool
    interface_error: Optional[str] = None
    warnings: List[str]
    source: Optional[str] = None


class CapturePermissionCheck(BaseModel):
    interface: Optional[str] = None
    can_capture: bool
    status: str
    error: Optional[str] = None
    command: List[str]
    returncode: Optional[int] = None
    source: Optional[str] = None


class CaptureRunRequest(BaseModel):
    interface: str = Field(..., min_length=1, max_length=64)
    bpf_filter: Optional[str] = Field(default=None, max_length=256)
    duration_seconds: int = Field(default=5, ge=1, le=30)
    packet_count: int = Field(default=50, ge=1, le=500)


class CaptureRunResult(BaseModel):
    status: str
    interface: str
    bpf_filter: Optional[str]
    pcap_path: Optional[str] = None
    packet_count: int
    summary_lines: List[str]
    command: List[str]
    returncode: Optional[int] = None
    error: Optional[str] = None
    stderr: Optional[str] = None
    source: Optional[str] = None


class CaptureTask(BaseModel):
    id: str
    status: str
    interface: str
    bpf_filter: Optional[str]
    duration_seconds: int
    packet_count_limit: int
    captured_packet_count: int
    pcap_path: Optional[str] = None
    summary_lines: List[str]
    command: List[str]
    error: Optional[str] = None
    stderr: Optional[str] = None
    source: Optional[str] = None
    created_at: str
    started_at: str
    finished_at: str


class CaptureFile(BaseModel):
    id: str
    filename: str
    path: str
    size_bytes: int
    created_at: str
    modified_at: str


class OperationLog(BaseModel):
    id: str
    timestamp: str
    module: str
    action: str
    status: str
    message: str
    metadata: Dict[str, Any]
