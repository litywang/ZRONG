"""
core/validator.py - 节点验证与去重模块

从 utils.py 迁移验证/去重相关函数和常量，负责：
- 节点去重（generate_unique_id）
- 域名黑名单过滤（is_cn_proxy_domain / CN_DOMAIN_BLACKLIST_RE）
- Reality 安全域名（REALITY_SAFE_DOMAINS）
- 非代理端口检测（NON_PROXY_PORTS）
- 大陆直连节点判断（is_china_mainland）
- 亚洲节点判断（is_asia，从 utils 导入）

使用：
    from core.validator import generate_unique_id, is_cn_proxy_domain
    from core.validator import CN_DOMAIN_BLACKLIST_RE, REALITY_SAFE_DOMAINS, NON_PROXY_PORTS
"""

import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ===== CN 域名黑名单正则 =====
CN_DOMAIN_BLACKLIST_RE = re.compile(
    r'\.(cn|cyou|top|xyz|cc|mojcn|cnmjin|qpon|'
    r'hk[\-_]?db|entry\.v\d+|internal\.(?:hk|tw|jp|sg)|bk[\-_]?hk\.node|'
    r'mobgslb\.tbcache|mobgslb\.tengine|tbcache\.com|tengine\.alicdn)\d*'
    r'|(?:^|[\.\-])(?:v\d+|node)\d*\.hk[\-_]?(?:db|internal)|'
    r'fastcoke|mojcn\.com|cnmjin\.net', re.I)

# ===== Reality 安全域名 =====
REALITY_SAFE_DOMAINS = {'reality.dev', 'v2fly.org', 'matsuri.biz', 'poi.moe',
                         '233boys.dev', 'ssrsub.com', 'justmysocks.net', 'flow.kjjiang.com'}

# ===== 非代理端口黑名单 =====
NON_PROXY_PORTS = {2377, 2376, 2375, 9200, 9300, 27017, 27018, 27019,
                    6379, 11211, 5432, 3306, 8086}


def generate_unique_id(proxy):
    """生成节点唯一ID（协议/服务器/端口/认证信息 MD5 前12位）

    包含协议类型和路径，避免不同协议/路径的节点被误去重。
    """
    protocol = proxy.get('type', proxy.get('protocol', 'unknown'))
    server = proxy.get('server', '')
    port = proxy.get('port', 0)
    auth = proxy.get('uuid') or proxy.get('password') or ''
    path = proxy.get('path', '')
    network = proxy.get('network', 'tcp')

    key = f"{protocol}|{server}|{port}|{auth}|{path}|{network}"
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:12].upper()


def is_cn_proxy_domain(server):
    """判断是否为大陆代理域名（黑名单匹配）"""
    from utils import is_pure_ip
    if not server or is_pure_ip(server):
        return False
    sl = server.lower()
    for safe in REALITY_SAFE_DOMAINS:
        if sl.endswith(safe) or sl == safe:
            return False
    if CN_DOMAIN_BLACKLIST_RE.search(server):
        return True
    return False


def is_china_mainland(p):
    """判断是否为内地直连节点（一般不可用，用于过滤）"""
    from utils import is_pure_ip
    from core.scorer import _get_limiter
    if not p or not isinstance(p, dict):
        return False
    try:
        t = f"{p.get('name', '')} {p.get('server', '')}".lower()
        tokens = set(re.split(r'[\s\-_|,.:;/()\uff08\uff09\u3010\u3011\[\]\{\}]+', t))
        cn_2letter = {"cn"}
        cn_long = ["china", "中国", "国内", "直连", "direct",
                    "北京", "上海", "广州", "深圳", "成都", "杭州"]
        if tokens & cn_2letter:
            return True
        if any(k in t for k in cn_long):
            return True
        server = p.get("server", "")
        if is_pure_ip(server):
            try:
                limiter = _get_limiter()
                geo = limiter.get_geo(server)
                if geo:
                    cc = geo.get("countryCode", "").upper()
                    if cc == "CN":
                        return True
            except (ImportError, AttributeError):
                logger.debug("is_china_mainland limiter not ready", exc_info=True)
        return False
    except (ValueError, TypeError):
        logger.debug("is_china_mainland error", exc_info=True)
        return False


