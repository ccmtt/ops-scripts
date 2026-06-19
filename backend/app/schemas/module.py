from typing import List, Literal

from pydantic import BaseModel


ModuleStatus = Literal["planned", "active", "experimental"]


class ToolModule(BaseModel):
    key: str
    name: str
    category: str
    summary: str
    status: ModuleStatus
    entry: str
    capabilities: List[str]
