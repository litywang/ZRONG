"""
core/scorer.py - 节点评分模块

从 utils.py 迁移评分相关函数，负责：
- 大陆友好评分（legacy / new 两版）
- 协议优先级评分
- 端口质量评分
- 区域判断辅助（is_asia / is_china_mainland / get_region 保留在 utils.py，评分时导入）

使用：
    from core.scorer import mainland_friendly_score, PROTOCOL_SCORE
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ===== 评分策略开关 =====
# 环境变量 ZRONG_USE_NEW_SCORING=1 启用新版大陆友好评分
# 默认关闭，行为与原版完全一致
USE_NEW_SCORING = os.getenv("ZRONG_USE_NEW_SCORING", "0") == "1"

# ===== 协议优先级评分 =====
PROTOCOL_SCORE = {
    "vless": 15, "trojan": 12, "vmess": 8, "hysteria2": 12, "anytls": 5,
    "hysteria": 6, "tuic": 8, "snell": 2, "ss": 4, "ssr": 1, "http": 2, "socks5": 2,
}

# ===== 端口质量评分 =====
HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}


def _cc_to_flag(cc):
    """国家代码转 emoji flag，如 'US' → '🇺🇸'"""
    try:
        return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in cc.upper()[:2])
    except (ValueError, TypeError):
        logger.debug("Exception occurred", exc_info=True)
        return "[WEB]"


def _get_limiter():
    """延迟导入 limiter，避免循环依赖"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.limiter


def _mainland_friendly_score_legacy(p):
    """v28.23 原始评分逻辑（保留用于对比和回退）

    评估节点对大陆用户的友好程度，返回 0-100 分数。
    综合考虑：地理位置、协议特性、传输层类型、端口特征。
    高分 = 更可能对大陆用户稳定可用。
    """
    if not p or not isinstance(p, dict):
        return 0
    score = 0

    # 1. 地理位置加成（权重最大）
    from core.validator import is_asia
    if is_asia(p):
        score += 50
        t = f"{p.get('name', '')} {p.get('server', '')}".lower()
        premium_regions = [
            "hk", "hongkong", "港", "🇭🇰",
            "tw", "taiwan", "台", "🇹🇼",
            "jp", "japan", "日", "tokyo", "osaka", "🇯🇵",
            "sg", "singapore", "新加坡", "狮城", "🇸🇬",
            "kr", "korea", "韩", "seoul", "🇰🇷",
        ]
        if any(k in t for k in premium_regions):
            score += 20
    else:
        server = p.get("server", "")
        try:
            limiter = _get_limiter()
            geo = limiter.get_geo(server) if server else None
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc == "US":
                    score += 10
                elif cc in ("CA", "AU"):
                    score += 5
        except (ImportError, AttributeError):
            logger.debug("Limiter not ready, skipping geo lookup")

    # 2. 协议加成（抗检测能力）
    ptype = p.get("type", "")
    proto_bonus = {
        "vless": 20, "trojan": 15, "vmess": 10,
        "hysteria2": 18, "hysteria": 12,
        "ss": 5, "ssr": 3,
    }
    score += proto_bonus.get(ptype, 0)

    # 3. Reality 加成（最强抗封锁）
    if p.get("reality-opts") or p.get("tls"):
        score += 10
        if p.get("reality-opts"):
            score += 5

    # 4. 传输层加成
    network = p.get("network", "tcp")
    if network == "ws":
        score += 5
    elif network == "grpc":
        score += 3

    # 5. 端口加成
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    if port in (443, 8443):
        score += 5
    elif port in (80, 8080):
        score += 2

    return min(score, 100)