def is_asia(p):
    """v28.16: 增强亚洲节点检测（关键词+IP地理位置+SNI+域名TLD+v30.0 emoji旗帜）

    延迟导入 utils 中的常量，避免循环依赖。
    """
    from utils import is_pure_ip, ASIA_REGIONS
    from core.scorer import _get_limiter
    if not p or not isinstance(p, dict):
        return False

    # v30.0: 国旗 emoji 直接匹配（re.split 会拆散复合emoji，需单独检测）
    name = p.get('name', '')
    # 亚洲地区国旗 emoji：港新日韩台泰越马印菲蒙柬老
    asia_flags = {
        '🇭🇰', '🇸🇬', '🇯🇵', '🇰🇷', '🇹🇼',
        '🇹🇭', '🇻🇳', '🇲🇾', '🇮🇩', '🇵🇭',
        '🇲🇴', '🇲🇳', '🇰🇭', '🇱🇦',
    }
    if any(fl in name for fl in asia_flags):
        return True
    # 非亚洲常见国旗（优先排除，减少误判）
    non_asia_flags = {
        '🇺🇸', '🇬🇧', '🇩🇪', '🇫🇷', '🇳🇱',
        '🇷🇺', '🇺🇦', '🇹🇷', '🇮🇹', '🇨🇦',
        '🇦🇺', '🇧🇷', '🇮🇳', '🇪🇸', '🇵🇱',
        '🇨🇭', '🇸🇪', '🇳🇴', '🇩🇰', '🇫🇮',
        '🇧🇪', '🇦🇹', '🇵🇹', '🇨🇿', '🇭🇺',
        '🇮🇷',
    }
    if any(fl in name for fl in non_asia_flags):
        return False

    t = f"{name} {p.get('server', '')}".lower()
    tokens = set(re.split(r'[\s\-_|,.:;/()\uff08\uff09\u3010\u3011\[\]\{\}]+', t))
    asia_2letter = {
        "hk", "tw", "jp", "sg", "kr", "th", "vn",
        "ph", "mo", "mn", "kh", "mm", "bn",
        "tl", "np", "lk", "bd", "bt", "mv",
    }
    if tokens & asia_2letter:
        return True
    asia_long = [
        "hongkong", "港", "taiwan", "台", "japan", "日",
        "singapore", "新加坡", "狮城", "korea", "韩", "asia",
        "hkt", "thailand", "泰", "vietnam", "越", "malaysia", "马",
        "indonesia", "印尼", "philippines", "菲律宾", "phillipines",
        "macau", "澳门", "macao", "mongolia", "蒙古",
        "cambodia", "柬埔寨", "laos", "老挝", "myanmar", "缅甸",
        "brunei", "文莱", "nepal", "尼泊尔", "sri lanka", "斯里兰卡",
        "bangladesh", "孟加拉", "bhutan", "不丹", "maldives", "马尔代夫",
        "east asia", "southeast asia", "south asia", "东亚", "东南亚", "南亚",
        "asia pacific", "apac", "亚太", "tokyo", "osaka", "seoul",
        "bangkok", "hanoi", "jakarta", "manila", "kuala", "taipei",
    ]
    if any(k in t for k in asia_long):
        return True
    server = p.get("server", "")
    if is_pure_ip(server):
        try:
            limiter = _get_limiter()
            geo = limiter.get_geo(server)
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc in ASIA_REGIONS:
                    return True
        except (ImportError, AttributeError):
            logger.debug("Limiter not ready, skipping geo lookup")
    sni = (p.get("sni", "") or p.get("servername", "")).lower()
    ws_opts = p.get("ws-opts", {})
    ws_host = (
        ws_opts.get("headers", {}).get("Host", "")
        if isinstance(ws_opts, dict) else ""
    )
    check_domains = f"{sni} {ws_host} {server}".lower()
    asia_tlds = [
        ".hk", ".tw", ".jp", ".sg", ".kr", ".th", ".vn",
        ".my", ".id", ".ph", ".mo", ".mn", ".kh", ".la",
    ]
    for tld in asia_tlds:
        if tld in check_domains:
            return True
    return False


