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
