# parsers/tuic.py - TUIC 链接解析
# 从 crawler.py 原 parse_tuic 函数迁移

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode

logger = logging.getLogger(__name__)

def parse_tuic(node: str) -> dict | None:
    """解析 tuic:// 链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("tuic://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        uuid_val = p_url.username or ""
        tuic_password = p_url.password or uuid_val
        params = parse_qs(p_url.query)
        def gp(k):
            return params.get(k, [""])[0]

        node_obj = ProxyNode(
            protocol="tuic",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            uuid=uuid_val,
            password=tuic_password,
            skip_cert_verify=True
        )

        sni = gp("sni")
        if sni:
            node_obj.sni = sni

        fp = gp("fp")
        if fp:
            node_obj._extra["client-fingerprint"] = fp

        alpn = gp("alpn")
        if alpn:
            node_obj._extra["alpn"] = [a.strip() for a in alpn.split(",")]

        return node_obj.to_dict() if node_obj.server else None
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as e:
        logger.debug(f"[parse_tuic] 解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default
