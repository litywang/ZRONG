# parsers/hysteria.py - Hysteria/Hysteria2 链接解析
# 从 crawler.py 原 parse_hysteria / parse_hysteria2 函数迁移

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode

logger = logging.getLogger(__name__)

def parse_hysteria2(node: str) -> dict | None:
    """解析 hysteria2:// 链接，返回 dict（兼容层）。"""
    try:
        if not node.startswith("hysteria2://") and not node.startswith("hy2://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        def gp(k): return params.get(k, [""])[0]

        node_obj = ProxyNode(
            protocol="hysteria2",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            password=pwd,
            skip_cert_verify=True
        )
        
        sni = gp("sni")
        if sni:
            node_obj.sni = sni
        elif p_url.hostname:
            node_obj.sni = p_url.hostname
        
        obfs = gp("obfs")
        if obfs:
            node_obj.hysteria_opts = node_obj.hysteria_opts or {}
            node_obj.hysteria_opts["obfs"] = obfs
        
        obfs_password = gp("obfs-password")
        if obfs_password:
            node_obj.hysteria_opts = node_obj.hysteria_opts or {}
            node_obj.hysteria_opts["obfs-password"] = obfs_password
        
        insecure = gp("insecure")
        if insecure == "1":
            node_obj.skip_cert_verify = True
        
        fp = gp("fp")
        if fp:
            node_obj._extra["client-fingerprint"] = fp
        
        return node_obj.to_dict() if node_obj.server else None
    except Exception as e:
        logger.debug(f"[parse_hysteria2] 解析失败: {e}", exc_info=True)
        return None


def parse_hysteria(node: str) -> dict | None:
    """解析 hysteria:// 链接（v1），返回 dict（兼容层）。"""
    try:
        if not node.startswith("hysteria://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        def gp(k): return params.get(k, [""])[0]

        node_obj = ProxyNode(
            protocol="hysteria",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            password=pwd,
            skip_cert_verify=True
        )
        
        sni = gp("sni")
        if sni:
            node_obj.sni = sni
        
        obfs = gp("obfs")
        if obfs:
            node_obj.hysteria_opts = node_obj.hysteria_opts or {}
            node_obj.hysteria_opts["obfs"] = obfs
        
        auth_str = gp("auth")
        if auth_str:
            node_obj.hysteria_opts = node_obj.hysteria_opts or {}
            node_obj.hysteria_opts["auth_str"] = auth_str
        
        alpn = gp("alpn")
        if alpn:
            node_obj._extra["alpn"] = [a.strip() for a in alpn.split(",")]
        
        insecure = gp("insecure")
        if insecure == "1":
            node_obj.skip_cert_verify = True
        
        return node_obj.to_dict() if node_obj.server else None
    except Exception as e:
        logger.debug(f"[parse_hysteria] 解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default
