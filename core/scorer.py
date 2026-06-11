"""
core/scorer.py - 节点评分模块

从 utils.py 迁移评分相关函数，负责：
- 大陆友好评分（legacy / new 两版，权重从 config/rules.yaml 读取）
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

# ===== 评分策略（v30.0: 统一使用新版评分）=====

# ===== 从 config/rules.yaml 读取评分规则 =====
from config import load_rules, get_scoring_weights
from core.validator import is_asia

_rules = load_rules()
_scoring_legacy = get_scoring_weights(use_new=False)
_scoring_new = get_scoring_weights(use_new=True)

# ===== 协议优先级评分（保留此处，也可外置到 rules.yaml）=====
PROTOCOL_SCORE = {
    "vless": 15, "trojan": 12, "vmess": 8, "hysteria2": 12, "anytls": 5,
    "hysteria": 6, "tuic": 8, "snell": 2, "ss": 4, "ssr": 1, "http": 2, "socks5": 2,
}

# ===== 端口质量评分 =====
HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}


def _cc_to_flag(cc):
    """国家代码转 emoji flag"""
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


def _is_pure_ip(host: str) -> bool:
    """判断是否为纯 IP（不含域名）— 避免从 utils 循环导入"""
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except (ValueError, TypeError):
        return False


def _main_land_friendly_score_legacy(p):
    """v28.23 原始评分逻辑（保留用于对比和回退）

    评估节点对大陆用户的友好程度，返回 0-100 分数。
    综合考虑：地理位置、协议特性、传输层类型、端口特征。
    高分 = 更可能对大陆用户稳定可用。

    权重从 config/rules.yaml → scoring_legacy 读取。
    """
    if not p or not isinstance(p, dict):
        return 0
    score = 0
    rules = _scoring_legacy

    # 1. 地理位置加成（权重最大）
    if is_asia(p):
        score += rules["geo_bonus"]["asia"]
        t = f"{p.get('name', '')} {p.get('server', '')}".lower()
        premium_keywords = _rules["regions"].get("premium", [])
        if any(k in t for k in premium_keywords):
            score += rules["geo_bonus"]["premium_region"]
    else:
        server = p.get("server", "")
        try:
            limiter = _get_limiter()
            geo = limiter.get_geo(server) if server else None
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc == "US":
                    score += rules["geo_bonus"]["us"]
                elif cc in ("CA", "AU"):
                    score += rules["geo_bonus"]["ca_au"]
        except (ImportError, AttributeError):
            logger.debug("Limiter not ready, skipping geo lookup")

    # 2. 协议加成（抗检测能力）
    ptype = p.get("type", "")
    score += rules["proto_bonus"].get(ptype, 0)

    # 3. Reality 加成（最强抗封锁）
    if p.get("reality-opts") or p.get("tls"):
        score += rules["reality_bonus"]
        if p.get("reality-opts"):
            score += rules["reality_extra_bonus"]

    # 4. 传输层加成
    network = p.get("network", "tcp")
    score += rules["network_bonus"].get(network, 0)

    # 5. 端口加成
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    port_b = rules["port_bonus"]
    if port in tuple(port_b["high"]):
        score += port_b["high_value"]
    elif port in tuple(port_b["medium"]):
        score += port_b["medium_value"]

    return min(score, 100)


def _main_land_friendly_score_new(p):
    """v28.50 优化版大陆友好评分（ZRONG_USE_NEW_SCORING=1 时生效）

    在 legacy 基础上：
    - 亚洲节点分层更细（一级港日韩新 / 二级东南亚 / 三级其他亚洲）
    - IP 地理位置确认的优质线路额外加分
    - 协议/Reality/传输层/端口权重均从 config/rules.yaml 读取
    - 非亚洲节点仅保留美西等极少数友好地区

    权重从 config/rules.yaml → scoring_new 读取。
    """
    if not p or not isinstance(p, dict):
        return 0
    score = 0
    rules = _scoring_new

    # is_asia 已在文件开头导入

    if is_asia(p):
        t = f"{p.get('name', '')} {p.get('server', '')}".lower()
        has_hk = any(k in t for k in ["hk", "hongkong", "港", "🇭🇰"])
        has_tw = any(k in t for k in ["tw", "taiwan", "台", "🇹🇼"])
        has_jp = any(k in t for k in ["jp", "japan", "日", "tokyo", "osaka", "🇯🇵"])
        has_sg = any(k in t for k in ["sg", "singapore", "新加坡", "狮城", "🇸🇬"])
        has_kr = any(k in t for k in ["kr", "korea", "韩", "seoul", "🇰🇷"])
        has_th = any(k in t for k in ["th", "thailand", "泰", "🇹🇭"])
        has_vn = any(k in t for k in ["vn", "vietnam", "越", "🇻🇳"])
        has_ph = any(k in t for k in ["ph", "philippines", "菲", "🇵🇭"])
        has_my = any(k in t for k in ["my", "malaysia", "马", "🇲🇾"])
        has_id = any(k in t for k in ["id", "indonesia", "印尼", "🇮🇩"])

        if has_hk or has_tw or has_jp or has_sg:
            score += rules["asia_tier1"]
        elif has_kr or has_th or has_vn or has_ph or has_my or has_id:
            score += rules["asia_tier2"]
        else:
            score += rules["asia_tier3"]

        server = p.get("server", "")
        if server and _is_pure_ip(server):
            try:
                limiter = _get_limiter()
                geo = limiter.get_geo(server)
                if geo:
                    cc = geo.get("countryCode", "").upper()
                    if cc in ("HK", "TW", "JP", "SG"):
                        score += rules["geo_confirm_bonus"]
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
                    us_west_keywords = [
                        "la", "san francisco", "seattle", "portland",
                        "los angeles", "san jose", "西海岸",
                    ]
                    if any(k in t for k in us_west_keywords):
                        score += rules["us_west"]
                    else:
                        score += rules["us_other"]
                elif cc in ("JP", "KR"):
                    score += rules["jp_kr_ip"]
        except (ImportError, AttributeError):
            logger.debug("Limiter not ready, skipping geo lookup")

    # 2. 协议加成
    ptype = p.get("type", "")
    score += rules["proto_bonus"].get(ptype, 0)

    # 3. Reality 加成
    if p.get("reality-opts"):
        score += rules["reality_bonus"]
        if p.get("type") == "vless":
            score += rules["reality_vless_bonus"]
    elif p.get("tls"):
        score += rules["tls_bonus"]

    # 4. 传输层加成
    network = p.get("network", "tcp")
    score += rules["network_bonus"].get(network, 0)

    # 5. 端口加成
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    port_b = rules["port_bonus"]
    if port in tuple(port_b["very_high"]):
        score += port_b["very_high_value"]
    elif port in tuple(port_b["high"]):
        score += port_b["high_value"]
    elif port in tuple(port_b["medium"]):
        score += port_b["medium_value"]
    elif port_b["low_range"][0] <= port <= port_b["low_range"][1] and port not in tuple(port_b["exclude_ports"]):
        score += port_b["low_value"]

    return min(score, 100)


def mainland_friendly_score(p):
    """评估节点对大陆用户的友好程度，返回 0-100 分数。v30.0: 统一使用新版评分。"""
    return _main_land_friendly_score_new(p)


def composite_score(p: dict) -> float:
    """v30.0: 综合评分（0-100）= 评分权重: 地理+协议40% + TCP延迟25% + 速度15% + 历史10% + Reality/TLS 10%

    此函数在 final_sort_key 中使用，替代简单的 mainland_friendly_score。
    """
    mf = _main_land_friendly_score_new(p)  # 地理+协议+端口（0-100）

    # TCP延迟评分：从节点名称中提取延迟ms
    lat = 9999
    m = re.search(r"\d+", p.get("name", ""))
    if m:
        lat = int(m.group(0))
    if lat <= 100:
        lat_score = 100
    elif lat <= 200:
        lat_score = 80
    elif lat <= 400:
        lat_score = 60
    elif lat <= 800:
        lat_score = 35
    elif lat <= 1500:
        lat_score = 15
    else:
        lat_score = 0

    # 速度评分
    speed = p.get("_speed", 0.0)
    if speed <= 0:
        speed_score = 0
    elif speed < 10:
        speed_score = 20
    elif speed < 50:
        speed_score = 50
    elif speed < 200:
        speed_score = 80
    else:
        speed_score = 100

    # 历史稳定性评分
    try:
        from core.history import get_node_history_score as _ghs
        hist = _ghs(p)
    except (ImportError, AttributeError):
        hist = 0
    hist_score = min(hist * 20, 100)  # 归一化到0-100

    # Reality/TLS 加分
    reality = 100 if p.get("reality-opts") else (50 if p.get("tls") else 0)

    # 加权合成
    composite = (
        mf * 0.40 +      # 地理+协议+端口
        lat_score * 0.25 + # TCP延迟
        speed_score * 0.15 + # 速度
        hist_score * 0.10 +  # 历史
        reality * 0.10       # Reality/TLS
    )
    return round(min(composite, 100), 2)
