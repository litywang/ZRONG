# core/namer.py - NodeNamer
# v28.41 Phase3 重构

class NodeNamer:
    FANCY = {
        'A': '𝔄',
        'B': '𝔅',
        'C': '𝔆',
        'D': '𝔇',
        'E': '𝔈',
        'F': '𝔉',
        'G': '𝔊',
        'H': '𝔋',
        'I': 'ℑ',
        'J': '𝔍',
        'K': '𝔎',
        'L': '𝔏',
        'M': '𝔐',
        'N': '𝔑',
        'O': '𝔒',
        'P': '𝔓',
        'Q': '𝔔',
        'R': '𝔕',
        'S': '𝔖',
        'T': '𝔗',
        'U': '𝔘',
        'V': '𝔙',
        'W': '𝔚',
        'X': '𝔛',
        'Y': '𝔜',
        'Z': '𝔝'}

    def __init__(self):
        self.counters = {}

    def to_fancy(self, t):

        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat=None, score=None, speed=None, tcp=False, server=None, sni=None, mainland_pass=None):
        """【v28.58】命名包含区域emoji + 编号 + 延迟 + 评分 + 大陆可达标记 + 哥特体后缀"""
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        # 延迟信息（仅保留整数）
        lat_str = f"{int(lat)}ms" if lat is not None and lat < 9999 else "N/A"
        # 大陆友好评分（保留1位小数）
        score_str = f"s{score:.1f}" if score is not None else ""
        # v28.58: 大陆可达性标记
        ml_str = "✓" if mainland_pass else ""
        # 哥特体后缀
        gothic = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"
        return f"{code}{num}-{lat_str}{score_str}{ml_str}-{gothic}"


