# parsers/vmess.py - VMess 链接解析
# 从 crawler.py 原 parse_vmess 函数迁移，保留 ProxyNode 兼容

import base64
import json
import logging
from .common import ProxyNode

logger = logging.getLogger(__name__)

def parse_vmess(node: str) -> dict | None:
    """解析 vmess:// 链接，返回 dict（兼容层）。内部使用 ProxyNode 结构化存储。"""
    try:
        if not node.startswith("vmess://"):
            return None
        payload = node[8:]
        m = len(payload) % 4
        if m:
            payload += "=" * (4 - m)
        d = base64.b64decode(payload).decode("utf-8", errors="ignore")
        if not d.startswith("{"):
            return None
        c = json.loads(d)

        # 从 ps 字段提取原始名称
        original_name = c.get("ps", "")
        if not original_name:
            from .common import generate_unique_id
            uid = generate_unique_id({'server': c.get('add') or c.get('host'), 'port': _safe_port(c.get('port'), 443), 'uuid': c.get('id')})
            original_name = f"VM-{uid}"

        vmess_port = _safe_port(c.get("port"), 443)
        # v28.23: aid 参数安全转换（部分源传 "auto" 等非数字值）
        try:
            aid_val = int(c.get("aid", 0)) if str(c.get("aid", "0")).isdigit() else 0
        except (ValueError, TypeError):
            aid_val = 0

        # v28.26: 使用 ProxyNode 结构化存储
        net = c.get("net", "tcp").lower()
        ws_opts = None
        grpc_opts = None
        h2_opts = None

        if net == "ws":
            wo = {}
            if c.get("path"):
                wo["path"] = c.get("path")
            if c.get("host"):
                wo["headers"] = {"Host": c.get("host")}
            if wo:
                ws_opts = wo
        elif net == "grpc":
            if c.get("path"):
                grpc_opts = {"grpc-service-name": c.get("path")}
        elif net == "h2":
            h2o = {}
            if c.get("path"):
                h2o["path"] = c.get("path")
            if c.get("host"):
                h2o["host"] = [c.get("host")]
            if h2o:
                h2_opts = h2o

        tls = c.get("tls") in ("tls", "1", 1, True) or c.get("security") in ("tls", "1", 1, True)
        sni_val = c.get("sni") or c.get("host") or c.get("add", "")

        node_obj = ProxyNode(
            protocol="vmess",
            server=c.get("add") or c.get("host", ""),
            port=vmess_port,
            name=original_name,
            uuid=c.get("id", ""),
            alterId=aid_val,
            network=net,
            tls=tls,
            sni=sni_val,
            ws_opts=ws_opts,
            grpc_opts=grpc_opts,
            h2_opts=h2_opts,
            udp=True,
            skip_cert_verify=True
        )

        # 向后兼容：返回 dict
        return node_obj.to_dict() if node_obj.server and node_obj.uuid else None
    except (json.JSONDecodeError, base64.binascii.Error, UnicodeDecodeError, KeyError, ValueError) as e:
        logger.debug(f"VMess解析失败: {e}", exc_info=True)
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
