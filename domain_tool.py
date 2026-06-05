#!/usr/bin/env python3
"""域名管理工具 - 跨平台通用 (Linux/macOS/Windows)"""

import os
import re
import sys
import shutil
import socket
import platform
import time
import json
import ssl
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import urllib.request
except ImportError:
    urllib = None

DOMAIN_FILE = "domains.txt"

# 公共 DNS 服务器列表（国内优先）
PUBLIC_DNS = [
    ('223.5.5.5', '阿里云'),
    ('223.6.6.6', '阿里云'),
    ('119.29.29.29', '腾讯云'),
    ('182.254.118.118', '腾讯云'),
    ('114.114.114.114', '腾讯'),
    ('8.8.8.8', 'Google'),
    ('1.1.1.1', 'Cloudflare'),
]

# 可用 DNS 模块
DNS_AVAILABLE = False
try:
    import dns.resolver
    import dns.exception
    DNS_AVAILABLE = True
except ImportError:
    pass

# 终端颜色支持
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS = {
        'header': Fore.CYAN + Style.BRIGHT,
        'domain': Fore.GREEN + Style.BRIGHT,
        'label': Fore.BLUE,
        'value': Fore.WHITE,
        'error': Fore.RED + Style.BRIGHT,
        'warning': Fore.YELLOW + Style.BRIGHT,
        'success': Fore.GREEN,
        'dim': Fore.LIGHTBLACK_EX,
    }
except ImportError:
    COLORS = {k: '' for k in ['header', 'domain', 'label', 'value', 'error', 'warning', 'success', 'dim']}


def check_environment():
    """检查运行环境及依赖"""
    errors = []
    warnings = []
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 6):
        errors.append(f"Python 版本过低: {version.major}.{version.minor}，需要 3.6+")

    system = platform.system()
    if system not in {'Linux', 'Darwin', 'Windows'}:
        errors.append(f"不支持的系统: {system}")

    # ========== 依赖检测 ==========
    missing_deps = []
    missing_cmds = []

    # Python 模块
    if not DNS_AVAILABLE:
        missing_deps.append('dnspython')
    if not urllib:
        missing_deps.append('urllib (内置)')

    # 系统命令
    if system in ('Linux', 'Darwin'):
        import shutil as shutil_mod
        if not shutil_mod.which('whois'):
            missing_cmds.append('whois')
        if not shutil_mod.which('openssl'):
            missing_cmds.append('openssl')

    # 颜色模块（可选，有就更好）
    try:
        import colorama
    except ImportError:
        warnings.append('colorama (建议安装，颜色显示)')

    if missing_deps:
        errors.append(f"缺少 Python 模块: {', '.join(missing_deps)}")
    if missing_cmds:
        errors.append(f"缺少系统命令: {', '.join(missing_cmds)}")

    if errors:
        return False, '\n'.join(errors), missing_deps, missing_cmds
    return True, f"{platform.system()} {platform.release()} / Python {version.major}.{version.minor}.{version.micro}", missing_deps, missing_cmds


def get_ip_info(ip: str) -> dict:
    """查询 IP 地址详细信息"""
    result = {
        'ip': ip,
        'country': None,
        'region': None,
        'city': None,
        'isp': None,
        'org': None,
        'asn': None,
        'timezone': None,
        'coords': None,
        'error': None
    }

    if not urllib:
        result['error'] = 'urllib 模块不可用'
        return result

    # 跳过私有 IP
    if ip.startswith(('10.', '172.16.', '172.17.', '172.18.', '172.19.',
                      '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                      '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                      '172.30.', '172.31.', '192.168.', '127.', '0.', '198.18.', '198.19.')):
        result['error'] = '保留/私有 IP (CDN/内网)'
        return result

    apis = [
        ('ipapi.co', 'http://ipapi.co/{ip}/json/'),
        ('ip-api.com', 'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,isp,org,as,timezone,lat,lon'),
    ]

    for api_name, api_url in apis:
        try:
            url = api_url.format(ip=ip)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if api_name == 'ipapi.co':
                if data.get('error'):
                    continue
                result['country'] = f"{data.get('country_name', '')} ({data.get('country_code', '')})"
                result['region'] = data.get('region', '')
                result['city'] = data.get('city', '')
                result['isp'] = data.get('org', '')
                result['org'] = data.get('org', '')
                result['asn'] = data.get('asn', '')
                result['timezone'] = data.get('timezone', '')
                result['coords'] = f"{data.get('latitude', '')}, {data.get('longitude', '')}"
            else:
                if data.get('status') != 'success':
                    continue
                result['country'] = f"{data.get('country', '')} ({data.get('countryCode', '')})"
                result['region'] = data.get('regionName', '')
                result['city'] = data.get('city', '')
                result['isp'] = data.get('isp', '')
                result['org'] = data.get('org', '')
                result['asn'] = data.get('as', '')
                result['timezone'] = data.get('timezone', '')
                result['coords'] = f"{data.get('lat', '')}, {data.get('lon', '')}"

            if result['country'] or result['isp']:
                return result
        except Exception:
            continue

    result['error'] = '查询失败 (可能超出API限制)'
    return result


