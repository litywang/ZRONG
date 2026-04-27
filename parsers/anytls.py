# parsers/anytls.py - AnyTLS 链接解析
# 从 crawler.py 原 parse_anytls 函数迁移

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode

logger = logging.getLogger(__name__)

def parse_anytls(node: str) -> dict | None:
    """解析 anytls:// 链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("anytls://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None

        node_obj = ProxyNode(
            protocol="anytls",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            skip_cert_verify=True
        )

        node_obj.name = p_url.fragment if p_url.fragment else f"AT-{generate_unique_id({'server': p_url.hostname, 'port': node_obj.port})}"

        params = parse_qs(p_url.query)
        def gp(k):
            return params.get(k, [""])[0]

        sni = gp("sni")
        if sni:
            node_obj.sni = sni
        elif p_url.hostname:
            node_obj.sni = p_url.hostname

        fp = gp("fp")
        if fp:
            node_obj._extra["client-fingerprint"] = fp

        return node_obj.to_dict() if node_obj.server else None
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError) as e:
        logger.debug(f"[parse_anytls] 解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default


from .common import generate_unique_id
