# sources/utils.py - 公共工具函数
# v28.53: 从 telegram.py / subscription.py 提取公共函数，消除重复

import re
import base64
import hashlib
import logging
from typing import List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ===== URL 工具函数 =====

def clean_url(url: str) -> str:
    """URL 规范化（通用版，适用于 Telegram 和 Subscription 源）

    移除不可见字符、统一协议、去除尾部标点、检查长度和域名有效性。
    """
    if not url:
        return ""
    cleaned = re.sub(r'\s+', '', url)
    # 对 github 域名统一为 https
    if 'github' in cleaned.lower():
        cleaned = cleaned.replace("http://", "https://", 1)
    cleaned = cleaned.rstrip('.,;:!?"\\')
    if len(cleaned) < 15:
        return ""
    domain = urlparse(cleaned).netloc
    if not domain or len(domain) < 4:
        return ""
    return cleaned


def is_valid_url(url: str) -> bool:
    """URL 有效性检查（通用版）"""
    if not url or len(url) < 10:
        return False
    url = url.strip().rstrip('.,;:')
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    invalid_domains = ["t.me", "telegram.org"]
    if any(domain in url for domain in invalid_domains):
        return False
    return True


def check_subscription_quality(url: str) -> bool:
    """订阅质量快速筛查（通用版）"""
    quality_indicators = [
        "token=", "/subscribe/", "/api/v1/client/",
        ".txt", ".yaml", ".yml", ".json", "/link/"
    ]
    url_lower = url.lower()
    match_count = sum(1 for indicator in quality_indicators if indicator in url_lower)
    return match_count >= 1


def strip_url(u: str) -> str:
    """确保 URL 无空格"""
    if u:
        return u.strip().replace("\n", "").replace(" ", "")
    return ""


def check_url_fast(u: str) -> bool:
    """跳过 HEAD 验证，直接返回 True（零验证直拉策略）"""
    return True


def check_url(u: str) -> bool:
    """跳过 HEAD 验证（零验证直拉策略，统一入口）"""
    return True


# ===== 编码/解码工具 =====

def is_base64(s: str) -> bool:
    """判断是否为 base64 编码"""
    try:
        s = s.strip()
        if len(s) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
        return True
    except (ValueError, base64.binascii.Error):
        logging.debug("is_base64 failed", exc_info=True)
        return False


def decode_b64(c: str) -> str:
    """Base64 解码"""
    try:
        c = c.strip()
        m = len(c) % 4
        if m:
            c += "=" * (4 - m)
        d = base64.b64decode(c).decode("utf-8", errors="ignore")
        return d if "://" in d else c
    except (ValueError, base64.binascii.Error):
        logging.debug("decode_b64 failed", exc_info=True)
        return c


# ===== YAML 解析 =====

def is_yaml_content(content: str) -> bool:
    """判断内容是否为 YAML 订阅源"""
    c_lower = content[:2000].lower()
    return ("proxies:" in c_lower or "proxy:" in c_lower) and ("server:" in c_lower)


def parse_yaml_proxies(content: str) -> List[dict]:
    """解析 YAML 格式的 Clash/Mihomo 订阅，提取 proxies 列表"""
    import yaml
    try:
        data = yaml.safe_load(content)
        if not data or not isinstance(data, dict):
            return []
        proxies = data.get("proxies") or data.get("Proxy") or []
        if not isinstance(proxies, list):
            return []
        results = []
        for p in proxies:
            if not isinstance(p, dict) or not p.get("server"):
                continue
            ptype = (p.get("type") or "").lower()
            if ptype not in ("vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2", "tuic",
                             "wireguard", "shadowtls", "snell", "http", "socks5", "anytls"):
                continue
            try:
                port = int(p.get("port", 0))
                if port <= 0:
                    continue
            except (ValueError, TypeError):
                continue
            original_name = p.get("name", "")
            if not original_name:
                key = f"{p['server']}:{port}:{p.get('uuid', p.get('password', ''))}"
                h = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8].upper()
                ptype_tag = {"vmess": "VM", "vless": "VL", "trojan": "TJ", "ss": "SS", "ssr": "SR",
                             "hysteria": "HY", "hysteria2": "H2", "tuic": "TU", "wireguard": "WG", "shadowtls": "ST"}
                original_name = f"{ptype_tag.get(ptype, 'XX')}-{h}"
            p["name"] = original_name
            results.append(p)
        return results
    except (yaml.YAMLError, TypeError, AttributeError):
        logging.debug("parse_yaml_proxies failed", exc_info=True)
        return []


# ===== 源权重 =====

def source_weight(url: str) -> int:
    """根据URL特征推断源权重（1-10），国内友好源得分更高

    这是静态权重版本，用于无法访问动态权重函数时的降级。
    """
    u = url.lower()
    domestic_keywords = [
        "ermaozi", "peasoft", "aiboboxx", "mfuu", "freefq", "kxswa",
        "llywhn", "adiwzx", "changfengoss", "mymysub", "yeahwu",
        "mksshare", "bulianglin", "yiiss", "free18", "shaoyouvip",
        "yonggekkk", "vxiaodong", "wxloststar",
    ]
    for kw in domestic_keywords:
        if kw in u:
            return 8
    aggregator_keywords = ["mahdibland", "epodonios", "barry-far"]
    for kw in aggregator_keywords:
        if kw in u:
            return 5
    if "vless" in u or "hysteria2" in u:
        return 7
    if "trojan" in u:
        return 6
    return 3