def get_whois(domain: str) -> dict:
    """查询 WHOIS 信息"""
    result = {
        'domain': domain,
        'registrar': None,
        'registration_date': None,
        'expiration_date': None,
        'name_servers': [],
        'status': None,
        'error': None
    }

    try:
        if platform.system() == 'Darwin' or platform.system() == 'Linux':
            # macOS/Linux 用系统 whois 命令
            proc = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=10)
            output = proc.stdout
        else:
            result['error'] = 'WHOIS 仅支持 macOS/Linux'
            return result

        if not output:
            result['error'] = 'WHOIS 查询无结果'
            return result

        # 解析关键字段
        for line in output.split('\n'):
            line = line.strip()
            if ':' in line:
                key, _, val = line.partition(':')
                key = key.strip().lower()
                val = val.strip()

                if 'registrar' in key or 'sponsoring registrar' in key:
                    result['registrar'] = val
                elif 'creation date' in key or 'created' in key or 'created date' in key:
                    if not result['registration_date']:
                        result['registration_date'] = val
                elif 'expir' in key or 'expiration date' in key or 'expires' in key:
                    if not result['expiration_date']:
                        result['expiration_date'] = val
                elif 'name server' in key or 'ns' in key:
                    if val and '.' in val:
                        result['name_servers'].append(val.lower())
                elif 'domain status' in key or 'status' in key:
                    if not result['status']:
                        result['status'] = val

        if not result['registrar'] and not result['registration_date']:
            # 尝试原始输出匹配
            if 'No match' in output or 'NOT FOUND' in output:
                result['error'] = '域名未注册或不可用'
            elif 'Domain Name:' in output:
                # 另一种格式
                for line in output.split('\n'):
                    if line.startswith('Domain Name:'):
                        result['registrar'] = line.split(':', 1)[1].strip()
                        break

    except subprocess.TimeoutExpired:
        result['error'] = 'WHOIS 查询超时'
    except FileNotFoundError:
        result['error'] = '系统未安装 whois 命令 (macOS: brew install whois)'
    except Exception as e:
        result['error'] = f'WHOIS 查询异常: {e}'

    return result


