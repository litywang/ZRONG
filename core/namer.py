# core/namer.py - NodeNamer
# v29.01: 修复命名格式，增加协议+速度标识

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
        """命名 = 国旗+序号-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
        
        格式: 🇸🇬1-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
              🇭🇰2-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
        """
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        
        return f"{code}{num}-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"