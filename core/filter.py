# core/filter.py - filter_quality 核心过滤函数
# v28.42 Phase4 重构

def filter_quality(p):
    """【v28.58】节点质量过滤，含 CN IP/域名黑名单 + 非代理端口过滤 + 大陆友好性评分"""
    if not p or not isinstance(p, dict):
        return False
    name = p.get("name", "").lower()

    # 仅排除明显无效的
    exclude_keywords = [
        "过期", "到期", "失效", "expire", "expired",
        "广告", "推广", "官网", "购买", "test", "测试",
        "体验", "试用", "trial", "临时", "temp",
        "公益", "免费", "free",  # 公益/免费节点通常不稳定
        "倍率", "倍", "x5", "x10", "x20",  # 高倍率节点
        "邀请", "邀请码", "invite",
        "订阅", "sub", "节点", "node",  # 纯描述性节点
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
    # SSR 协议特征明显，大陆环境下基本不可用
    if ptype == "ssr":
        return False
    # HTTP/SOCKS5 无加密，大陆环境下容易被识别
    if ptype in ("http", "socks5") and network == "tcp":
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
    if p.get("_mainland_pass") is False:
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
