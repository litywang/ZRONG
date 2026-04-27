# parsers/__init__.py - 导出所有解析器，方便 crawler.py 导入
from .vmess import parse_vmess
from .vless import parse_vless
from .trojan import parse_trojan, parse_trojan_go
from .ss import parse_ss, parse_ssr
from .hysteria import parse_hysteria, parse_hysteria2
from .tuic import parse_tuic
from .snell import parse_snell
from .socks import parse_http_proxy, parse_socks
from .anytls import parse_anytls
from .dispatch import parse_node

__all__ = [
    "parse_vmess", "parse_vless", "parse_trojan", "parse_trojan_go",
    "parse_ss", "parse_ssr", "parse_hysteria", "parse_hysteria2",
    "parse_tuic", "parse_snell", "parse_http_proxy", "parse_socks",
    "parse_anytls", "parse_node",
]
