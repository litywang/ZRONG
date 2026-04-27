# parsers/ss.py - SS/SSR 链接解析
# 从 crawler.py 原 parse_ss 和 parse_ssr 函数迁移

import base64
import logging
from .common import ProxyNode, generate_unique_id

logger = logging.getLogger(__name__)

def parse_ss(node: str) -> dict | None:
    """解析 ss:// 链接，返回 dict（兼容层）。内部使用 ProxyNode 结构化存储。"""
    try:
        if not node.startswith("ss://"):
            return None
        parts = node[5:].split("#")
        info = parts[0]
        # 从 URL fragment 提取原始名称
        original_name = parts[1] if len(parts) > 1 else None
        try:
            m_info = len(info) % 4
            info_padded = info + "=" * (4 - m_info) if m_info else info
            decoded = base64.b64decode(info_padded).decode("utf-8", errors="ignore")
            method_pwd, server_info = decoded.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        except Exception:
            logger.debug("Exception occurred", exc_info=True)
            method_pwd, server_info = info.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        server, port = server_info.rsplit(":", 1)  # BUGFIX v28.20: 用 rsplit 从右拆分，兼容 IPv6
        # 去除 IPv6 方括号
        if server.startswith("[") and server.endswith("]"):
            server = server[1:-1]

        # 如果没有原始名称，生成默认名称
        if not original_name:
            original_name = f"SS-{generate_unique_id({'server': server, 'port': _safe_port(port), 'password': pwd})}"

        # v28.26: 使用 ProxyNode 结构化存储
        node_obj = ProxyNode(
            protocol="ss",
            server=server,
            port=_safe_port(port),
            name=original_name,
            cipher=method,
            password=pwd,
            udp=True
        )
        # 向后兼容：返回 dict
        return node_obj.to_dict()
    except Exception as e:
        logger.debug(f"[parse_ss] 解析失败: {e}", exc_info=True)
        return None


def parse_ssr(node: str) -> dict | None:
    """解析 SSR:// 链接，返回 dict（兼容层）。内部使用 ProxyNode 结构化存储。"""
    try:
        if not node.startswith("ssr://"):
            return None
        raw_b64 = node[6:]
        m_raw = len(raw_b64) % 4
        raw_padded = raw_b64 + "=" * (4 - m_raw) if m_raw else raw_b64
        raw = base64.b64decode(raw_padded).decode("utf-8", errors="ignore")
        # SSR 格式: server:port:protocol:method:obfs:base64pass/?obfsparam=xxx&remark=xxx
        qmark_pos = raw.find("/?")
        if qmark_pos != -1:
            main = raw[:qmark_pos]
            params_str = raw[qmark_pos + 2:]
        else:
            main = raw
            params_str = ""

        segments = main.split(":")
        if len(segments) < 6:
            return None
        b64pass = segments[-1]
        obfs = segments[-2]
        method = segments[-3]
        protocol = segments[-4]
        port_str = segments[-5]
        server = ":".join(segments[:-5])

        try:
            port = int(port_str)
            if port <= 0 or port > 65535:
                return None
            m_pass = len(b64pass) % 4
            pass_padded = b64pass + "=" * (4 - m_pass) if m_pass else b64pass
            password = base64.b64decode(pass_padded).decode("utf-8", errors="ignore")
        except ValueError:
            return None

        # 从参数提取备注名称
        name = ""
        if params_str:
            from urllib.parse import parse_qs
            params = parse_qs(params_str)
            remark_b64 = params.get("remarks", [""])[0]
            if remark_b64:
                m_rem = len(remark_b64) % 4
                rem_padded = remark_b64 + "=" * (4 - m_rem) if m_rem else remark_b64
                name = base64.b64decode(rem_padded).decode("utf-8", errors="ignore")

        if not name:
            uid = generate_unique_id({"server": server, "port": port})
            name = f"SR-{uid}"

        # 提取 obfsparam 和 protoparam
        obfs_param = ""
        proto_param = ""
        if params_str:
            from urllib.parse import parse_qs
            params = parse_qs(params_str)
            obfs_param_b64 = params.get("obfsparam", [""])[0]
            if obfs_param_b64:
                m_obfs = len(obfs_param_b64) % 4
                obfs_padded = obfs_param_b64 + "=" * (4 - m_obfs) if m_obfs else obfs_param_b64
                obfs_param = base64.b64decode(obfs_padded).decode("utf-8", errors="ignore")
            proto_param_b64 = params.get("protoparam", [""])[0]
            if proto_param_b64:
                m_proto = len(proto_param_b64) % 4
                proto_padded = proto_param_b64 + "=" * (4 - m_proto) if m_proto else proto_param_b64
                proto_param = base64.b64decode(proto_padded).decode("utf-8", errors="ignore")

        # v28.27: 使用 ProxyNode 结构化存储
        node_obj = ProxyNode(
            protocol="ssr",
            server=server,
            port=port,
            name=name,
            cipher=method,
            password=password
        )
        node_obj._extra["protocol"] = protocol
        node_obj._extra["obfs"] = obfs
        if obfs_param:
            node_obj._extra["obfs-param"] = obfs_param
        if proto_param:
            node_obj._extra["protocol-param"] = proto_param
        
        # 向后兼容：返回 dict
        return node_obj.to_dict()
    except Exception as e:
        logger.debug(f"[parse_ssr] 解析失败: {e}", exc_info=True)
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
