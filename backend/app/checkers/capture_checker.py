import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


CAPTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "captures"


def _run(command: list[str], timeout: float = 5.0) -> Dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {"command": command, "error": f"command not found: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"command": command, "error": f"timeout after {timeout}s"}


def _tool_status(name: str, version_args: list[str]) -> Dict[str, Any]:
    path = shutil.which(name)
    result: Dict[str, Any] = {
        "name": name,
        "available": path is not None,
        "path": path,
    }
    if path:
        version = _run([path, *version_args], timeout=3)
        result["version_output"] = version.get("stdout") or version.get("stderr") or version.get("error")
    return result


def _parse_tcpdump_interfaces(output: str) -> List[Dict[str, Any]]:
    interfaces: List[Dict[str, Any]] = []
    pattern = re.compile(r"^(?P<index>\d+)\.(?P<name>[^\s]+)(?:\s+\[(?P<flags>[^\]]+)\])?")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        flags = [flag.strip() for flag in (match.group("flags") or "").split(",") if flag.strip()]
        interfaces.append(
            {
                "index": int(match.group("index")),
                "name": match.group("name"),
                "flags": flags,
                "source": "tcpdump",
            }
        )
    return interfaces


def _interfaces_from_ifconfig() -> List[Dict[str, Any]]:
    if platform.system() == "Windows":
        return []
    result = _run(["ifconfig", "-l"], timeout=3)
    if result.get("returncode") != 0:
        return []
    names = result.get("stdout", "").split()
    return [{"index": idx + 1, "name": name, "flags": [], "source": "ifconfig"} for idx, name in enumerate(names)]


def get_capture_environment() -> Dict[str, Any]:
    tcpdump = _tool_status("tcpdump", ["--version"])
    tshark = _tool_status("tshark", ["--version"])

    interfaces: List[Dict[str, Any]] = []
    interface_error = None
    if tcpdump.get("path"):
        result = _run([tcpdump["path"], "--list-interfaces"], timeout=5)
        if result.get("returncode") == 0:
            interfaces = _parse_tcpdump_interfaces(result.get("stdout", ""))
        else:
            interface_error = result.get("stderr") or result.get("error") or "tcpdump interface listing failed"

    if not interfaces:
        interfaces = _interfaces_from_ifconfig()

    can_list_interfaces = bool(interfaces)
    ready_for_capture = bool(tcpdump.get("available") and can_list_interfaces)

    warnings = []
    if not tcpdump.get("available"):
        warnings.append("未检测到 tcpdump，无法执行本机抓包。")
    if not tshark.get("available"):
        warnings.append("未检测到 tshark，深度协议解析能力暂不可用。")
    if ready_for_capture:
        warnings.append("真正开始抓包通常需要管理员权限，后续应通过受控 agent 执行。")

    return {
        "system": platform.system(),
        "tools": {
            "tcpdump": tcpdump,
            "tshark": tshark,
        },
        "interfaces": interfaces,
        "can_list_interfaces": can_list_interfaces,
        "ready_for_capture": ready_for_capture,
        "interface_error": interface_error,
        "warnings": warnings,
    }


def _safe_capture_name(interface: str) -> str:
    safe_interface = re.sub(r"[^a-zA-Z0-9_.-]", "_", interface)
    return f"capture_{safe_interface}_{int(time.time())}.pcap"


def _summarize_pcap(tcpdump_path: str, pcap_path: Path, limit: int = 40) -> List[str]:
    result = _run([tcpdump_path, "-nn", "-tttt", "-r", str(pcap_path)], timeout=8)
    output = result.get("stdout") or result.get("stderr") or ""
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[:limit]


def run_short_capture(
    interface: str,
    *,
    bpf_filter: Optional[str],
    duration_seconds: int,
    packet_count: int,
) -> Dict[str, Any]:
    env = get_capture_environment()
    tcpdump = env["tools"]["tcpdump"]
    if not tcpdump.get("available") or not tcpdump.get("path"):
        return {
            "status": "error",
            "interface": interface,
            "bpf_filter": bpf_filter,
            "pcap_path": None,
            "packet_count": 0,
            "summary_lines": [],
            "command": [],
            "error": "未检测到 tcpdump，无法抓包。",
        }

    known_interfaces = {item["name"] for item in env.get("interfaces", [])}
    if known_interfaces and interface not in known_interfaces:
        return {
            "status": "error",
            "interface": interface,
            "bpf_filter": bpf_filter,
            "pcap_path": None,
            "packet_count": 0,
            "summary_lines": [],
            "command": [],
            "error": f"网卡不存在或不可用: {interface}",
        }

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    pcap_path = CAPTURE_DIR / _safe_capture_name(interface)
    command = [
        tcpdump["path"],
        "-i",
        interface,
        "-c",
        str(packet_count),
        "-G",
        str(duration_seconds),
        "-W",
        "1",
        "-w",
        str(pcap_path),
    ]
    if bpf_filter:
        command.extend(bpf_filter.split())

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=duration_seconds + 5,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "interface": interface,
            "bpf_filter": bpf_filter,
            "pcap_path": str(pcap_path),
            "packet_count": 0,
            "summary_lines": [],
            "command": command,
            "error": f"抓包超时，超过 {duration_seconds + 5}s。",
        }

    stderr = proc.stderr.strip()
    pcap_exists = pcap_path.exists() and pcap_path.stat().st_size > 0
    if proc.returncode != 0 or not pcap_exists:
        error = stderr or "抓包失败，未生成 pcap 文件。"
        if "permission denied" in error.lower() or "you don't have permission" in error.lower():
            error = f"{error} 请使用具备抓包权限的 agent 或以管理员权限运行后端。"
        return {
            "status": "error",
            "interface": interface,
            "bpf_filter": bpf_filter,
            "pcap_path": str(pcap_path) if pcap_path.exists() else None,
            "packet_count": 0,
            "summary_lines": [],
            "command": command,
            "returncode": proc.returncode,
            "error": error,
            "stderr": stderr,
        }

    summary_lines = _summarize_pcap(tcpdump["path"], pcap_path)
    return {
        "status": "success",
        "interface": interface,
        "bpf_filter": bpf_filter,
        "pcap_path": str(pcap_path),
        "packet_count": len(summary_lines),
        "summary_lines": summary_lines,
        "command": command,
        "returncode": proc.returncode,
        "stderr": stderr,
    }


