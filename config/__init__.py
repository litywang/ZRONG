# config/__init__.py - 规则配置加载

import os
import logging
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

logger = logging.getLogger(__name__)

# 默认规则文件路径
_DEFAULT_RULES_PATH = Path(__file__).parent / "rules.yaml"

# 内存缓存
_cached_rules = None
_cache_mtime = 0


def load_rules(path=None):
    """加载 rules.yaml，返回 dict；读取失败返回默认规则字典"""
    global _cached_rules, _cache_mtime

    if path is None:
        path = _DEFAULT_RULES_PATH
    else:
        path = Path(path)

    # 使用文件 mtime 做简单缓存
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        logger.warning("rules.yaml 未找到: %s，使用内置默认规则", path)
        return _default_rules()

    if _cached_rules is not None and mtime == _cache_mtime:
        return _cached_rules

    if not _HAS_YAML:
        logger.error("PyYAML 未安装，无法加载 rules.yaml，使用内置默认规则")
        logger.error("请运行: pip install pyyaml")
        return _default_rules()

    with open(path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    if not isinstance(rules, dict):
        logger.error("rules.yaml 格式错误，应为 dict，使用内置默认规则")
        return _default_rules()

    # 合并默认值（防止 yaml 缺少某些 key）
    defaults = _default_rules()
    for key in defaults:
        if key not in rules:
            rules[key] = defaults[key]

    _cached_rules = rules
    _cache_mtime = mtime
    logger.info("已加载规则配置: %s", path)
    return rules


def _default_rules():
    """内置默认规则（与硬编码值一致，防止 yaml 缺失）"""
    return {
        "regions": {
            "asia": [
                "HK", "TW", "JP", "SG", "KR", "TH", "VN", "MY", "ID", "PH",
                "MO", "MN", "KH", "LA", "MM", "BN", "TL", "NP", "LK", "BD",
                "BT", "MV",
            ],
            "non_friendly": [
                "IR", "IN", "RU", "NG", "ZA", "BR", "AR", "CL", "PE", "VE",
                "EC", "CO", "MX",
                "US", "CA", "AU", "EU", "GB", "DE", "FR", "NL", "IT", "ES",
                "SE", "NO", "FI", "DK", "PL", "CZ", "HU", "RO", "BG", "GR",
                "PT", "AT", "CH", "BE", "IE",
            ],
            "premium": [
                "hk", "hongkong", "港", "🇭🇰",
                "tw", "taiwan", "台", "🇹🇼",
                "jp", "japan", "日", "tokyo", "osaka", "🇯🇵",
                "sg", "singapore", "新加坡", "狮城", "🇸🇬",
                "kr", "korea", "韩", "seoul", "🇰🇷",
            ],
        },
        "scoring_legacy": {
            "geo_bonus": {"asia": 50, "premium_region": 20, "us": 10, "ca_au": 5},
            "proto_bonus": {
                "vless": 20, "trojan": 15, "vmess": 10,
                "hysteria2": 18, "hysteria": 12, "ss": 5, "ssr": 3,
            },
            "reality_bonus": 10,
            "reality_extra_bonus": 5,
            "network_bonus": {"ws": 5, "grpc": 3, "h2": 0, "quic": 0},
            "port_bonus": {
                "high": [443, 8443], "high_value": 5,
                "medium": [80, 8080], "medium_value": 2,
            },
        },
        "scoring_new": {
            "asia_tier1": 60,
            "asia_tier2": 45,
            "asia_tier3": 35,
            "geo_confirm_bonus": 15,
            "us_west": 20,
            "us_other": 5,
            "jp_kr_ip": 10,
            "proto_bonus": {
                "vless": 25, "trojan": 20, "hysteria2": 18,
                "vmess": 10, "anytls": 12, "hysteria": 8,
                "tuic": 8, "ss": 3, "ssr": 1, "http": 2, "socks5": 2,
            },
            "reality_bonus": 20,
            "reality_vless_bonus": 10,
            "tls_bonus": 8,
            "network_bonus": {"ws": 8, "grpc": 6, "h2": 4, "quic": 3},
            "port_bonus": {
                "very_high": [443], "very_high_value": 8,
                "high": [8443, 2053, 2083, 2087, 2096], "high_value": 6,
                "medium": [80, 8080, 8880, 2052, 2082, 2086, 2095], "medium_value": 4,
                "low_range": [1, 1023], "low_value": 2,
                "exclude_ports": [22, 25, 53, 110, 143, 993, 995],
            },
        },
        "requests": {
            "per_second": 6.0,
            "max_retries": 2,
        },
        "asia_priority_bonus": 40,
        "non_friendly_penalty": 40,
    }


def get_region_list():
    """返回 ASIA_REGIONS 列表"""
    rules = load_rules()
    return rules.get("regions", {}).get("asia", [])


def get_non_friendly_regions():
    """返回 NON_FRIENDLY_REGIONS 列表"""
    rules = load_rules()
    return rules.get("regions", {}).get("non_friendly", [])


def get_premium_keywords():
    """返回 premium_regions 关键词列表"""
    rules = load_rules()
    return rules.get("regions", {}).get("premium", [])


def get_scoring_weights(use_new=False):
    """返回评分权重 dict（legacy 或 new）"""
    rules = load_rules()
    if use_new:
        return rules.get("scoring_new", {})
    return rules.get("scoring_legacy", {})


def get_requests_config():
    """返回请求配置 dict"""
    rules = load_rules()
    return rules.get("requests", {})


def get_asia_priority_bonus():
    """返回 ASIA_PRIORITY_BONUS 值"""
    rules = load_rules()
    return rules.get("asia_priority_bonus", 40)


def get_non_friendly_penalty():
    """返回 NON_FRIENDLY_PENALTY 值"""
    rules = load_rules()
    return rules.get("non_friendly_penalty", 40)


# 便捷：直接暴露常用配置的 property
_rules = load_rules()
ASIA_REGIONS = _rules["regions"]["asia"]
NON_FRIENDLY_REGIONS = _rules["regions"]["non_friendly"]
ASIA_PRIORITY_BONUS = _rules.get("asia_priority_bonus", 40)
NON_FRIENDLY_PENALTY = _rules.get("non_friendly_penalty", 40)
REQUESTS_PER_SECOND = _rules.get("requests", {}).get("per_second", 6.0)
MAX_RETRIES = _rules.get("requests", {}).get("max_retries", 2)
