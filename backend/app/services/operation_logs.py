import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LOG_FILE = DATA_DIR / "operation_logs.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_operation_log(
    action: str,
    *,
    status: str,
    message: str,
    module: str = "capture",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": uuid.uuid4().hex,
        "timestamp": _now(),
        "module": module,
        "action": action,
        "status": status,
        "message": message,
        "metadata": metadata or {},
    }
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def list_operation_logs(limit: int = 50, module: Optional[str] = None) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with LOG_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if module and row.get("module") != module:
                continue
            rows.append(row)
    return list(reversed(rows))[:limit]
