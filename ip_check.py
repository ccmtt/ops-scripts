#!/usr/bin/env python3
"""
交互式 IP 检查与端口扫描工具

支持: Ping / TCP端口 / 批量端口 / 网段扫描 / Traceroute / 综合诊断
"""

import argparse
import ipaddress
import json
import locale
import math
import platform
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


# ========== 工具函数 ==========

def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: List[str], timeout: float) -> Dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "elapsed_seconds": round(time.time() - started, 3),
        }
    except FileNotFoundError:
        return {
            "command": command,
            "error": f"command not found: {command[0]}",
            "elapsed_seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "error": f"timeout after {timeout}s",
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            "elapsed_seconds": round(time.time() - started, 3),
        }


def _enqueue_stream(stream: Any, output_queue: "queue.Queue[Tuple[str, str]]", stream_name: str) -> None:
    try:
        for line in iter(stream.readline, ""):
            output_queue.put((stream_name, line.rstrip("\n")))
    finally:
        stream.close()


def run_command_streaming(command: List[str], timeout: float) -> Dict[str, Any]:
    started = time.time()
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    output_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError:
        return {
            "command": command,
            "error": f"command not found: {command[0]}",
            "elapsed_seconds": round(time.time() - started, 3),
        }

    assert proc.stdout is not None
    assert proc.stderr is not None
    threads = [
        threading.Thread(target=_enqueue_stream, args=(proc.stdout, output_queue, "stdout"), daemon=True),
        threading.Thread(target=_enqueue_stream, args=(proc.stderr, output_queue, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    deadline = started + timeout
    while True:
        remaining = max(0.0, deadline - time.time())
        try:
            stream_name, line = output_queue.get(timeout=min(0.2, remaining) if remaining else 0.05)
            if stream_name == "stdout":
                stdout_lines.append(line)
                print(f"  {line}", flush=True)
            else:
                stderr_lines.append(line)
                print(f"  {line}", flush=True)
        except queue.Empty:
            pass

        if proc.poll() is not None:
            while True:
                try:
                    stream_name, line = output_queue.get_nowait()
                except queue.Empty:
                    break
                if stream_name == "stdout":
                    stdout_lines.append(line)
                    print(f"  {line}", flush=True)
                else:
                    stderr_lines.append(line)
                    print(f"  {line}", flush=True)
            break

        if time.time() >= deadline:
            timed_out = True
            proc.kill()
            proc.wait()
            break

    for thread in threads:
        thread.join(timeout=0.2)

    result: Dict[str, Any] = {
        "command": command,
        "returncode": proc.returncode,
        "stdout": "\n".join(stdout_lines).strip(),
        "stderr": "\n".join(stderr_lines).strip(),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    if timed_out:
        result["error"] = f"timeout after {timeout}s"
    return result


def parse_host_port(target: str, default_port: int) -> Tuple[str, int]:
    """解析 IP:PORT 字符串"""
    if ":" in target and target.count(":") == 1:
        host, port = target.rsplit(":", 1)
        return host, _parse_port(port, default_port)
    return target, default_port


def format_host_port(host: str, port: int) -> str:
    return f"{host}:{port}"


def normalize_ip(ip_text: str) -> Optional[str]:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return None
    if ip.version != 4:
        return None
    return str(ip)


def normalize_ip_or_print(ip_text: str) -> Optional[str]:
    ip = normalize_ip(ip_text)
    if ip:
        return ip
    print("  输入不是合法 IPv4。域名解析请使用 domain_tool.py。")
    return None


def _parse_port(value: str, default_port: int) -> int:
    try:
        port = int(value)
    except ValueError:
        return default_port
    if 1 <= port <= 65535:
        return port
    return default_port


def ask_int(prompt: str, default: int, min_value: int, max_value: int) -> int:
    while True:
        val = input(f"{prompt} (默认 {default}): ").strip()
        if not val:
            return default
        try:
            parsed = int(val)
        except ValueError:
            print("  请输入整数")
            continue
        if min_value <= parsed <= max_value:
            return parsed
        print(f"  请输入 {min_value}-{max_value} 之间的整数")


def ask_float(prompt: str, default: float, min_value: float, max_value: float) -> float:
    while True:
        val = input(f"{prompt} (默认 {default}): ").strip()
        if not val:
            return default
        try:
            parsed = float(val)
        except ValueError:
            print("  请输入数字")
            continue
        if min_value <= parsed <= max_value:
            return parsed
        print(f"  请输入 {min_value}-{max_value} 之间的数字")


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "-"
    return str(value)


def brief_output(result: Dict[str, Any], max_lines: int = 8) -> None:
    """打印命令输出摘要"""
    if result.get("error"):
        print(f"  error: {result.get('error')}")
    if "returncode" in result:
        print(f"  returncode: {result.get('returncode')}")
    stdout = result.get("stdout")
    stderr = result.get("stderr")
    if stdout:
        lines = stdout.splitlines()
        for line in lines[:max_lines]:
            print(f"  {line}")
        if len(lines) > max_lines:
            print(f"  ... ({len(lines) - max_lines} more lines)")
    elif stderr:
        print(f"  stderr: {stderr}")
    else:
        print(f"  (无输出)")
    if result.get("elapsed_seconds") is not None:
        print(f"  elapsed: {result.get('elapsed_seconds')}s")


# ========== IP 检测 ==========

PUBLIC_IP_ENDPOINTS = {
    "ipv4": [
        "https://api.ipify.org?format=json",
        "https://ipv4.icanhazip.com",
        "https://ifconfig.me/ip",
    ],
}

GEO_LOOKUP_URL = "https://ipwho.is/{ip}"


def get_public_ip(version: str, timeout: float) -> Tuple[Optional[str], Optional[str], List[str]]:
    errors: List[str] = []
    expected_version = 4 if version == "ipv4" else 6
    for url in PUBLIC_IP_ENDPOINTS[version]:
        try:
            ip = _parse_public_ip_response(_request_text(url, timeout))
            if ip:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == expected_version:
                    return ip, url, errors
                errors.append(f"{url}: got IPv{ip_obj.version}, expected IPv{expected_version}")
            else:
                errors.append(f"{url}: invalid response")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    return None, None, errors


def _request_text(url: str, timeout: float) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ip-check/1.0 (+https://python.org)",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(8192).decode("utf-8", errors="replace").strip()


def _request_json(url: str, timeout: float) -> Dict[str, Any]:
    return json.loads(_request_text(url, timeout))


def _parse_public_ip_response(text: str) -> Optional[str]:
    text = text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        for key in ("ip", "query", "address"):
            value = payload.get(key)
            if isinstance(value, str):
                text = value.strip()
                break
    first_line = text.splitlines()[0].strip()
    try:
        return str(ipaddress.ip_address(first_line))
    except ValueError:
        return None


def get_outbound_local_ip(family: socket.AddressFamily, timeout: float) -> Optional[str]:
    target = ("8.8.8.8", 80)
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.connect(target)
        address = sock.getsockname()[0]
        return str(ipaddress.ip_address(address))
    except OSError:
        return None
    finally:
        sock.close()


def get_hostname_addresses() -> List[str]:
    addresses = set()
    names = {socket.gethostname(), socket.getfqdn()}
    for name in names:
        try:
            infos = socket.getaddrinfo(name, None)
        except socket.gaierror:
            continue
        for info in infos:
            raw = info[4][0]
            try:
                ip = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if not ip.is_loopback:
                addresses.add(str(ip))
    return sorted(addresses, key=lambda value: (":" in value, value))


def classify_ip(ip_text: str) -> Dict[str, Any]:
    ip = ipaddress.ip_address(ip_text)
    labels = []
    for label, enabled in [
        ("private", ip.is_private),
        ("global", ip.is_global),
        ("loopback", ip.is_loopback),
        ("link_local", ip.is_link_local),
        ("multicast", ip.is_multicast),
        ("reserved", ip.is_reserved),
        ("unspecified", ip.is_unspecified),
    ]:
        if enabled:
            labels.append(label)
    reverse_dns = None
    try:
        reverse_dns = socket.gethostbyaddr(ip_text)[0]
    except (socket.herror, socket.gaierror, OSError):
        pass
    return {"ip": str(ip), "version": ip.version, "network_type": labels, "reverse_dns": reverse_dns}


def get_outbound_local_ip_for_target(address: str, port: int, timeout: float) -> Optional[str]:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip.version != 4:
        return None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.connect((address, port))
        return str(ipaddress.ip_address(sock.getsockname()[0]))
    except OSError:
        return None
    finally:
        sock.close()


def summarize_ping(result: Dict[str, Any]) -> str:
    if result.get("returncode") == 0:
        return "可达"
    if result.get("error"):
        return f"异常: {result.get('error')}"
    return "不可达或被禁 ICMP"


def print_ip_classification(address: str, prefix: str = "  ") -> None:
    try:
        ip_cls = classify_ip(address)
    except ValueError:
        return
    print(f"{prefix}{address}: IPv{ip_cls.get('version')} / {format_value(ip_cls.get('network_type'))}")
    if ip_cls.get("reverse_dns"):
        print(f"{prefix}  反向DNS: {ip_cls.get('reverse_dns')}")


def lookup_geo(ip_text: str, timeout: float) -> Dict[str, Any]:
    ip = ipaddress.ip_address(ip_text)
    if not ip.is_global:
        return {"enabled": False, "reason": "非公网 IP，跳过 Geo 查询"}
    url = GEO_LOOKUP_URL.format(ip=urllib.parse.quote(str(ip), safe=""))
    try:
        payload = _request_json(url, timeout)
    except Exception as exc:
        return {"enabled": True, "error": str(exc)}
    if payload.get("success") is False:
        return {"enabled": True, "error": payload.get("message") or "lookup failed"}
    return {
        "enabled": True,
        "country": payload.get("country"),
        "region": payload.get("region"),
        "city": payload.get("city"),
        "timezone": payload.get("timezone", {}).get("id") if isinstance(payload.get("timezone"), dict) else payload.get("timezone"),
        "isp": payload.get("isp"),
        "org": payload.get("connection", {}).get("org") if isinstance(payload.get("connection"), dict) else None,
        "asn": payload.get("connection", {}).get("asn") if isinstance(payload.get("connection"), dict) else None,
        "lat": payload.get("latitude"),
        "lon": payload.get("longitude"),
    }


def print_geo(geo: Dict[str, Any]) -> None:
    if not geo:
        return
    if geo.get("enabled") is False:
        print(f"  geo: {geo.get('reason')}")
        return
    if geo.get("error"):
        print(f"  geo_error: {geo.get('error')}")
        return
    loc = [geo.get("country"), geo.get("region"), geo.get("city")]
    print(f"  location: {format_value([x for x in loc if x])}")
    print(f"  timezone: {format_value(geo.get('timezone'))}")
    print(f"  isp: {format_value(geo.get('isp'))}")
    print(f"  org: {format_value(geo.get('org'))}")
    print(f"  asn: {format_value(geo.get('asn'))}")
    print(f"  lat_lon: {format_value(geo.get('lat'))}, {format_value(geo.get('lon'))}")


# ========== Ping ==========

def ping_host(host: str, count: int, timeout: float) -> Dict[str, Any]:
    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", str(count), "-w", str(max(1, int(timeout * 1000))), host]
    elif system == "darwin":
        command = ["ping", "-c", str(count), "-W", str(max(1, int(math.ceil(timeout * 1000)))), host]
    else:
        command = ["ping", "-c", str(count), "-W", str(max(1, int(math.ceil(timeout)))), host]
    return run_command(command, max(timeout * count + 2, timeout + 2))


# ========== TCP ==========

def tcp_check(target: str, timeout: float) -> Dict[str, Any]:
    host, port = parse_host_port(target, 80)
    started = time.time()
    result: Dict[str, Any] = {"target": target, "host": host, "port": port}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            result["local_address"] = f"{sock.getsockname()[0]}:{sock.getsockname()[1]}"
            result["remote_address"] = f"{sock.getpeername()[0]}:{sock.getpeername()[1]}"
            result["ok"] = True
    except OSError as exc:
        result["ok"] = False
        result["error"] = str(exc)
    result["elapsed_seconds"] = round(time.time() - started, 3)
    return result


def nmap_tcp_check(host: str, port: int, timeout: float) -> Dict[str, Any]:
    command = [
        "nmap",
        "-sT",
        "-Pn",
        "-n",
        "--host-timeout", f"{max(1, int(math.ceil(timeout + 2)))}s",
        "-p", str(port),
        host,
    ]
    result = run_command(command, max(timeout + 5, 8))
    result.update({"target": format_host_port(host, port), "host": host, "port": port, "scanner": "nmap"})
    state = parse_nmap_port_state(result.get("stdout", ""), port)
    if state:
        result["port_state"] = state
        result["ok"] = state == "open"
    return result


def parse_nmap_port_state(output: str, port: int) -> Optional[str]:
    prefix = f"{port}/tcp"
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            parts = stripped.split()
            if len(parts) >= 2:
                return parts[1]
    return None


def scan_tcp_port(host: str, port: int, timeout: float) -> Dict[str, Any]:
    if command_exists("nmap"):
        result = nmap_tcp_check(host, port, timeout)
        if result.get("port_state"):
            return result

    result = tcp_check(format_host_port(host, port), timeout)
    result["scanner"] = "python-connect"
    state, reason = classify_tcp_port(result)
    result["port_state"] = state
    result["port_reason"] = reason
    return result


def classify_tcp_port(result: Dict[str, Any]) -> Tuple[str, str]:
    if result.get("port_state"):
        state = str(result["port_state"])
        reasons = {
            "open": "TCP 端口明确开放",
            "closed": "目标明确拒绝连接，主机可达但端口未开放",
            "filtered": "探测被过滤或无响应，无法确认开关",
            "open|filtered": "端口可能开放也可能被过滤，无法确认",
            "closed|filtered": "端口可能关闭也可能被过滤，无法确认",
            "unfiltered": "端口可达，但开放状态未确认",
        }
        return state, reasons.get(state, result.get("port_reason") or "未知状态")

    if result.get("ok"):
        return "open", "TCP 握手成功，端口明确开放"

    error = str(result.get("error") or "").lower()
    if "refused" in error:
        return "closed", "目标明确拒绝连接，主机可达但端口未开放"
    if "timed out" in error or "timeout" in error:
        return "filtered", "探测超时，无法确认开关；常见于防火墙/安全组丢弃"
    if "network is unreachable" in error or "no route" in error:
        return "unreachable", "本机到目标无可用路由"
    if "host is down" in error:
        return "unreachable", "目标主机不可达"
    return "unknown", result.get("error") or "未知状态"


# ========== Traceroute ==========

def build_trace_command(host: str) -> Tuple[List[str], float]:
    system = platform.system().lower()
    max_hops = 20
    hop_timeout = 2
    probes_per_hop = 1
    if system == "windows":
        probes_per_hop = 3
        command = ["tracert", "-d", "-w", str(max(1, int(hop_timeout * 1000))), "-h", str(max_hops), host]
    elif system == "darwin":
        if command_exists("traceroute"):
            command = [
                "traceroute",
                "-n",
                "-q", str(probes_per_hop),
                "-w", str(max(1, int(hop_timeout))),
                "-m", str(max_hops),
                host,
            ]
        else:
            command = ["tracepath", "-m", str(max_hops), host]
    else:
        binary = "traceroute" if command_exists("traceroute") else "tracepath"
        if binary == "traceroute":
            command = [
                binary,
                "-n",
                "-q", str(probes_per_hop),
                "-w", str(max(1, int(hop_timeout))),
                "-m", str(max_hops),
                host,
            ]
        else:
            command = [binary, "-m", str(max_hops), host]
    command_timeout = hop_timeout * max_hops * probes_per_hop + 10
    return command, command_timeout


def trace_route(host: str, timeout: float, stream: bool = False) -> Dict[str, Any]:
    """路由追踪。

    traceroute 默认每跳探测 3 次。如果 20 跳都不响应，2s * 20 * 3
    会超过原先 45s 的总超时，导致脚本提前杀掉命令。这里每跳只探测
    1 次，优先保证交互式诊断能稳定返回。
    """
    command, command_timeout = build_trace_command(host)
    runner = run_command_streaming if stream else run_command
    return runner(command, max(command_timeout, timeout + 5))


# ========== 综合诊断 ==========

def diag_target(host: str, count: int, timeout: float, include_trace: bool = True) -> Dict[str, Any]:
    """综合诊断: IP类型 + 本机出口 + Ping + TCP80/443 + Traceroute"""
    result = {
        "target": host,
        "ip_classification": classify_ip(host),
        "outbound_local_ip": get_outbound_local_ip_for_target(host, 443, timeout),
        "ping": ping_host(host, count, timeout),
        "tcp_80": scan_tcp_port(host, 80, timeout),
        "tcp_443": scan_tcp_port(host, 443, timeout),
    }
    if include_trace:
        result["trace"] = trace_route(host, timeout)
    return result


def common_tcp_ports() -> List[Tuple[int, str]]:
    return [
        (21, "FTP"), (22, "SSH"), (23, "Telnet"), (25, "SMTP"),
        (53, "DNS"), (80, "HTTP"), (110, "POP3"), (143, "IMAP"),
        (443, "HTTPS"), (465, "SMTPS"), (587, "SMTP-TLS"),
        (993, "IMAPS"), (995, "POP3S"), (1433, "MSSQL"),
        (1521, "Oracle"), (3306, "MySQL"), (3389, "RDP"),
        (5432, "PostgreSQL"), (5900, "VNC"), (6379, "Redis"),
        (8080, "HTTP-Alt"), (8443, "HTTPS-Alt"), (27017, "MongoDB"),
    ]


def run_subnet_scan(subnet: str, start: int, end: int, port: int, timeout: float) -> None:
    parts = subnet.split(".")
    if len(parts) != 3 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        print(f"\n  格式错误: 请输入三段式C段，如 192.168.1，不是 {subnet}\n")
        return
    if start < 1 or end > 254 or start > end:
        print("\n  IP 范围错误: 起始 1-254，结束 1-254，起始 <= 结束\n")
        return
    if not 1 <= port <= 65535:
        print("\n  端口范围错误: 1-65535\n")
        return

    print(f"\n扫描 {subnet}.{start}-{end}:{port} ...\n")
    open_hosts = []
    counts: Dict[str, int] = {}
    for i in range(start, end + 1):
        ip = f"{subnet}.{i}"
        result = scan_tcp_port(ip, port, timeout)
        state, _ = classify_tcp_port(result)
        counts[state] = counts.get(state, 0) + 1
        if state == "open":
            open_hosts.append(ip)
            print(f"  {ip}:{port} 开放")

    if open_hosts:
        print(f"\n发现 {len(open_hosts)} 个开放目标")
    else:
        print("\n未发现开放目标")
    print("  状态汇总: " + ", ".join(f"{state}={count}" for state, count in sorted(counts.items())))


# ========== 接口/网关信息 ==========

def interface_info(timeout: float) -> Dict[str, Any]:
    system = platform.system().lower()
    if system == "windows":
        commands = [["ipconfig", "/all"]]
    elif system == "darwin":
        commands = [["ifconfig"], ["networksetup", "-listallhardwareports"]]
    else:
        commands = [["ip", "-brief", "address"] if command_exists("ip") else ["ifconfig", "-a"]]
    return {"commands": [run_command(command, timeout) for command in commands]}


def gateway_info(timeout: float) -> Dict[str, Any]:
    system = platform.system().lower()
    if system == "windows":
        command = ["route", "print", "0.0.0.0"]
    elif system == "darwin":
        command = ["route", "-n", "get", "default"]
    else:
        command = ["ip", "route", "show", "default"] if command_exists("ip") else ["netstat", "-rn"]
    return run_command(command, timeout)


# ========== 交互式菜单 ==========

# ========== 全局超时设置 ==========
_timeout_basic = 4.0
_timeout_port = 2.0
_timeout_subnet = 1.0


def _get_basic_timeout() -> float:
    return _timeout_basic


def _get_port_timeout() -> float:
    return _timeout_port


def _get_subnet_timeout() -> float:
    return _timeout_subnet


MENU = """
== IP 检查与端口扫描 ==

  1. 检测本机/公网 IP
  2. Ping 检查
  3. TCP 端口扫描（单个）
  4. 批量端口扫描（常用端口）
  5. 扫描内网网段
  6. Traceroute 路由追踪
  7. 综合诊断（IP类型+出口+Ping+TCP+Trace）
  8. 网卡信息
  9. 网关信息

 s. 设置超时时间

 q. 退出
"""


def run_settings():
    global _timeout_basic, _timeout_port, _timeout_subnet
    print(f"""
== 超时设置 ==

  1. 基础超时 (Ping/HTTP/TLS/Trace)  当前: {_timeout_basic}s
  2. 端口扫描超时                     当前: {_timeout_port}s
  3. 网段扫描超时                     当前: {_timeout_subnet}s

  0. 返回
""")
    choice = input("请选择: ").strip()
    if choice == "1":
        _timeout_basic = ask_float("输入超时秒数", _timeout_basic, 0.1, 120.0)
    elif choice == "2":
        _timeout_port = ask_float("输入超时秒数", _timeout_port, 0.1, 120.0)
    elif choice == "3":
        _timeout_subnet = ask_float("输入超时秒数", _timeout_subnet, 0.1, 120.0)


# --- 菜单选项 ---

def run_local_ip():
    print("\n检测中...\n")
    timeout = _get_basic_timeout()

    local_ipv4 = get_outbound_local_ip(socket.AF_INET, timeout)
    hostname_addrs = get_hostname_addresses()

    print(f"  本机 IPv4: {format_value(local_ipv4)}")
    print(f"  主机名地址: {format_value(hostname_addrs)}")

    for version in ("ipv4",):
        ip, source, errors = get_public_ip(version, timeout)
        ip_cls = classify_ip(ip) if ip else {}
        geo = lookup_geo(ip, timeout) if ip else {}
        print(f"\n  公网 {version.upper()}:")
        print(f"    IP: {format_value(ip)}")
        print(f"    来源: {format_value(source)}")
        if ip_cls:
            print(f"    类型: {format_value(ip_cls.get('network_type'))}")
            print(f"    反向DNS: {format_value(ip_cls.get('reverse_dns'))}")
        print_geo(geo)
        if errors and not ip:
            print(f"    错误: {' | '.join(errors)}")


def run_ping():
    host = input("输入 IP: ").strip()
    if not host:
        return
    host = normalize_ip_or_print(host)
    if not host:
        return
    count = ask_int("Ping 次数", 4, 1, 20)
    timeout = _get_basic_timeout()
    print("\n")
    result = ping_host(host, count, timeout)
    brief_output(result)


def run_tcp():
    target = input("输入 IP:PORT (如 8.8.8.8:443): ").strip()
    if not target:
        return
    if ":" not in target:
        print("  缺少端口号，假设 80")
        target += ":80"
    host, port = parse_host_port(target, 80)
    host = normalize_ip_or_print(host)
    if not host:
        return
    target = format_host_port(host, port)
    timeout = _get_port_timeout()
    print("\n检测中...\n")
    result = scan_tcp_port(host, port, timeout)
    state, reason = classify_tcp_port(result)
    print(f"  port_state: {state}")
    print(f"  reason: {reason}")
    print(f"  scanner: {result.get('scanner')}")
    print(f"  source_ip: {format_value(get_outbound_local_ip_for_target(host, port, timeout))}")
    if result.get("remote_address"):
        print(f"  remote: {format_value(result.get('remote_address'))}")
    if result.get("local_address"):
        print(f"  local: {format_value(result.get('local_address'))}")
    if result.get("error"):
        print(f"  raw_error: {format_value(result.get('error'))}")
    print(f"  elapsed: {result.get('elapsed_seconds')}s")


def run_port_scan():
    target = input("输入 IP: ").strip()
    if not target:
        return
    target = normalize_ip_or_print(target)
    if not target:
        return
    timeout = _get_port_timeout()

    print(f"\n扫描 {target} 的常用端口...\n")
    results = []
    for port, name in common_tcp_ports():
        result = scan_tcp_port(target, port, timeout)
        state, _ = classify_tcp_port(result)
        results.append((port, name, state))
        if state == "open":
            print(f"  {port:<8} {name:<12} open")

    counts: Dict[str, int] = {}
    for _, _, state in results:
        counts[state] = counts.get(state, 0) + 1

    print("\n  == 汇总 ==")
    for state in sorted(counts):
        print(f"  {state:<16} {counts[state]}")

    uncertain = [item for item in results if item[2] in {"filtered", "open|filtered", "closed|filtered", "unknown"}]
    if uncertain:
        print(f"  提示: {len(uncertain)} 个端口状态不确定，不能按关闭处理。")


def run_subnet():
    subnet = input("输入 IP 网段 (如 192.168.1): ").strip()
    if not subnet:
        return

    start = ask_int("起始 IP", 1, 1, 254)
    end = ask_int("结束 IP", 254, 1, 254)
    port = ask_int("检测端口", 80, 1, 65535)
    timeout = _get_subnet_timeout()
    run_subnet_scan(subnet, start, end, port, timeout)


def run_trace():
    host = input("输入 IP: ").strip()
    if not host:
        return
    host = normalize_ip_or_print(host)
    if not host:
        return
    timeout = _get_basic_timeout()
    print("\n追踪中...\n")
    result = trace_route(host, timeout, stream=True)
    if result.get("error"):
        print(f"  error: {result.get('error')}")
    print(f"  elapsed: {result.get('elapsed_seconds')}s")


def run_diag():
    host = input("输入 IP: ").strip()
    if not host:
        return
    host = normalize_ip_or_print(host)
    if not host:
        return
    count = ask_int("Ping 次数", 4, 1, 20)
    timeout = _get_basic_timeout()
    print("\n诊断中...\n")
    result = diag_target(host, count, timeout, include_trace=False)

    print("  == 目标 IP ==")
    print(f"  输入目标: {result.get('target')}")
    ip_cls = result.get("ip_classification", {})
    print(f"  版本: IPv{ip_cls.get('version')}")
    print(f"  类型: {format_value(ip_cls.get('network_type'))}")
    print(f"  反向DNS: {format_value(ip_cls.get('reverse_dns'))}")

    print("\n  == 本机出口 ==")
    print(f"  访问目标时本机源地址: {format_value(result.get('outbound_local_ip'))}")
    if not result.get("outbound_local_ip"):
        print("  提示: 无法确定本机出口地址，可能是本机无对应协议栈路由或目标网络不可达")

    print("\n  == 连通性 ==")
    print(f"  Ping: {summarize_ping(result['ping'])} / rc={result['ping'].get('returncode')} / elapsed={result['ping'].get('elapsed_seconds')}s")
    tcp80_state, tcp80_reason = classify_tcp_port(result["tcp_80"])
    tcp443_state, tcp443_reason = classify_tcp_port(result["tcp_443"])
    print(f"  TCP 80: {tcp80_state} / {tcp80_reason}")
    print(f"  TCP 443: {tcp443_state} / {tcp443_reason}")

    if result["ping"].get("returncode") == 0 and tcp80_state == "closed" and tcp443_state == "closed":
        print("  判断: 主机 ICMP 可达，但常用 Web 端口关闭，优先查目标服务监听。")
    elif tcp80_state == "open" or tcp443_state == "open":
        print("  判断: 至少一个 TCP 端口可达，基础三层/四层链路基本正常。")
    elif tcp80_state == "filtered" or tcp443_state == "filtered":
        print("  判断: 至少一个 TCP 端口被过滤或无响应，不能直接判定端口关闭，优先查防火墙/安全组/白名单。")
    elif result["ping"].get("returncode") != 0:
        print("  判断: Ping 不通不一定代表目标不可达，可能是 ICMP 被禁；结合 TCP 和 Trace 判断。")

    print(f"\n  == Traceroute ==")
    result["trace"] = trace_route(host, timeout, stream=True)
    if result["trace"].get("error"):
        print(f"  error: {result['trace'].get('error')}")
    print(f"  elapsed: {result['trace'].get('elapsed_seconds')}s")


def run_interfaces():
    timeout = _get_basic_timeout()
    print("\n获取网卡信息...\n")
    info = interface_info(timeout)
    for item in info.get("commands", []):
        print(f"\n  === {' '.join(item.get('command', []))} ===")
        brief_output(item, max_lines=30)


def run_gateway():
    timeout = _get_basic_timeout()
    print("\n获取网关信息...\n")
    result = gateway_info(timeout)
    brief_output(result)


def print_tcp_result(result: Dict[str, Any], source_ip: Optional[str] = None) -> None:
    state, reason = classify_tcp_port(result)
    print(f"port_state: {state}")
    print(f"reason: {reason}")
    print(f"scanner: {result.get('scanner')}")
    if source_ip:
        print(f"source_ip: {source_ip}")
    if result.get("remote_address"):
        print(f"remote: {result.get('remote_address')}")
    if result.get("local_address"):
        print(f"local: {result.get('local_address')}")
    if result.get("error"):
        print(f"raw_error: {result.get('error')}")
    print(f"elapsed: {result.get('elapsed_seconds')}s")


def run_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="IP 检查与端口扫描工具")
    timeout_parent = argparse.ArgumentParser(add_help=False)
    timeout_parent.add_argument("--timeout", type=float, default=_timeout_basic, help="基础超时秒数")
    port_timeout_parent = argparse.ArgumentParser(add_help=False)
    port_timeout_parent.add_argument("--port-timeout", type=float, default=_timeout_port, help="端口扫描超时秒数")

    subparsers = parser.add_subparsers(dest="command")

    tcp_parser = subparsers.add_parser("tcp", parents=[port_timeout_parent], help="扫描单个 TCP 端口")
    tcp_parser.add_argument("target", help="IPv4:PORT")

    ping_parser = subparsers.add_parser("ping", parents=[timeout_parent], help="Ping 检查")
    ping_parser.add_argument("ip", help="IPv4 地址")
    ping_parser.add_argument("-c", "--count", type=int, default=4, help="Ping 次数")

    trace_parser = subparsers.add_parser("trace", parents=[timeout_parent], help="Traceroute 路由追踪")
    trace_parser.add_argument("ip", help="IPv4 地址")

    diag_parser = subparsers.add_parser("diag", parents=[timeout_parent], help="综合诊断")
    diag_parser.add_argument("ip", help="IPv4 地址")
    diag_parser.add_argument("-c", "--count", type=int, default=4, help="Ping 次数")

    ports_parser = subparsers.add_parser("ports", parents=[port_timeout_parent], help="扫描常用端口")
    ports_parser.add_argument("ip", help="IPv4 地址")

    subnet_parser = subparsers.add_parser("subnet", parents=[port_timeout_parent], help="扫描 IPv4 C 段指定端口")
    subnet_parser.add_argument("subnet", help="三段式 C 段，如 192.168.1")
    subnet_parser.add_argument("--start", type=int, default=1)
    subnet_parser.add_argument("--end", type=int, default=254)
    subnet_parser.add_argument("-p", "--port", type=int, default=80)

    subparsers.add_parser("local", help="检测本机/公网 IPv4")
    subparsers.add_parser("interfaces", help="网卡信息")
    subparsers.add_parser("gateway", help="网关信息")

    args = parser.parse_args(argv)
    if not args.command:
        return -1

    if args.command == "tcp":
        host, port = parse_host_port(args.target, 80)
        host = normalize_ip(host)
        if not host:
            parser.error("target 必须是 IPv4:PORT")
        result = scan_tcp_port(host, port, args.port_timeout)
        print_tcp_result(result, get_outbound_local_ip_for_target(host, port, args.port_timeout))
    elif args.command == "ping":
        host = normalize_ip(args.ip)
        if not host:
            parser.error("ip 必须是合法 IPv4")
        brief_output(ping_host(host, args.count, args.timeout))
    elif args.command == "trace":
        host = normalize_ip(args.ip)
        if not host:
            parser.error("ip 必须是合法 IPv4")
        trace_route(host, args.timeout, stream=True)
    elif args.command == "diag":
        host = normalize_ip(args.ip)
        if not host:
            parser.error("ip 必须是合法 IPv4")
        result = diag_target(host, args.count, args.timeout, include_trace=False)
        print(f"target: {result['target']}")
        print(f"source_ip: {format_value(result.get('outbound_local_ip'))}")
        print(f"ping: {summarize_ping(result['ping'])}")
        for key in ("tcp_80", "tcp_443"):
            state, reason = classify_tcp_port(result[key])
            print(f"{key}: {state} / {reason}")
        print("trace:")
        trace_route(host, args.timeout, stream=True)
    elif args.command == "ports":
        host = normalize_ip(args.ip)
        if not host:
            parser.error("ip 必须是合法 IPv4")
        for port, name in common_tcp_ports():
            result = scan_tcp_port(host, port, args.port_timeout)
            state, _ = classify_tcp_port(result)
            print(f"{port:<8} {name:<12} {state}")
    elif args.command == "subnet":
        run_subnet_scan(args.subnet, args.start, args.end, args.port, _timeout_subnet)
    elif args.command == "local":
        run_local_ip()
    elif args.command == "interfaces":
        run_interfaces()
    elif args.command == "gateway":
        run_gateway()
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if len(sys.argv) > 1:
        code = run_cli(sys.argv[1:])
        if code >= 0:
            return

    print("\n  IP 检查与端口扫描工具")
    print(f"  超时: 基础={_timeout_basic}s / 端口={_timeout_port}s / 网段={_timeout_subnet}s")
    print("  Python", platform.python_version(), "/", platform.system(), platform.release())

    while True:
        print(MENU)
        choice = input("请选择: ").strip()

        if choice.lower() == "q":
            print("再见")
            break

        handlers = {
            "1": run_local_ip,
            "2": run_ping,
            "3": run_tcp,
            "4": run_port_scan,
            "5": run_subnet,
            "6": run_trace,
            "7": run_diag,
            "8": run_interfaces,
            "9": run_gateway,
            "s": run_settings,
        }

        handler = handlers.get(choice)
        if handler:
            try:
                handler()
            except Exception as e:
                print(f"\n错误: {e}\n")
        else:
            print("无效选择\n")


if __name__ == "__main__":
    main()
