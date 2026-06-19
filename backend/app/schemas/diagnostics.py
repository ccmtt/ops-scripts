from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


DiagnosticStatus = Literal["success", "warn", "error", "info"]


class DiagnosticRequest(BaseModel):
    target: str
    timeout: float = 3.0
    include_trace: bool = False


class DiagnosticResult(BaseModel):
    module_key: str
    target: str
    status: DiagnosticStatus
    summary: str
    suggestions: List[str]
    raw_data: Dict[str, Any]


class DomainDiagnosticRequest(BaseModel):
    domain: str
    include_whois: bool = False
    include_ssl: bool = True
    compare_dns: bool = False


class NetworkDiagnosticRequest(BaseModel):
    host: str
    port: Optional[int] = None
    timeout: float = 3.0
    include_ping: bool = True
    include_trace: bool = False
