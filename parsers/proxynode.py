# parsers/proxynode.py - ProxyNode 模型定义（v28.52）
# 独立文件避免循环导入：crawler.py、parsers/*.py 均可直接导入
# 不依赖 crawler 模块，保持导入层级干净
from pydantic import BaseModel, Field, field_validator, ConfigDict, PrivateAttr
from typing import Dict, Any, Optional
import hashlib
import time


class ProxyNode(BaseModel):
    """Pydantic V2 强类型节点模型，替代原dataclass。
    
    保留所有原有字段，新增字段校验和自动填充逻辑。
    """
    model_config = ConfigDict(extra="allow")  # 允许 _extra 等额外字段

    # 核心字段（必须有）
    protocol: str = Field(default="unknown", min_length=1, description="节点协议类型")
    server: str = Field(default="", min_length=1, description="节点服务器地址")
    port: int = Field(default=0, le=65535, description="节点端口")
    # 协议相关字段
    name: str = ""
    cipher: str = ""
    password: str = ""
    uuid: str = ""
    sni: str = ""
    host: str = ""
    path: str = ""
    alpn: str = ""

    @field_validator('alpn', mode='before')
    @classmethod
    def validate_alpn(cls, v):
        """兼容alpn为列表或字符串，统一转为逗号分隔字符串"""
        if isinstance(v, list):
            return ','.join(str(item) for item in v)
        return str(v) if v is not None else ""

    # 协议辅助字段
    alterId: int = 0
    network: str = "tcp"
    tls: bool = False
    udp: bool = True
    skip_cert_verify: bool = True
    # Clash 特有字段
    ws_opts: Optional[Dict] = Field(default=None, description="ws-opts配置")
    grpc_opts: Optional[Dict] = Field(default=None, description="grpc-opts配置")
    h2_opts: Optional[Dict] = Field(default=None, description="h2-opts配置")
    hysteria_opts: Optional[Dict] = Field(default=None, description="hysteria2特有配置")
    tuic_opts: Optional[Dict] = Field(default=None, description="tuic特有配置")
    vless_opts: Optional[Dict] = Field(default=None, description="vless相关配置")
    # 内部评分/元数据（Pydantic私有属性，不参与序列化）
    _score: float = PrivateAttr(default=0.0)
    _src_weight: float = PrivateAttr(default=0.0)
    _mainland_reachable: bool = PrivateAttr(default=False)
    _region: str = PrivateAttr(default="")
    _rtt: float = PrivateAttr(default=0.0)
    # 原始解析数据（供 to_dict 使用）
    _extra: Dict[str, Any] = PrivateAttr(default_factory=dict)

    @field_validator('sni', mode='before')
    @classmethod
    def auto_fill_sni(cls, v, info):
        """SNI缺失时自动用server填充"""
        if not v:
            return info.data.get('server', '')
        return v

    def dedup_key(self) -> str:
        """生成去重键（六元组：协议/服务器/端口/认证/路径/主机）。
        
        v28.51: 扩展为六元组去重，区分同一服务器不同配置变体。
        """
        uid = self.uuid or self.password or ""
        # host 来源优先级：ws-opts.host > servername > sni > host
        host = ""
        if self.ws_opts and isinstance(self.ws_opts, dict):
            host = self.ws_opts.get("host", "")
        if not host:
            host = self.vless_opts.get("host", "") if self.vless_opts else ""
        if not host:
            host = self.h2_opts.get("host", [""])[0] if self.h2_opts else ""
        if not host:
            host = self.sni or self.host or ""
        # path 来源优先级：ws-opts.path > h2-opts.path > path
        path = self.path or ""
        if not path and self.ws_opts and isinstance(self.ws_opts, dict):
            path = self.ws_opts.get("path", "")
        if not path and self.h2_opts and isinstance(self.h2_opts, dict):
            path = self.h2_opts.get("path", "")
        return hashlib.md5(
            f"{self.protocol}|{self.server}|{self.port}|{uid}|{path}|{host}".encode(),
            usedforsecurity=False,
        ).hexdigest()

    def to_dict(self) -> Dict:
        """转换为 Clash 配置 dict 格式（供 create_config 使用），注入Meta信息。"""
        # 生成带Meta的节点名（区域emoji + 延迟 + 评分）
        emoji = ""
        if self._region:
            try:
                from utils import _cc_to_flag
                emoji = _cc_to_flag(self._region) + " "
            except ImportError:
                pass
        delay_str = f"{self._rtt*1000:.0f}ms" if self._rtt else "N/A"
        score_str = f"{self._score:.2f}" if self._score else "0.00"
        base_name = self.name or f"{self.protocol.upper()}-{self.server}:{self.port}"
        name = f"{emoji}{base_name} | {delay_str} | 评分{score_str}"
        
        p = {"name": name, "type": self.protocol, "server": self.server, "port": self.port, "udp": True, "skip-cert-verify": self.skip_cert_verify}
        
        # 添加Clash Meta字段（供客户端智能排序）
        p["meta"] = {
            "test_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "protocol": self.protocol,
            "rtt_ms": round(self._rtt * 1000, 0) if self._rtt else None,
            "alive_score": round(self._score, 3) if self._score else 0.0,
            "region": self._region,
            "mainland_reachable": self._mainland_reachable
        }

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
        elif self.protocol == "tuic":
            p["type"] = "tuic"
            p.update({"uuid": self.uuid, "password": self.password, "sni": self.sni or self.server})
            if self.tuic_opts:
                p.update(self.tuic_opts)
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
        alpn_val = d.get("alpn", "")
        # v28.42: 规范化 alpn（TUIC 解析器输出 list，其他输出 string）
        if isinstance(alpn_val, list):
            alpn_val = ",".join(str(a) for a in alpn_val)

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
            alpn=alpn_val,
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
