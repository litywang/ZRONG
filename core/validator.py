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
    """v28.16: 增强亚洲节点检测（关键词+IP地理位置+SNI+域名TLD）

    延迟导入 utils 中的常量，避免循环依赖。
    """
    from utils import is_pure_ip, ASIA_REGIONS
    from core.scorer import _get_limiter
    if not p or not isinstance(p, dict):
        return False
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
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
