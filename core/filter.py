# core/filter.py - filter_quality 核心过滤函数
# v28.42 Phase4 重构

import os
import re
import logging

from core.validator import is_china_mainland, is_asia, NON_PROXY_PORTS
from core.scorer import mainland_friendly_score, PROTOCOL_SCORE
from network.tls import is_reality_friendly
from core.history import get_node_history_score as _get_node_history_score
from config import ASIA_REGIONS, ASIA_PRIORITY_BONUS, NON_FRIENDLY_REGIONS, NON_FRIENDLY_PENALTY
from network.geo import limiter
from utils import is_pure_ip

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
MAINLAND_PASS_BONUS = int(os.getenv("MAINLAND_PASS_BONUS", "20"))

# v29.1: 限制无法识别地区的 CDN 伪装节点数量
MAX_WEB_NET_NODES = int(os.getenv("MAX_WEB_NET_NODES", "15"))


def filter_quality(p):
    """【v28.58】节点质量过滤，含 CN IP/域名黑名单 + 非代理端口过滤 + 大陆友好性评分"""
    if not p or not isinstance(p, dict):
        return False
    name = p.get("name", "").lower()

    # v29.01: 收窄排除关键词——"免费/公益/临时"可能含有效亚洲节点
    exclude_keywords = [
        "过期", "到期", "失效", "expire", "expired",
        "广告", "推广", "官网", "购买",
        "倍率", "x5", "x10", "x20", "x50",  # 高倍率节点
        "邀请码", "invite-only",
    ]
    for kw in exclude_keywords:
        if kw in name:
            return False

    # 排除内地直连
    if is_china_mainland(p):
        return False

    # 排除已知不可用的协议组合
    ptype = p.get("type", "").lower()
    network = p.get("network", "tcp").lower()
    # SSR/HTTP/SOCKS5 无加密，大陆环境下基本不可用
    if ptype == "ssr":
        return False
    if ptype in ("http", "socks5") and network == "tcp":
        return False
    # v29.01: anytls 协议 Clash 不支持，过滤
    if ptype == "anytls":
        return False

    # 非代理端口过滤（v24）
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    if port <= 0 or port > 65535:
        return False
    if port in NON_PROXY_PORTS:
        return False

    # v28.63: 大陆可达性评分（大陆不可达仅扣分，不硬筛）
    if p.get("mainland_reachable") is False:
        logging.debug("Score: mainland-unreachable node %s, -30 score", p.get('name', '?'))
        # 不直接过滤，交给评分函数处理

    # v28.39: 大陆友好性评分过滤 - 过滤掉极低友好度的节点
    try:
        mf_score = mainland_friendly_score(p)
        if mf_score < 10:  # 友好度低于10分的节点大概率不可用
            logging.debug("Filter: skip low mainland-friendly node %s (score=%s)", p.get('name', '?'), mf_score)
            return False
    except (ValueError, KeyError, TypeError):
        logging.debug("mainland_friendly_score error for %s", p.get('name', '?'), exc_info=True)
        # 评分失败时不过滤，避免误杀

    return True

def _geo_score(item):
    """IP 地理位置评分：亚洲高分，非友好区域低分"""
    srv = item["proxy"].get("server", "")
    # BUGFIX v28.20: IPv6 安全提取 host
    if srv.startswith("[") and "]" in srv:
        host = srv.split("]")[0][1:]
    elif is_pure_ip(srv) and ":" in srv:
        host = srv  # 纯 IPv6（如 fe80::1）整体就是 host
    elif ":" in srv:
        host = srv.split(":")[0]
    else:
        host = srv
    score = 0
    geo = limiter.get_geo(host)  # v28.22: 统一使用 limiter.get_geo()
    if geo:
        score += 2  # 有地理位置信息，更可靠
        cc = geo.get("countryCode", "").upper()
        # v28.8: 亚洲友好区域高额加分
        if cc in ASIA_REGIONS:
            score += ASIA_PRIORITY_BONUS
        # v28.8: 非友好区域扣分
        elif cc in NON_FRIENDLY_REGIONS:
            score -= NON_FRIENDLY_PENALTY
    # 大陆友好加分：名称含大陆/CN/内地关键词
    name_lower = item.get("proxy", {}).get("name", "").lower()
    cn_friendly_kw = ["cn", "china", "国内", "大陆", "直连", "beijing", "shanghai", "guangzhou", "shenzhen"]
    if any(kw in name_lower for kw in cn_friendly_kw):
        score += 30
    return score

def final_sort_key(p):
    """v28.90: 排序键 = 亚洲 > 大陆友好分 > 速度 > 源权重 > Reality > 协议 > 历史 > 延迟"""
    asia = 3 if is_asia(p) else 0
    reality = 1 if is_reality_friendly(p) else 0
    proto_score = PROTOCOL_SCORE.get(p.get("type", ""), 0) / 10.0
    mf_score = mainland_friendly_score(p)
    if asia > 0:
        mf_score += 15
    # 大陆测试加分（仅开启时）
    if ENABLE_MAINLAND_TEST:
        ml = p.get("mainland_reachable")
        if ml is True:
            mf_score += MAINLAND_PASS_BONUS
        elif ml is False:
            mf_score -= 30
    src_weight = p.get("_src_weight", 3)
    speed = p.get("_speed", 0.0)
    hist_score = _get_node_history_score(p)
    lat_from_name = 0
    m = re.search(r"\d+", p.get("name", ""))
    if m:
        lat_from_name = int(m.group(0))
    return (-asia, -mf_score, -speed, -src_weight, -reality, -proto_score, -hist_score, lat_from_name)

