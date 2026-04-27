# parsers/common.py - 解析器公共定义（从 crawler.py 提取）
# 包含 ProxyNode 数据模型、辅助函数，供所有解析器使用

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import hashlib
import base64
import logging

# ========== ProxyNode 数据模型 ==========
@dataclass
class ProxyNode:
    """结构化代理节点数据模型，替代 dict 作为内部统一格式。

    兼容 dict 回退：所有属性提供默认值，parse_* 函数返回的 dict 仍可透明使用。
    """
    # 核心字段（必须有）
    protocol: str = "unknown"
    server: str = ""
    port: int = 0
    # 协议相关字段
    name: str = ""
    cipher: str = ""
    password: str = ""
    uuid: str = ""
    sni: str = ""
    host: str = ""
    path: str = ""
    alpn: str = ""
    # 协议辅助字段
    alterId: int = 0
    network: str = "tcp"
    tls: bool = False
    udp: bool = True
    skip_cert_verify: bool = True
    # Clash 特有字段
    ws_opts: Optional[Dict] = None  # ws-opts
    grpc_opts: Optional[Dict] = None  # grpc-opts
    h2_opts: Optional[Dict] = None  # h2-opts
    hysteria_opts: Optional[Dict] = None  # hysteria2 特有
    tuic_opts: Optional[Dict] = None  # tuic 特有
    vless_opts: Optional[Dict] = None  # vlessreality 等
    # 内部评分/元数据
    _score: float = 0.0
    _src_weight: float = 0.0
    _mainland_reachable: bool = False
    # 原始解析数据（供 to_dict 使用）
    _extra: Dict[str, Any] = field(default_factory=dict)

    def dedup_key(self) -> str:
        """生成去重键（基于协议/服务器/端口/认证信息）。"""
        uid = self.uuid or self.password or ""
        return hashlib.md5(
            f"{self.protocol}|{self.server}|{self.port}|{uid}|{self.path}|{self.sni}".encode(),
            usedforsecurity=False,
        ).hexdigest()

    def to_dict(self) -> Dict:
        """转换为 Clash 配置 dict 格式（供 create_config 使用）。"""
        name = self.name or f"{self.protocol.upper()}-{self.server}:{self.port}"
        p = {"name": name, "type": self.protocol, "server": self.server, "port": self.port, "udp": True, "skip-cert-verify": self.skip_cert_verify}

        if self.protocol in ("ss", "ss2022"):
            p.update({"cipher": self.cipher or "aes-128-gcm", "password": self.password})
        elif self.protocol == "vmess":
            p.update({"uuid": self.uuid, "alterId": self.alterId, "cipher": "auto"})
            if self.network in ("ws", "h2", "grpc"):
                p["network"] = self.network
            if self.tls:
                p["tls"] = True
                p["sni"] = self.sni or self.host or self.server
            if self.network == "ws" and self.ws_opts:
                p["ws-opts"] = self.ws_opts
            elif self.network == "grpc" and self.grpc_opts:
                p["grpc-opts"] = self.grpc_opts
            elif self.network == "h2" and self.h2_opts:
                p["h2-opts"] = self.h2_opts
        elif self.protocol == "vless":
            p.update({"uuid": self.uuid})
            if self.tls:
                p["tls"] = True
                p["sni"] = self.sni or self.server
            if self.network in ("ws", "grpc"):
                p["network"] = self.network
                if self.ws_opts:
                    p["ws-opts"] = self.ws_opts
            if self.vless_opts:
                p.update(self.vless_opts)
        elif self.protocol == "trojan":
            p.update({"password": self.password or "", "tls": True, "sni": self.sni or self.server})
        elif self.protocol in ("hysteria", "hysteria2", "hy2"):
            p["type"] = "hysteria2"
            p.update({"password": self.password or "", "sni": self.sni or self.server})
            if self.hysteria_opts:
                p.update(self.hysteria_opts)
            else:
                # v28.39: 确保 hysteria2 基础字段存在
                p.update({"up": "100 Mbps", "down": "100 Mbps"})
        elif self.protocol == "tuic":
            p["type"] = "tuic"
            p.update({"uuid": self.uuid, "password": self.password, "sni": self.sni or self.server})
            if self.tuic_opts:
                p.update(self.tuic_opts)
            else:
                # v28.39: 确保 tuic 基础字段存在
                p.update({"congestion-controller": "bbr"})
        elif self.protocol == "ssr":
            p.update({"cipher": self.cipher, "password": self.password})
            if self._extra:
                p.update(self._extra)
        elif self.protocol in ("socks5", "socks4"):
            p["type"] = self.protocol
            if self._extra.get("username"):
                p["username"] = self._extra["username"]
            if self._extra.get("password"):
                p["password"] = self._extra["password"]
        elif self.protocol in ("http", "https"):
            p["type"] = self.protocol
            if self._extra.get("username"):
                p["username"] = self._extra["username"]
            if self._extra.get("password"):
                p["password"] = self._extra["password"]
        elif self.protocol == "anytls":
            p["type"] = "anytls"
            p.update({"password": self.password or "", "tls": True, "sni": self.sni or self.server})
            if self._extra.get("client-fingerprint"):
                p["client-fingerprint"] = self._extra["client-fingerprint"]
        elif self.protocol == "snell":
            p.update({"password": self.password or ""})

        # 合并 _extra 中的其他字段（用于 ssr 等特殊字段）
        for k, v in self._extra.items():
            if k not in p:
                p[k] = v

        return p

    @staticmethod
    def from_dict(d: Dict) -> "ProxyNode":
        """从 dict（现有 parse_* 函数返回值）构造 ProxyNode。"""
        return ProxyNode(
            protocol=d.get("type", "unknown"),
            server=d.get("server", ""),
            port=d.get("port", 0),
            name=d.get("name", ""),
            cipher=d.get("cipher", ""),
            password=d.get("password", ""),
            uuid=d.get("uuid", ""),
            sni=d.get("sni", ""),
            host=d.get("host", ""),
            path=d.get("path", ""),
            alpn=d.get("alpn", ""),
            alterId=d.get("alterId", 0),
            network=d.get("network", "tcp"),
            tls=bool(d.get("tls", False)),
            udp=bool(d.get("udp", True)),
            skip_cert_verify=bool(d.get("skip-cert-verify", True)),
            ws_opts=d.get("ws-opts"),
            grpc_opts=d.get("grpc-opts"),
            h2_opts=d.get("h2-opts"),
            hysteria_opts=d.get("hysteria_opts"),
            tuic_opts=d.get("tuic_opts"),
            vless_opts=d.get("vless_opts"),
            _score=d.get("_score", 0.0),
            _src_weight=d.get("_src_weight", 0.0),
            _mainland_reachable=d.get("_mainland_reachable", False),
            _extra={k: v for k, v in d.items() if k.startswith("_") or k in ("protocol", "obfs", "obfs-param", "protocol-param", "group")}
        )


def generate_unique_id(proxy):
    """生成节点唯一 ID（与 crawler.py 原逻辑一致）"""
    key = f"{proxy.get('server', '')}:{proxy.get('port', '')}:{proxy.get('uuid', proxy.get('password', ''))}"
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8].upper()


def _safe_port(val, default=443):
    """端口安全转换（与 crawler.py 原逻辑一致）"""
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default


from urllib.parse import urlparse, unquote, parse_qs

# 日志配置 - v28.39: 使用 NullHandler 避免重复配置
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
