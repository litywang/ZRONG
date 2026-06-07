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
    # v28.68: 仅在大陆出口IP检测开启时才使用 mainland_pass 评分
    #         默认关闭，mainland_pass=False 不扣分（避免将未测节点全部压在底部）
    if ENABLE_MAINLAND_TEST:
        ml_bonus = MAINLAND_PASS_BONUS if p.get("_mainland_pass", False) else (-30 if p.get("_mainland_pass") is False else 0)
    else:
        ml_bonus = 0
    # v28.23: 排序整合大陆友好性评分 + 源权重
    asia = 3 if is_asia(p) else 0  # v28.14: 提高亚洲权重（2→3）
    reality = 1 if is_reality_friendly(p) else 0
    proto_score = PROTOCOL_SCORE.get(p.get("type", ""), 0) / 10.0  # normalize
    # v28.23: 大陆友好性综合评分（替代纯 region_bonus）
    mf_score = mainland_friendly_score(p)
    # v28.49: 亚洲节点额外加分（提高亚洲排序优先级）
    if asia > 0:
        mf_score += 15
    # v28.58: 合并大陆测试加分 + 静态评分（静态评分占100%权重，测试通过额外加分）
    mf_score = mf_score + ml_bonus
    # v28.54: 使用动态源权重（1-20分），替代静态权重
    src_weight = p.get("_src_weight", 3)
    # 兼容旧 region_bonus 逻辑（IP geo 额外惩罚不友好地区）
    region_bonus = 0
    srv = p.get("server", "")
    # BUGFIX v28.20: IPv6 安全提取 host
    if srv.startswith("[") and "]" in srv:
        host = srv.split("]")[0][1:]
    elif is_pure_ip(srv) and ":" in srv:
        host = srv  # 纯 IPv6（如 fe80::1）整体就是 host
    elif ":" in srv:
        host = srv.split(":")[0]
    else:
        host = srv
    geo = limiter.get_geo(host)
    if geo:
        cc = geo.get("countryCode", "").upper()
        if cc in NON_FRIENDLY_REGIONS:
            region_bonus = -NON_FRIENDLY_PENALTY
    # v28.14: extract latency from name for secondary sort
    lat_from_name = 0
    m = re.search(r"\d+", p.get("name", ""))
    if m:
        lat_from_name = int(m.group(0))
    # v28.53: 融合历史可用性评分（0-20分）
    hist_score = _get_node_history_score(p)
    # sort: asia > mainland_friendly > src_weight > reality > proto > region_penalty > hist > latency
    return (-asia, -mf_score, -src_weight, -reality, -proto_score, -region_bonus, -hist_score, lat_from_name)
