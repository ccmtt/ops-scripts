import os
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Ops Workbench"
    app_version: str = "0.1.0"
    environment: str = "development"
    capture_agent_url: Optional[str] = os.getenv("CAPTURE_AGENT_URL")


settings = Settings()
