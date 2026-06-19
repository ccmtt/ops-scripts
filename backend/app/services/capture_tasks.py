import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.capture import CaptureRunRequest
from app.services.capture_proxy import run_capture_via_agent_or_local


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TASK_FILE = DATA_DIR / "capture_tasks.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _append_task(task: Dict[str, Any]) -> None:
    _ensure_data_dir()
    with TASK_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(task, ensure_ascii=False) + "\n")


def _read_tasks() -> List[Dict[str, Any]]:
    if not TASK_FILE.exists():
        return []
    tasks: List[Dict[str, Any]] = []
    with TASK_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tasks


def create_capture_task(request: CaptureRunRequest) -> Dict[str, Any]:
    created_at = _now()
    task_id = uuid.uuid4().hex
    result = run_capture_via_agent_or_local(request)
    finished_at = _now()
    status = "success" if result.get("status") == "success" else "failed"

    task = {
        "id": task_id,
        "status": status,
        "interface": request.interface,
        "bpf_filter": request.bpf_filter,
        "duration_seconds": request.duration_seconds,
        "packet_count_limit": request.packet_count,
        "captured_packet_count": result.get("packet_count", 0),
        "pcap_path": result.get("pcap_path"),
        "summary_lines": result.get("summary_lines", []),
        "command": result.get("command", []),
        "error": result.get("error"),
        "stderr": result.get("stderr"),
        "source": result.get("source"),
        "created_at": created_at,
        "started_at": created_at,
        "finished_at": finished_at,
    }
    _append_task(task)
    return task


def list_capture_tasks(limit: int = 20) -> List[Dict[str, Any]]:
    tasks = _read_tasks()
    return list(reversed(tasks))[:limit]


def get_capture_task(task_id: str) -> Optional[Dict[str, Any]]:
    for task in reversed(_read_tasks()):
        if task.get("id") == task_id:
            return task
    return None
