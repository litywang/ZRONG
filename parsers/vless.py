# parsers/vless.py - VLESS 链接解析
# 从 crawler.py 原 parse_vless 函数迁移，保留 ProxyNode 兼容

import logging
from urllib.parse import urlparse, unquote, parse_qs
from .common import ProxyNode, generate_unique_id

logger = logging.getLogger(__name__)

def parse_vless(node: str) -> dict | None:
    """解析 vless:// 链接，返回 dict（兼容层）。内部使用 ProxyNode 结构化存储。"""
    try:
        if not node.startswith("vless://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        uuid = p_url.username or ""
        if not uuid:
            return None
        params = parse_qs(p_url.query)
        def gp(k): return params.get(k, [""])[0]
        sec = gp("security")

        # 从 URL fragment 提取原始名称
        original_name = p_url.fragment if p_url.fragment else f"VL-{generate_unique_id({'server': p_url.hostname, 'port': _safe_port(p_url.port), 'uuid': uuid})}"

        port_val = _safe_port(p_url.port)
        
        node_obj = ProxyNode(
            protocol="vless",
            server=p_url.hostname,
            port=port_val,
            name=original_name,
            uuid=uuid,
            skip_cert_verify=True
        )
        
        if sec in ["tls", "reality"]:
            node_obj.tls = True
            node_obj.sni = gp("sni") or node_obj.server
        if sec == "reality":
            pbk, sid = gp("pbk"), gp("sid")
            if pbk and sid:
                node_obj.vless_opts = {"reality-opts": {"public-key": pbk, "short-id": sid}}
            else:
                return None
        fp = gp("fp")
        if fp:
            node_obj.vless_opts = node_obj.vless_opts or {}
            node_obj.vless_opts["client-fingerprint"] = fp
        else:
            node_obj.vless_opts = node_obj.vless_opts or {}
            node_obj.vless_opts["client-fingerprint"] = "chrome"
        
        flow = gp("flow")
        _VALID_FLOWS = {'', 'xtls-rprx-vision', 'xtls-rprx-vision-udp443'}
        if flow not in _VALID_FLOWS:
            if flow:
                logger.debug("VLESS illegal flow value: %s, ignored", flow)
            flow = ''
        if flow:
            node_obj.vless_opts = node_obj.vless_opts or {}
            node_obj.vless_opts["flow"] = flow
        
        tp = gp("type")
        if tp == "ws":
            node_obj.network = "ws"
            wo = {}
            if gp("path"):
                wo["path"] = gp("path")
            if gp("host"):
                wo["headers"] = {"Host": gp("host")}
            if wo:
                node_obj.ws_opts = wo
        elif tp == "grpc":
            node_obj.network = "grpc"
            if gp("serviceName"):
                node_obj.grpc_opts = {"grpc-service-name": gp("serviceName")}
        
        # 向后兼容：返回 dict
        return node_obj.to_dict()
    except Exception as e:
        logger.debug(f"VLESS解析失败: {e}", exc_info=True)
        return None


def _safe_port(val, default=443):
    """端口安全转换"""
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default