def check_capture_permission(interface: Optional[str] = None) -> Dict[str, Any]:
    env = get_capture_environment()
    tcpdump = env["tools"]["tcpdump"]
    if not tcpdump.get("available") or not tcpdump.get("path"):
        return {
            "interface": interface,
            "can_capture": False,
            "status": "missing-tcpdump",
            "error": "未检测到 tcpdump。",
            "command": [],
        }

    selected_interface = interface
    if not selected_interface:
        for item in env.get("interfaces", []):
            flags = set(item.get("flags", []))
            if "Up" in flags and item.get("name") != "lo0":
                selected_interface = item.get("name")
                break
        if not selected_interface and env.get("interfaces"):
            selected_interface = env["interfaces"][0]["name"]

    if not selected_interface:
        return {
            "interface": None,
            "can_capture": False,
            "status": "missing-interface",
            "error": "未发现可用网卡。",
            "command": [],
        }

    command = [tcpdump["path"], "-i", selected_interface, "-c", "1", "-w", "/dev/null"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired:
        return {
            "interface": selected_interface,
            "can_capture": True,
            "status": "capture-started",
            "command": command,
            "error": None,
        }

    stderr = proc.stderr.strip()
    can_capture = proc.returncode == 0
    status = "ok" if can_capture else "permission-denied"
    error = None if can_capture else stderr or "抓包权限检查失败。"
    return {
        "interface": selected_interface,
        "can_capture": can_capture,
        "status": status,
        "error": error,
        "command": command,
        "returncode": proc.returncode,
    }