def get_ssl_info(domain: str, port: int = 443) -> dict:
    """获取 SSL 证书信息"""
    result = {
        'domain': domain,
        'port': port,
        'issuer': None,
        'subject': None,
        'valid_from': None,
        'valid_to': None,
        'days_remaining': None,
        'version': None,
        'cipher': None,
        'signature_algorithm': None,
        'is_valid': None,
        'error': None
    }

    # 方法1: 用 openssl 命令（跨平台）
    try:
        proc = subprocess.run(
            ['openssl', 's_client', '-connect', f'{domain}:{port}', '-servername', domain],
            input=b'Q\n',
            capture_output=True,
            timeout=10
        )
        cert_text = proc.stdout.decode('utf-8', errors='ignore')

        # 解析证书内容
        if 'BEGIN CERTIFICATE' in cert_text:
            # 用 openssl 提取证书信息
            cert_proc = subprocess.run(
                ['openssl', 'x509', '-noout', '-subject', '-issuer', '-dates', '-serial'],
                input=proc.stdout,
                capture_output=True,
                timeout=5
            )
            if cert_proc.returncode == 0:
                lines = cert_proc.stdout.decode('utf-8').strip().split('\n')
                for line in lines:
                    if 'subject=' in line:
                        result['subject'] = line.split('=', 1)[1].strip()
                    elif 'issuer=' in line:
                        result['issuer'] = line.split('=', 1)[1].strip()
                    elif 'notBefore=' in line:
                        result['valid_from'] = line.split('=', 1)[1].strip()
                    elif 'notAfter=' in line:
                        result['valid_to'] = line.split('=', 1)[1].strip()
                        # 计算剩余天数
                        try:
                            exp_date = datetime.strptime(result['valid_to'], '%b %d %H:%M:%S %Y %Z')
                            result['days_remaining'] = (exp_date - datetime.now()).days
                        except:
                            pass

                # 判断有效性
                if result['days_remaining'] is not None:
                    if result['days_remaining'] < 0:
                        result['is_valid'] = '已过期'
                    elif result['days_remaining'] < 30:
                        result['is_valid'] = '即将过期'
                    else:
                        result['is_valid'] = '有效'

                return result

    except FileNotFoundError:
        result['error'] = '系统未安装 OpenSSL'
    except subprocess.TimeoutExpired:
        result['error'] = 'SSL 查询超时'
    except Exception:
        pass

    # 方法2: 用 socket 直接获取证书信息（基础信息）
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((domain, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cipher = ssock.cipher()
                if cipher:
                    result['cipher'] = cipher[0]
                    result['signature_algorithm'] = cipher[1]

                # 获取对等证书（不需要解析内部函数）
                cert_bin = ssock.getpeercert(binary_form=True)
                if cert_bin:
                    # 尝试从原始数据获取基本信息
                    try:
                        import base64
                        # 提取基本时间信息
                        # 这是简化版，完整解析需要 cryptography 库
                        result['is_valid'] = '有效(连接成功)'
                    except:
                        pass

        if not result.get('error') and not result.get('subject'):
            result['is_valid'] = '有效(连接成功)'

    except ssl.SSLCertVerificationError as e:
        result['error'] = f'证书验证失败: {e}'
    except socket.timeout:
        result['error'] = '连接超时'
    except ConnectionRefusedError:
        result['error'] = '连接被拒绝'
    except Exception as e:
        result['error'] = f'SSL 查询异常: {e}'

    return result


def resolve_with_dns(domain: str, dns_server: str = None) -> dict:
    """使用指定 DNS 服务器解析域名（完整版）"""
    record_types = ['A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'SRV', 'PTR']

    result = {
        'domain': domain,
        'records': {},
        'ports': {},
        'errors': [],
        'dns_server': dns_server,
        'response_time': None,
        'ttl': {},
        'ip_info': {}
    }

    # 域名格式校验
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    if not re.match(pattern, domain):
        result['errors'].append('域名格式不正确')
        return result

    if not DNS_AVAILABLE:
        result['errors'].append('dnspython 模块未安装，无法使用指定 DNS')
        return result

    resolver = dns.resolver.Resolver()
    resolver.timeout = 3
    resolver.lifetime = 5

    start_time = time.time()

    def query_record(record_type: str):
        try:
            answers = resolver.resolve(domain, record_type)
            records = []
            ttl = answers.ttl if hasattr(answers, 'ttl') else None

            if record_type == 'A':
                records = [rdata.address for rdata in answers]
            elif record_type == 'AAAA':
                records = [rdata.address for rdata in answers]
            elif record_type == 'MX':
                records = [f"{rdata.preference} {rdata.exchange}" for rdata in answers]
            elif record_type == 'TXT':
                records = [str(rdata).strip('"') for rdata in answers]
            elif record_type == 'CNAME':
                records = [str(rdata) for rdata in answers]
            elif record_type == 'NS':
                records = [str(rdata) for rdata in answers]
            elif record_type == 'SOA':
                records = [f"Serial:{answers[0].serial} Refresh:{answers[0].refresh} Retry:{answers[0].retry} Expire:{answers[0].expire} MBox:{answers[0].rname}"]
            elif record_type == 'SRV':
                records = [f"{rdata.priority} {rdata.weight} {rdata.port} {rdata.target}" for rdata in answers]
            elif record_type == 'PTR':
                records = [str(rdata) for rdata in answers]

            return records, ttl
        except dns.resolver.NoAnswer:
            return None, None
        except dns.resolver.NXDOMAIN:
            result['errors'].append('域名不存在 (NXDOMAIN)')
            return None, None
        except dns.exception.Timeout:
            return None, None
        except Exception as e:
            result['errors'].append(f'{record_type} 查询失败: {e}')
            return None, None

    if dns_server:
        resolver.nameservers = [dns_server]
        for rtype in record_types:
            records, ttl = query_record(rtype)
            if records is not None:
                result['records'][rtype] = records
                if ttl:
                    result['ttl'][rtype] = ttl
        result['dns_server'] = dns_server
    else:
        for dns_ip, dns_name in PUBLIC_DNS:
            resolver.nameservers = [dns_ip]
            for rtype in record_types:
                records, ttl = query_record(rtype)
                if records is not None:
                    result['records'][rtype] = records
                    if ttl:
                        result['ttl'][rtype] = ttl

            if result['records'] or result['errors']:
                result['dns_server'] = f"{dns_ip} ({dns_name})"
                break

        if not result['records'] and not result['errors']:
            result['errors'].append('所有公共 DNS 均解析失败')

    result['response_time'] = round((time.time() - start_time) * 1000, 2)

    # 查询 IPv4 详细信息
    if 'A' in result['records'] and result['records']['A']:
        ipv4 = result['records']['A'][0]
        ip_info = get_ip_info(ipv4)
        result['ip_info'] = ip_info

    # 检测是否为 CDN/私有 IP
    def is_private_cdn_ip(ip: str) -> bool:
        return ip.startswith(('10.', '172.16.', '172.17.', '172.18.', '172.19.',
                              '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                              '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                              '172.30.', '172.31.', '192.168.', '127.', '0.',
                              '198.18.', '198.19.', '169.254.', '224.', '240.'))

    # 端口检测
    if 'A' in result['records'] and result['records']['A']:
        first_ip = result['records']['A'][0]
        if is_private_cdn_ip(first_ip):
            result['ports']['note'] = 'CDN/私有IP，跳过端口检测'
        else:
            port_checks = {80: 'HTTP', 443: 'HTTPS', 8080: 'HTTP-Alt', 8443: 'HTTPS-Alt'}
            for port, name in port_checks.items():
                try:
                    sock = socket.create_connection((first_ip, port), timeout=2)
                    sock.close()
                    result['ports'][port] = f'{name} 可连接'
                except socket.timeout:
                    result['ports'][port] = f'{name} 超时'
                except (ConnectionRefusedError, OSError):
                    result['ports'][port] = f'{name} 关闭'
                except Exception:
                    result['ports'][port] = f'{name} 异常'

    return result


def compare_dns_all(domain: str) -> list:
    """在所有 DNS 服务器上查询并对比结果"""
    results = []

    def query_with_dns(dns_ip, dns_name):
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [dns_ip]
            resolver.timeout = 3
            resolver.lifetime = 5
            a_records = resolver.resolve(domain, 'A')
            ips = [rdata.address for rdata in a_records]
            return {'dns': f"{dns_ip} ({dns_name})", 'ips': sorted(ips), 'success': True}
        except Exception as e:
            return {'dns': f"{dns_ip} ({dns_name})", 'ips': [], 'success': False, 'error': str(e)}

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(query_with_dns, ip, name): (ip, name) for ip, name in PUBLIC_DNS}
        for future in as_completed(futures):
            results.append(future.result())

    return results


def display_result(result: dict):
    """格式化显示结果"""
    records = result.get('records', {})
    ttl = result.get('ttl', {})
    ports = result.get('ports', {})
    ip_info = result.get('ip_info', {})
    c = COLORS

    print(f"\n{c['header']}{'='*56}")
    print(f"{c['domain']}  域名: {result['domain']}{c['dim']}")
    if result.get('dns_server'):
        print(f"{c['dim']}  DNS:  {result['dns_server']}")
    print(f"{c['dim']}  耗时: {result.get('response_time')}ms")
    print(f"{c['header']}{'='*56}")

    if result['errors'] and not records:
        print(f"  {c['error']}错误: {'; '.join(result['errors'])}")
        return

    def show_record(label, key, limit=None):
        if key in records and records[key]:
            val = ', '.join(records[key])
            if limit and len(val) > limit:
                val = val[:limit] + '...'
            print(f"  {c['label']}%-10s{c['value']} %s" % (f'{label}:', val))
            if key in ttl:
                print(f"  {c['dim']}%-10s TTL: %ds" % ('', ttl[key]))
        else:
            print(f"  {c['label']}%-10s{c['dim']} 无记录" % (f'{label}:',))

    def show_record_multiline(label, key):
        if key in records and records[key]:
            print(f"  {c['label']}%-10s" % (f'{label}:',))
            for r in records[key]:
                print(f"  {c['label']}%-10s{c['value']} %s" % ('', r))
            if key in ttl:
                print(f"  {c['dim']}%-10s TTL: %ds" % ('', ttl[key]))
        else:
            print(f"  {c['label']}%-10s{c['dim']} 无记录" % (f'{label}:',))

    show_record('IPv4', 'A')
    show_record('IPv6', 'AAAA')
    show_record_multiline('MX', 'MX')
    show_record('TXT', 'TXT', 60)
    show_record('CNAME', 'CNAME', 60)
    show_record('NS', 'NS', 50)
    show_record_multiline('SOA', 'SOA')
    show_record_multiline('SRV', 'SRV')
    show_record('PTR', 'PTR')

    # IP 详细信息
    if ip_info:
        print(f"\n  {c['header']}-- IP 详细信息 --")
        if ip_info.get('error'):
            print(f"  {c['dim']}%-10s %s" % ('状态:', ip_info['error']))
        else:
            if ip_info.get('country'):
                print(f"  {c['label']}%-10s{c['value']} %s" % ('国家:', ip_info['country']))
            if ip_info.get('region') or ip_info.get('city'):
                print(f"  {c['label']}%-10s{c['value']} %s %s" % ('位置:', ip_info.get('region', ''), ip_info.get('city', '')))
            if ip_info.get('isp'):
                print(f"  {c['label']}%-10s{c['value']} %s" % ('运营商:', ip_info['isp']))
            if ip_info.get('asn'):
                print(f"  {c['label']}%-10s{c['value']} %s" % ('ASN:', ip_info['asn']))

    # 端口检测
    if ports:
        print(f"\n  {c['header']}-- 端口检测 --")
        if 'note' in ports:
            print(f"  {c['dim']}%-10s %s" % ('状态:', ports['note']))
        else:
            open_ports = [f"{p}({v.split()[0]})" for p, v in ports.items() if '可连接' in v]
            if open_ports:
                print(f"  {c['success']}开放: {', '.join(open_ports)}")

    if result.get('errors'):
        print(f"\n  {c['warning']}警告: {'; '.join(result['errors'])}")


def display_whois(result: dict):
    """显示 WHOIS 结果"""
    c = COLORS
    print(f"\n  {c['header']}-- WHOIS 信息 --")
    if result.get('error'):
        print(f"  {c['dim']}%-10s %s" % ('状态:', result['error']))
        return

    if result.get('registrar'):
        print(f"  {c['label']}%-15s{c['value']} %s" % ('注册商:', result['registrar']))
    if result.get('registration_date'):
        print(f"  {c['label']}%-15s{c['value']} %s" % ('注册日期:', result['registration_date']))
    if result.get('expiration_date'):
        print(f"  {c['label']}%-15s{c['value']} %s" % ('到期日期:', result['expiration_date']))
    if result.get('name_servers'):
        print(f"  {c['label']}%-15s{c['value']} %s" % ('DNS服务器:', ', '.join(result['name_servers'][:4])))
    if result.get('status'):
        print(f"  {c['label']}%-15s{c['value']} %s" % ('状态:', result['status']))


def display_ssl(result: dict):
    """显示 SSL 证书结果"""
    c = COLORS
    print(f"\n  {c['header']}-- SSL 证书 --")
    if result.get('error'):
        print(f"  {c['dim']}%-10s %s" % ('状态:', result['error']))
        return

    if result.get('is_valid'):
        status_color = c['success'] if result['is_valid'] == '有效' else c['warning']
        print(f"  {c['label']}%-12s{status_color}%s" % ('有效性:', result['is_valid']))

    if result.get('days_remaining') is not None:
        days_color = c['success'] if result['days_remaining'] > 30 else c['warning']
        print(f"  {c['label']}%-12s{days_color}%d 天" % ('剩余天数:', result['days_remaining']))

    if result.get('valid_to'):
        print(f"  {c['label']}%-12s{c['value']} %s" % ('到期时间:', result['valid_to']))

    if result.get('issuer'):
        # 简化 issuer 显示
        issuer = result['issuer']
        if isinstance(issuer, dict):
            issuer = issuer.get('organizationName', str(issuer))
        print(f"  {c['label']}%-12s{c['value']} %s" % ('颁发者:', str(issuer)[:50]))

    if result.get('subject'):
        subject = result['subject']
        if isinstance(subject, dict):
            subject = subject.get('commonName', str(subject))
        print(f"  {c['label']}%-12s{c['value']} %s" % ('证书域名:', str(subject)[:50]))

    if result.get('cipher'):
        print(f"  {c['label']}%-12s{c['value']} %s" % ('加密套件:', result['cipher']))


def display_dns_compare(results: list):
    """显示多 DNS 对比结果"""
    c = COLORS
    print(f"\n  {c['header']}-- 多 DNS 对比 --")

    success_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]

    if success_results:
        print(f"  {c['success']}成功: {len(success_results)}/{len(results)}")
        for r in success_results:
            print(f"  {c['dim']}%-15s {c['value']}%s" % (r['dns'] + ':', ', '.join(r['ips']) if r['ips'] else '无A记录'))

        # 检查是否所有 DNS 返回相同 IP
        all_ips = [tuple(r['ips']) for r in success_results if r['ips']]
        if len(set(all_ips)) == 1:
            print(f"  {c['success']}✓ 所有DNS返回一致")
        else:
            print(f"  {c['warning']}⚠ DNS返回不一致!")

    if failed_results:
        print(f"  {c['error']}失败: {len(failed_results)}/{len(results)}")
        for r in failed_results:
            print(f"  {c['dim']}%-15s {r['error'] or '查询失败'}" % (r['dns'] + ':'))


def resolve_interactive():
    """交互式解析"""
    c = COLORS
    print(f"{c['header']}=== 域名解析检查 (完整版) ===")
    print(f"{c['dim']}输入域名后回车，输入 q 退出")
    print("-" * 50)

    dns_choice = PUBLIC_DNS[0][0]
    print(f"\n{c['dim']}默认使用 DNS: {dns_choice} ({PUBLIC_DNS[0][1]})")

    while True:
        user_input = input(f"\n{c['value']}请输入域名: ").strip()

        if user_input.lower() == 'q':
            print(f"{c['dim']}已退出")
            return

        if not user_input:
            continue

        domains = [d.strip() for d in user_input.split(',')]
        domains = [d for d in domains if d]

        if len(domains) == 1:
            domain = domains[0]
            result = resolve_with_dns(domain, dns_choice)

            if result['errors'] and not result['records']:
                print(f"\n  {c['error']}错误: {result['errors'][0]}")
                retry = input(f"{c['warning']}是否使用自定义 DNS? (y/n): ").strip().lower()
                if retry == 'y':
                    custom_dns = input(f"{c['value']}请输入 DNS 服务器 IP: ").strip()
                    if custom_dns:
                        result = resolve_with_dns(domain, custom_dns)

            display_result(result)

            # WHOIS 查询
            if result['records']:
                print(f"\n{c['dim']}正在查询 WHOIS...")
                whois_result = get_whois(domain)
                display_whois(whois_result)

            # SSL 证书查询
            if result.get('records', {}).get('A') or result.get('ports', {}).get(443):
                print(f"\n{c['dim']}正在查询 SSL 证书...")
                ssl_result = get_ssl_info(domain, 443)
                display_ssl(ssl_result)

            # 多 DNS 对比
            print(f"\n{c['dim']}正在多 DNS 对比...")
            compare_results = compare_dns_all(domain)
            display_dns_compare(compare_results)

        else:
            print(f"\n{c['dim']}正在并发解析 {len(domains)} 个域名...")

            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_domain = {executor.submit(resolve_with_dns, d, dns_choice): d for d in domains}
                for future in as_completed(future_to_domain):
                    domain = future_to_domain[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({'domain': domain, 'errors': [str(e)], 'records': {}})

            results_dict = {r['domain']: r for r in results}
            for domain in domains:
                display_result(results_dict[domain])


def validate_domain(domain: str) -> bool:
    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain))