def validate_node(p):
    """基础节点验证：过滤明显不可用的节点

    返回 True 表示节点可用，False 表示应被过滤。
    """
    if not p or not isinstance(p, dict):
        return False
    ptype = p.get("type", "")
    port = p.get("port", 0)
    server = p.get("server", "")
    if not ptype or not server:
        return False
    try:
        port_i = int(port)
    except (ValueError, TypeError):
        return False
    if port_i in NON_PROXY_PORTS:
        return False
    return True


# ===== v28.87: 健康检查状态常量 =====
HEALTH_OK = "ok"
HEALTH_DEGRADED = "degraded"
HEALTH_DISABLED = "disabled"
HEALTH_CHECK_FAIL_THRESHOLD = 3  # 连续失败次数达到此值后禁用节点

# v28.87: 运行时健康状态跟踪（server:port -> {"consecutive_fails": int, "status": str, "last_check": str}）
_RUNTIME_HEALTH: dict[str, dict] = {}


def get_runtime_health_key(node: dict) -> str:
    """生成节点运行时健康检查的唯一键"""
    return f"{node.get('server', '')}:{node.get('port', '')}"


def get_node_health_status(node: dict) -> str:
    """获取节点当前健康状态：ok / degraded / disabled"""
    key = get_runtime_health_key(node)
    entry = _RUNTIME_HEALTH.get(key)
    if not entry:
        return HEALTH_OK  # 无记录视为健康
    return entry.get("status", HEALTH_OK)


def is_node_disabled(node: dict) -> bool:
    """判断节点是否已被健康检查禁用"""
    return get_node_health_status(node) == HEALTH_DISABLED


def record_health_result(node: dict, success: bool) -> str:
    """v28.87: 记录健康检查结果，返回节点最新状态

    借鉴 discovery-service 的机制：
    - 连续失败 FAIL_THRESHOLD 次后标记为 disabled
    - 成功一次即重置失败计数
    - degraded 状态介于 ok 和 disabled 之间（失败1-2次）

    Returns:
        HEALTH_OK / HEALTH_DEGRADED / HEALTH_DISABLED
    """
    from datetime import datetime
    key = get_runtime_health_key(node)
    now = datetime.now().isoformat()

    if key not in _RUNTIME_HEALTH:
        _RUNTIME_HEALTH[key] = {"consecutive_fails": 0, "status": HEALTH_OK, "last_check": now}

    entry = _RUNTIME_HEALTH[key]
    entry["last_check"] = now

    if success:
        entry["consecutive_fails"] = 0
        entry["status"] = HEALTH_OK
    else:
        entry["consecutive_fails"] = entry.get("consecutive_fails", 0) + 1
        if entry["consecutive_fails"] >= HEALTH_CHECK_FAIL_THRESHOLD:
            entry["status"] = HEALTH_DISABLED
            logger.info(f"health: {key} DISABLED (consecutive fails: {entry['consecutive_fails']})")
        elif entry["consecutive_fails"] >= 1:
            entry["status"] = HEALTH_DEGRADED
            logger.debug(f"health: {key} degraded (fails: {entry['consecutive_fails']})")

    return entry["status"]


def get_health_summary() -> dict:
    """v28.87: 获取健康检查统计摘要"""
    ok_count = sum(1 for e in _RUNTIME_HEALTH.values() if e.get("status") == HEALTH_OK)
    degraded_count = sum(1 for e in _RUNTIME_HEALTH.values() if e.get("status") == HEALTH_DEGRADED)
    disabled_count = sum(1 for e in _RUNTIME_HEALTH.values() if e.get("status") == HEALTH_DISABLED)
    return {"ok": ok_count, "degraded": degraded_count, "disabled": disabled_count, "total": len(_RUNTIME_HEALTH)}


