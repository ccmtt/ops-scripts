from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


CAPTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "captures"


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _file_id(path: Path) -> str:
    return path.name


def _is_safe_pcap_name(file_id: str) -> bool:
    return "/" not in file_id and "\\" not in file_id and file_id.endswith(".pcap")


def list_capture_files() -> List[Dict[str, object]]:
    if not CAPTURE_DIR.exists():
        return []

    files = []
    for path in CAPTURE_DIR.glob("*.pcap"):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "id": _file_id(path),
                "filename": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "created_at": _iso_timestamp(stat.st_ctime),
                "modified_at": _iso_timestamp(stat.st_mtime),
            }
        )
    return sorted(files, key=lambda item: str(item["modified_at"]), reverse=True)


def get_capture_file(file_id: str) -> Optional[Dict[str, object]]:
    if not _is_safe_pcap_name(file_id):
        return None
    path = CAPTURE_DIR / file_id
    if not path.exists() or not path.is_file():
        return None
    stat = path.stat()
    return {
        "id": _file_id(path),
        "filename": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "created_at": _iso_timestamp(stat.st_ctime),
        "modified_at": _iso_timestamp(stat.st_mtime),
    }


def get_capture_file_path(file_id: str) -> Optional[Path]:
    file_info = get_capture_file(file_id)
    if not file_info:
        return None
    return Path(str(file_info["path"]))


def delete_capture_file(file_id: str) -> bool:
    path = get_capture_file_path(file_id)
    if not path:
        return False
    path.unlink()
    return True