def load_domains() -> list:
    if not os.path.exists(DOMAIN_FILE):
        shutil.copy(f"{DOMAIN_FILE}.template", DOMAIN_FILE) if os.path.exists(f"{DOMAIN_FILE}.template") else None
    domains = []
    if os.path.exists(DOMAIN_FILE):
        with open(DOMAIN_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    domains.append(line)
    return sorted(set(domains))


def save_domain(domain: str) -> bool:
    domains = load_domains()
    if domain in domains:
        return False
    with open(DOMAIN_FILE, 'a', encoding='utf-8') as f:
        f.write(domain + '\n')
    return True


def remove_domain(domain: str) -> bool:
    domains = load_domains()
    if domain not in domains:
        return False
    with open(DOMAIN_FILE, 'w', encoding='utf-8') as f:
        for d in domains:
            if d != domain:
                f.write(d + '\n')
    return True


def add_interactive():
    print("=== 域名添加模式 ===")
    print("输入域名后回车，输入 q 退出")
    print("-" * 30)

    while True:
        try:
            domain = input("请输入域名: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if domain.lower() == 'q':
            break

        if not domain:
            continue

        if not validate_domain(domain):
            print(f"  [错误] 域名格式不正确: {domain}")
            continue

        if save_domain(domain):
            print(f"  [成功] {domain} 已添加")
        else:
            print(f"  [跳过] {domain} 已存在")


def list_domains():
    domains = load_domains()
    print(f"=== 域名列表 ({len(domains)} 个) ===")
    for d in domains:
        print(d)


def check_domain(domain: str):
    domains = load_domains()
    if domain in domains:
        print(f"{domain} 已存在")
    else:
        print(f"{domain} 不存在")


def remove_interactive():
    domains = load_domains()
    if not domains:
        print("域名列表为空")
        return

    print("=== 域名删除模式 ===")
    print("输入序号删除域名，输入 q 退出")
    print("-" * 30)

    for i, d in enumerate(domains, 1):
        print(f"  {i}. {d}")

    print("-" * 30)

    while True:
        try:
            choice = input("请输入序号: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice.lower() == 'q':
            break

        if not choice.isdigit():
            print("  [错误] 请输入数字")
            continue

        idx = int(choice) - 1
        if idx < 0 or idx >= len(domains):
            print(f"  [错误] 序号超出范围 (1-{len(domains)})")
            continue

        domain = domains[idx]
        if remove_domain(domain):
            print(f"  [成功] {domain} 已删除")
            domains = load_domains()
            if not domains:
                print("域名列表已为空")
                break


def show_help():
    print("""用法: domain_tool.py <命令>

命令:
  add             交互式添加域名
  list            显示所有域名
  remove          交互式删除域名
  check <域名>    检查域名是否存在
  resolve         交互式解析检查
  help            显示帮助

示例:
  python domain_tool.py add
  python domain_tool.py list
  python domain_tool.py check example.com
  python domain_tool.py resolve""")


def main():
    print("正在检测环境...")
    compatible, info, missing_deps, missing_cmds = check_environment()
    print(f"环境信息: {info}")

    if not compatible:
        print(f"\n[错误] 环境不兼容:")
        print(f"  {info}")
        print("\n解决方法:")
        if missing_deps:
            print("  pip install dnspython colorama")
            print("  或使用国内镜像:")
            print("  pip install dnspython colorama -i https://pypi.tuna.tsinghua.edu.cn/simple")
        if missing_cmds:
            sys_name = platform.system()
            if sys_name == 'Darwin':
                print(f"  brew install {' '.join(missing_cmds)}")
            elif sys_name == 'Linux':
                print(f"  sudo apt install {' '.join(missing_cmds)}")
        print("\n注意: resolve 功能需要 dnspython，其他命令 (add/list/remove/check) 不受影响")
        sys.exit(1)

    # 警告信息（可选依赖缺失）
    if missing_deps or missing_cmds:
        print("\n[警告] 部分功能可能不可用:")
        if missing_deps:
            print(f"  Python模块: {', '.join(missing_deps)}")
        if missing_cmds:
            print(f"  系统命令: {', '.join(missing_cmds)}")
        print("")

    print("环境检测通过\n")

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'add':
        add_interactive()
    elif cmd == 'list':
        list_domains()
    elif cmd == 'remove':
        remove_interactive()
    elif cmd == 'check':
        if len(sys.argv) < 3:
            print("用法: domain_tool.py check <域名>")
            sys.exit(1)
        check_domain(sys.argv[2])
    elif cmd == 'resolve':
        resolve_interactive()
    elif cmd == 'help':
        show_help()
    else:
        show_help()
        sys.exit(1)


if __name__ == '__main__':
    main()