# parsers/dispatch.py - 协议调度解析器
# 从 crawler.py 原 parse_node 函数迁移，自动根据链接前缀选择对应解析器

import logging
from .vmess import parse_vmess
from .vless import parse_vless
from .trojan import parse_trojan, parse_trojan_go
from .ss import parse_ss, parse_ssr
from .hysteria import parse_hysteria, parse_hysteria2
from .tuic import parse_tuic
from .snell import parse_snell
from .socks import parse_http_proxy, parse_socks
from .anytls import parse_anytls

logger = logging.getLogger(__name__)

def parse_node(node: str) -> dict | None:
    """统一解析入口，根据链接前缀自动选择解析器"""
    node = node.strip()
    if not node or node.startswith("#"):
        return None
    if node.startswith("vmess://"):
        return parse_vmess(node)
    elif node.startswith("vless://"):
        return parse_vless(node)
    elif node.startswith("trojan://"):
        return parse_trojan(node)
    elif node.startswith("ss://"):
        return parse_ss(node)
    elif node.startswith("ssr://"):
        return parse_ssr(node)
    elif node.startswith("hysteria2://") or node.startswith("hy2://"):
        return parse_hysteria2(node)
    elif node.startswith("hysteria://"):
        return parse_hysteria(node)
    elif node.startswith("tuic://"):
        return parse_tuic(node)
    elif node.startswith("snell://"):
        return parse_snell(node)
    elif node.startswith("socks5://") or node.startswith("socks4://"):
        return parse_socks(node)
    elif node.startswith("http://") or node.startswith("https://"):
        return parse_http_proxy(node)
    elif node.startswith("anytls://"):
        return parse_anytls(node)
    elif node.startswith("trojan-go://"):
        return parse_trojan_go(node)
    return None