def reset_runtime_health():
    """重置运行时健康状态（新一轮测试开始时调用）"""
    _RUNTIME_HEALTH.clear()


def health_check_via_clash(node: dict, clash_api_port: int = 9090, timeout: int = 5) -> bool:
    """v28.87: 通过 Clash Controller API 进行健康检查

    使用 GET /proxies/{name}/delay 替代 TCP 直连，适配 GitHub Actions 环境。
    返回 True 表示节点健康，False 表示失效。
    """
    import requests
    name = node.get("name", "")
    if not name:
        return False
    try:
        url = f"http://127.0.0.1:{clash_api_port}/proxies/{requests.utils.quote(name)}/delay"
        resp = requests.get(url, params={"timeout": timeout * 1000, "url": "https://www.gstatic.com/generate_204"}, timeout=timeout + 2)
        if resp.status_code == 200:
            data = resp.json()
            delay = data.get("delay", 0)
            logger.debug(f"health_clash: {name} OK ({delay}ms)")
            return True
        else:
            logger.debug(f"health_clash: {name} FAIL (HTTP {resp.status_code})")
            return False
    except (requests.RequestException, ValueError, OSError) as e:
        logger.debug(f"health_clash: {name} FAIL: {e}")
        return False


def batch_health_check_via_clash(nodes: list[dict], clash_api_port: int = 9090,
                                 timeout: int = 5, max_workers: int = 10) -> dict[str, str]:
    """v28.87: 批量通过 Clash API 健康检查，返回 {key: status}

    借鉴 discovery-service 的机制：
    - 每次检查后更新运行时健康状态
    - 连续失败3次的节点标记为 disabled
    - 返回每个节点的健康状态
    """
    import concurrent.futures

    def _check(node):
        key = get_runtime_health_key(node)
        is_healthy = health_check_via_clash(node, clash_api_port, timeout)
        status = record_health_result(node, is_healthy)
        return key, status

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_node = {executor.submit(_check, node): node for node in nodes}
        for future in concurrent.futures.as_completed(future_to_node):
            try:
                key, status = future.result()
                results[key] = status
            except (OSError, ValueError, TypeError):
                node = future_to_node[future]
                key = get_runtime_health_key(node)
                status = record_health_result(node, False)
                results[key] = status

    return results


def health_check(node: dict, timeout: int = 5) -> bool:
    """健康检查：TCP 连接测试（兼容旧接口）

    返回 True 表示节点健康，False 表示失效。
    """
    import socket
    import time

    server = node.get("server", "")
    port = node.get("port", 0)
    if not server or not port:
        return False

    try:
        port_i = int(port)
    except (ValueError, TypeError):
        return False

    tcp_start = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((server, port_i))
        tcp_latency = (time.time() - tcp_start) * 1000
        logger.debug(f"health_check: {server}:{port_i} OK ({tcp_latency:.0f}ms)")
        return True
    except (OSError, ValueError, TypeError) as e:
        logger.debug(f"health_check: {server}:{port_i} FAIL: {e}")
        return False


def batch_health_check(nodes: list[dict], max_workers: int = 50, timeout: int = 5) -> dict[str, bool]:
    """批量健康检查（TCP 直连），返回 {node_id: is_healthy}

    兼容旧接口。新代码应使用 batch_health_check_via_clash。
    """
    import concurrent.futures

    def _check(node):
        node_id = f"{node.get('name', '')}@{node.get('server', '')}:{node.get('port', '')}"
        return node_id, health_check(node, timeout)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_node = {executor.submit(_check, node): node for node in nodes}
        for future in concurrent.futures.as_completed(future_to_node):
            try:
                node_id, is_healthy = future.result()
                results[node_id] = is_healthy
            except (OSError, ValueError, TypeError):
                node = future_to_node[future]
                node_id = f"{node.get('name', '')}@{node.get('server', '')}:{node.get('port', '')}"
                results[node_id] = False

    return results
