# core/namer.py - NodeNamer
# v30.1: 修复命名格式，去掉特殊Unicode字符，增加协议标识

import logging
from utils import get_region

# 协议缩写映射
PROTO_SHORT = {
    "vless": "VL", "vmess": "VM", "trojan": "TR", "ss": "SS",
    "hysteria2": "HY2", "hysteria": "HY", "tuic": "TU",
    "snell": "SN", "anytls": "AT", "wireguard": "WG",
    "ssr": "SR", "http": "HT", "socks5": "SK",
}


class NodeNamer:
    def __init__(self):
        self.counters = {}

    def generate(self, flag, lat=None, score=None, speed=None, tcp=False,
                 server=None, sni=None, mainland_reachable=None, proto=None):
        """命名 = 国旗+序号-协议标识

        格式: 🇸🇬1-VL (VL=VLESS)
              🇭🇰2-TR (TR=Trojan)
        """
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        # v30.1: 去掉特殊Unicode字符（Fraktur字体），改用协议缩写
        proto_short = PROTO_SHORT.get(proto, proto) if proto else ''
        suffix = f"-{proto_short}" if proto_short else ''
        return f"{code}{num}{suffix}"
