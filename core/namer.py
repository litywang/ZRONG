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
        """v29.01: 命名 = emoji区域-编号 | 延迟ms | 协议 | TCP标记
        
        格式: 🇯🇵JP01 | 347ms | VL | ✓  (大陆可达)
              🇭🇰HK02 | 120ms | TR | TCP (仅TCP通过)
        """
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        
        # 区域编号
        region_tag = f"{region}{num:02d}"
        
        # 延迟
        lat_str = f"{int(lat)}ms" if lat is not None and lat < 9999 else "timeout"
        
        # 协议缩写
        proto_str = PROTO_SHORT.get(proto or "", proto or "?")
        
        # 速度KB/s（仅真实测速有值）
        speed_str = ""
        if speed is not None and speed > 0:
            # speed是KB/s
            if speed >= 1000:
                speed_str = f"|{speed/1000:.1f}MB/s"
            elif speed > 10:
                speed_str = f"|{speed:.0f}KB/s"
        
        # 大陆可达标记
        ml_str = "|✓" if mainland_reachable else ""
        
        # TCP补充标记
        tcp_str = "|TCP" if tcp else ""
        
        # 评分标记（高分节点）
        score_str = ""
        if score is not None and score >= 60:
            score_str = f"|s{int(score)}"
        
        return f"{code}{region_tag} | {lat_str} | {proto_str}{speed_str}{ml_str}{tcp_str}{score_str}"