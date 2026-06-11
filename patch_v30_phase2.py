#!/usr/bin/env python3
"""v30.0 Phase 2: 评分系统重构 + final_sort_key 优化"""
import re

# === 1. scorer.py: 统一评分函数 + TCP/速度/历史权重 ===
PATH_SCORER = 'core/scorer.py'

with open(PATH_SCORER, 'r', encoding='utf-8') as f:
    content = f.read()

# 1a: Remove legacy scoring, make new scoring the default
old_switch = '''# ===== 评分策略开关 =====
USE_NEW_SCORING = os.getenv("ZRONG_USE_NEW_SCORING", "0") == "1"'''
new_switch = '''# ===== 评分策略（v30.0: 统一使用新版评分）====='''
content = content.replace(old_switch, new_switch)

# 1b: Simplify mainland_friendly_score to always use new scoring
old_dispatch = '''def mainland_friendly_score(p):
    """评估节点对大陆用户的友好程度，返回 0-100 分数。

    通过环境变量 ZRONG_USE_NEW_SCORING 控制使用新版还是旧版评分逻辑。
    默认使用旧版（与原版行为完全一致）。
    """
    if USE_NEW_SCORING:
        return _main_land_friendly_score_new(p)
    return _main_land_friendly_score_legacy(p)'''
new_dispatch = '''def mainland_friendly_score(p):
    """评估节点对大陆用户的友好程度，返回 0-100 分数。v30.0: 统一使用新版评分。"""
    return _main_land_friendly_score_new(p)'''
content = content.replace(old_dispatch, new_dispatch)

# 1c: Add a composite scoring function that includes TCP/speed/history
composite_fn = '''

def composite_score(p: dict) -> float:
    """v30.0: 综合评分（0-100）= 评分权重: 地理+协议40% + TCP延迟25% + 速度15% + 历史10% + Reality/TLS 10%

    此函数在 final_sort_key 中使用，替代简单的 mainland_friendly_score。
    """
    mf = _main_land_friendly_score_new(p)  # 地理+协议+端口（0-100）

    # TCP延迟评分：从节点名称中提取延迟ms
    lat = 9999
    m = re.search(r"\\d+", p.get("name", ""))
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
'''
content += composite_fn

with open(PATH_SCORER, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: scorer.py updated")


# === 2. filter.py: 优化 final_sort_key 使用 composite_score ===
PATH_FILTER = 'core/filter.py'

with open(PATH_FILTER, 'r', encoding='utf-8') as f:
    content = f.read()

# Update import to include composite_score
old_import = 'from core.scorer import mainland_friendly_score, PROTOCOL_SCORE'
new_import = 'from core.scorer import mainland_friendly_score, composite_score, PROTOCOL_SCORE'
content = content.replace(old_import, new_import)

# Replace final_sort_key
old_sort = '''def final_sort_key(p):
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
    m = re.search(r"\\d+", p.get("name", ""))
    if m:
        lat_from_name = int(m.group(0))
    return (-asia, -mf_score, -speed, -src_weight, -reality, -proto_score, -hist_score, lat_from_name)'''

new_sort = '''def final_sort_key(p):
    """v30.0: 排序键 = 亚洲优先 > 综合评分 > 源权重 > 延迟

    综合评分已包含地理+协议+TCP延迟+速度+历史+Reality的加权合成，
    无需再逐个字段排序。
    """
    asia = 3 if is_asia(p) else 0
    comp = composite_score(p)
    src_weight = p.get("_src_weight", 3)
    lat_from_name = 9999
    m = re.search(r"\\d+", p.get("name", ""))
    if m:
        lat_from_name = int(m.group(0))
    return (-asia, -comp, -src_weight, lat_from_name)'''

content = content.replace(old_sort, new_sort)

with open(PATH_FILTER, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: filter.py updated")


# === 3. rules.yaml: 调整评分权重 ===
PATH_RULES = 'config/rules.yaml'

with open(PATH_RULES, 'r', encoding='utf-8') as f:
    content = f.read()

# Adjust scoring_new weights for v30.0
# Lower geography weights slightly (since TCP/speed now have their own weights in composite)
content = content.replace(
    '  asia_tier1: 65  # 港台日新',
    '  asia_tier1: 60  # 港台日新 (v30.0: 略降，因TCP/速度独立权重)'
)
content = content.replace(
    '  asia_tier2: 48  # 韩泰越菲马印尼',
    '  asia_tier2: 45  # 韩泰越菲马印尼'
)
content = content.replace(
    '  asia_tier3: 38  # 其他亚洲',
    '  asia_tier3: 35  # 其他亚洲'
)

with open(PATH_RULES, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: rules.yaml updated")
