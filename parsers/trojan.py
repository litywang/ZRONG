# parsers/trojan.py - Trojan 链接解析
# 从 crawler.py 原 parse_trojan 和 parse_trojan_go 函数迁移

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode, generate_unique_id

logger = logging.getLogger(__name__)

def parse_trojan(node: str) -> dict | None:
    """解析 trojan:// 链接，返回 dict（兼容层）。内部使用 ProxyNode 结构化存储。"""
    try:
        if not node.startswith("trojan://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = p_url.username or unquote(p_url.path.strip("/"))
        if not pwd:
            return None
        params = parse_qs(p_url.query)
        def gp(k): return params.get(k, [""])[0]

        # 从 URL fragment 提取原始名称
        original_name = p_url.fragment if p_url.fragment else f"TJ-{generate_unique_id({'server': p_url.hostname, 'port': _safe_port(p_url.port), 'password': pwd})}"

        node_obj = ProxyNode(
            protocol="trojan",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            name=original_name,
            password=pwd,
            skip_cert_verify=True
        )
        node_obj.sni = gp("sni") or node_obj.server
        
        # BUGFIX v28.20: 解析 WS/GRPC 传输层参数
        ttype = gp("type")
        if ttype == "ws":
            node_obj.network = "ws"
            wo = {}
            if gp("path"):
                wo["path"] = gp("path")
            if gp("host"):
                wo["headers"] = {"Host": gp("host")}
            if wo:
                node_obj.ws_opts = wo
        elif ttype == "grpc":
            node_obj.network = "grpc"
            if gp("serviceName"):
                node_obj.grpc_opts = {"grpc-service-name": gp("serviceName")}
        
        alpn = gp("alpn")
        if alpn:
            node_obj._extra["alpn"] = [a.strip() for a in alpn.split(",")]
        
        fp = gp("fp")
        if fp:
            node_obj._extra["client-fingerprint"] = fp
        
        return node_obj.to_dict()
    except Exception as e:
        logger.debug(f"[parse_trojan] 解析失败: {e}", exc_info=True)
        return None


def parse_trojan_go(node: str) -> dict | None:
    """解析 trojan-go:// 链接（trojan-go 扩展协议），返回 dict（兼容层）。"""
    try:
        if not node.startswith("trojan-go://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = unquote(p_url.username or "")
        if not pwd:
            return None
        params = parse_qs(p_url.query)
        def gp(k): return params.get(k, [""])[0]

        node_obj = ProxyNode(
            protocol="trojan",
            server=p_url.hostname,
            port=_safe_port(p_url.port),
            name=p_url.fragment if p_url.fragment else f"TG-{generate_unique_id({'server': p_url.hostname, 'port': _safe_port(p_url.port), 'password': pwd})}",
            password=pwd,
            skip_cert_verify=True
        )
        node_obj.sni = gp("sni") or node_obj.server
        
        # trojan-go ws 扩展
        ttype = gp("type")
        if ttype == "ws":
            node_obj.network = "ws"
            wo = {}
            if gp("path"):
                wo["path"] = gp("path")
            if gp("host"):
                wo["headers"] = {"Host": gp("host")}
            if wo:
                node_obj.ws_opts = wo
        
        fp = gp("fp")
        if fp:
            node_obj._extra["client-fingerprint"] = fp
        
        return node_obj.to_dict()
    except Exception as e:
        logger.debug(f"[parse_trojan_go] 解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default
