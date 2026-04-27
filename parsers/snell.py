# parsers/snell.py - Snell 链接解析
# 从 crawler.py 原 parse_snell 函数迁移

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode, generate_unique_id

logger = logging.getLogger(__name__)

def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default

def parse_snell(node: str) -> dict | None:
    """解析 snell:// 链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("snell://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = unquote(p_url.username or "")

        node_obj = ProxyNode(
            protocol="snell",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            password=pwd,
            udp=True
        )

        node_obj.name = p_url.fragment if p_url.fragment else f"SN-{generate_unique_id({'server': p_url.hostname, 'port': node_obj.port})}"

        params = parse_qs(p_url.query)
        def gp(k):
            return params.get(k, [""])[0]

        obfs = gp("obfs")
        if obfs:
            node_obj._extra["obfs-opts"] = {"mode": obfs}

        version = gp("version")
        if version:
            node_obj._extra["version"] = int(version)

        return node_obj.to_dict() if node_obj.server else None
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as e:
        logger.debug(f"[parse_snell] 解析失败: {e}", exc_info=True)
        return None