def _mainland_friendly_score_new(p):
    """v28.50 优化版大陆友好评分（ZRONG_USE_NEW_SCORING=1 时生效）

    在 legacy 基础上：
    - 亚洲节点分层更细（一级港日韩新60分 / 二级东南亚45分 / 三级其他亚洲35分）
    - IP 地理位置确认的优质线路额外+15分
    - 协议权重调整（vless+25, trojan+20, hysteria2+18, anytls+12）
    - Reality+VLESS 组合额外+10分
    - 传输层权重调整（ws+8, grpc+6, h2+4）
    - 端口评分更精细化
    - 非亚洲节点仅保留美西等极少数友好地区
    """
    if not p or not isinstance(p, dict):
        return 0
    score = 0

    from core.validator import is_asia

    if is_asia(p):
        t = f"{p.get('name', '')} {p.get('server', '')}".lower()
        has_hk = "hk" in t or "hongkong" in t or "港" in t or "🇭🇰" in t
        has_tw = "tw" in t or "taiwan" in t or "台" in t or "🇹🇼" in t
        has_jp = "jp" in t or "japan" in t or "日" in t or "🇯🇵" in t
        has_sg = "sg" in t or "singapore" in t or "新加坡" in t or "🇸🇬" in t
        has_kr = "kr" in t or "korea" in t or "韩" in t or "🇰🇷" in t
        has_th = "th" in t or "thailand" in t or "泰" in t or "🇹🇭" in t
        has_vn = "vn" in t or "vietnam" in t or "越" in t or "🇻🇳" in t
        has_ph = "ph" in t or "philippines" in t or "菲" in t or "🇵🇭" in t
        has_my = "my" in t or "malaysia" in t or "马" in t or "🇲🇾" in t
        has_id = "id" in t or "indonesia" in t or "印尼" in t or "🇮🇩" in t

        if has_hk or has_tw or has_jp or has_sg:
            score += 60
        elif has_kr or has_th or has_vn or has_ph or has_my or has_id:
            score += 45
        else:
            score += 35

        server = p.get("server", "")
        if server and p.get("server", "").count(".") >= 3 or False:
            pass
        if server and _is_pure_ip(server):
            try:
                limiter = _get_limiter()
                geo = limiter.get_geo(server)
                if geo:
                    cc = geo.get("countryCode", "").upper()
                    if cc in ("HK", "TW", "JP", "SG"):
                        score += 15
            except (ImportError, AttributeError):
                logger.debug("Limiter not ready, skipping geo lookup")
    else:
        server = p.get("server", "")
        try:
            limiter = _get_limiter()
            geo = limiter.get_geo(server) if server else None
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc == "US":
                    t = f"{p.get('name', '')} {server}".lower()
                    if any(k in t for k in [
                        "la", "san francisco", "seattle", "portland",
                        "los angeles", "san jose", "西海岸",
                    ]):
                        score += 20
                    else:
                        score += 5
                elif cc in ("JP", "KR"):
                    score += 10
        except (ImportError, AttributeError):
            logger.debug("Limiter not ready, skipping geo lookup")

    # 2. 协议加成
    ptype = p.get("type", "")
    proto_bonus = {
        "vless": 25, "trojan": 20, "hysteria2": 18,
        "vmess": 10, "anytls": 12, "hysteria": 8,
        "tuic": 8, "ss": 3, "ssr": 1, "http": 2, "socks5": 2,
    }
    score += proto_bonus.get(ptype, 0)

    # 3. Reality 加成
    if p.get("reality-opts"):
        score += 20
        if p.get("type") == "vless":
            score += 10
    elif p.get("tls"):
        score += 8

    # 4. 传输层加成
    network = p.get("network", "tcp")
    if network == "ws":
        score += 8
    elif network == "grpc":
        score += 6
    elif network == "h2":
        score += 4
    elif network == "quic":
        score += 3

    # 5. 端口加成
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    if port == 443:
        score += 8
    elif port in (8443, 2053, 2083, 2087, 2096):
        score += 6
    elif port in (80, 8080, 8880, 2052, 2082, 2086, 2095):
        score += 4
    elif port < 1024 and port not in (22, 25, 53, 110, 143, 993, 995):
        score += 2

    return min(score, 100)


def mainland_friendly_score(p):
    """评估节点对大陆用户的友好程度，返回 0-100 分数。

    通过环境变量 ZRONG_USE_NEW_SCORING 控制使用新版还是旧版评分逻辑。
    默认使用旧版（与原版行为完全一致）。
    """
    if USE_NEW_SCORING:
        return _mainland_friendly_score_new(p)
    return _mainland_friendly_score_legacy(p)


def _is_pure_ip(host: str) -> bool:
    """判断是否为纯 IP（不含域名）— 避免从 utils 循环导入"""
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except (ValueError, TypeError):
        return False
