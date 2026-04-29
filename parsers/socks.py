# parsers/socks.py - HTTP/SOCKS 代理链接解析
# 从 crawler.py 原 parse_http_proxy / parse_socks 函数迁移

import logging
from urllib.parse import urlparse, unquote
from .common import ProxyNode, generate_unique_id

logger = logging.getLogger(__name__)

def parse_http_proxy(node: str) -> dict | None:
    """解析 http:// / https:// 代理链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("http://") and not node.startswith("https://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        username = unquote(p_url.username or "")
        password = unquote(p_url.password or "")
        ptype = "https" if node.startswith("https://") else "http"

        node_obj = ProxyNode(
            protocol=ptype,
            server=p_url.hostname,
            port=_safe_port(p_url.port, 443 if ptype == "https" else 80),
        )
        node_obj.name = p_url.fragment if p_url.fragment else f"HT-{generate_unique_id({'server': p_url.hostname, 'port': node_obj.port})}"

        if username:
            node_obj._extra["username"] = username
        if password:
            node_obj._extra["password"] = password

        d = node_obj.to_dict()
        if username:
            d["username"] = username
        if password:
            d["password"] = password
        return d
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as e:
        logger.debug(f"[parse_http_proxy] 解析失败: {e}", exc_info=True)
        return None


def parse_socks(node: str) -> dict | None:
    """解析 socks5:// / socks4:// 链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("socks5://") and not node.startswith("socks4://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        username = unquote(p_url.username or "")
        password = unquote(p_url.password or "")
        ptype = "socks5" if node.startswith("socks5://") else "socks4"

        node_obj = ProxyNode(
            protocol=ptype,
            server=p_url.hostname,
            port=_safe_port(p_url.port, 1080),
        )
        node_obj.name = p_url.fragment if p_url.fragment else f"SK-{generate_unique_id({'server': p_url.hostname, 'port': node_obj.port})}"

        if username:
            node_obj._extra["username"] = username
        if password:
            node_obj._extra["password"] = password

        d = node_obj.to_dict()
        if username:
            d["username"] = username
        if password:
            d["password"] = password
        return d
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as e:
        logger.debug(f"[parse_socks] 解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default
