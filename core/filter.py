# core/filter.py - filter_quality 核心过滤函数
# v28.42 Phase4 重构

import os
import re
import logging

from core.validator import is_china_mainland, is_asia, NON_PROXY_PORTS

# v30.5 FIX: 删除低价值地区硬筛 - 让测速决定可用性
# _LOW_VALUE_NON_ASIA_FLAGS = {'🇺🇦', '🇹🇷', '🇮🇷'}  # 已删除
from core.scorer import mainland_friendly_score, composite_score, PROTOCOL_SCORE
from network.tls import is_reality_friendly
from core.history import get_node_history_score as _get_node_history_score
from config import ASIA_REGIONS, ASIA_PRIORITY_BONUS, NON_FRIENDLY_REGIONS, NON_FRIENDLY_PENALTY
from network.geo import limiter
from utils import is_pure_ip

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
MAINLAND_PASS_BONUS = int(os.getenv("MAINLAND_PASS_BONUS", "20"))

# v30.5 FIX: 放宽 [WEB] 节点上限 - CDN 节点可能包含高质量亚洲节点
MAX_WEB_NET_NODES = int(os.getenv("MAX_WEB_NET_NODES", "50"))  # 15→50

# v30.0: [WEB] 节点计数器（每日重置，按自然日清零）
_web_node_count = 0
_web_node_reset_date = ""


def reset_filter_state():
    """重置过滤状态（由 main_flow 在每次运行开始时调用）"""
    global _web_node_count, _web_node_reset_date
    _web_node_count = 0
    _web_node_reset_date = ""


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

    # v30.5 FIX: 删除协议配置完整性硬筛 - 让测速决定可用性
    # 很多来源的节点缺少显式 tls 字段，但服务器实际支持 TLS
    # 协议参数不完整 ≠ 不可用，应进入测速阶段验证

    # v30.5 FIX: 放宽 [WEB] 节点上限 - 上限已从 15 提升到 50
    global _web_node_count, _web_node_reset_date
    from datetime import date
    today = str(date.today())
    if today != _web_node_reset_date:
        _web_node_count = 0
        _web_node_reset_date = today
    if name.startswith("[web]"):
        if _web_node_count >= MAX_WEB_NET_NODES:
            logging.debug("Filter: [WEB] node %s rejected, limit reached (%d)", p.get('name', '?'), MAX_WEB_NET_NODES)
            return False
        _web_node_count += 1

    # v30.5 FIX: 删除低价值地区硬筛 - 让测速决定可用性
    # CDN/中转节点可能通过低价值地区提供服务，不应提前过滤


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

def is_non_friendly_region(p):
    """判断节点是否属于低价值区域（UA/TR/IR等，通过名称中 emoji 旗帜识别）"""
    name = p.get("name", "")
    return any(fl in name for fl in _LOW_VALUE_NON_ASIA_FLAGS)


def final_sort_key(p):
    """v30.0: 排序键 = 亚洲优先 > 综合评分 > 源权重 > 延迟

    综合评分已包含地理+协议+TCP延迟+速度+历史+Reality的加权合成，
    无需再逐个字段排序。
    """
    asia = 3 if is_asia(p) else 0
    comp = composite_score(p)
    src_weight = p.get("_src_weight", 3)
    lat_from_name = 9999
    m = re.search(r"\d+", p.get("name", ""))
    if m:
        lat_from_name = int(m.group(0))
    return (-asia, -comp, -src_weight, lat_from_name)

