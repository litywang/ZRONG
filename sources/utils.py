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



# ===== 编码/解码工具 =====

def is_base64(s: str) -> bool:
    """判断是否为 base64 编码（增强版：支持标准/base64url/无填充）"""
    try:
        s = s.strip()
        if len(s) < 10:
            return False
        # v30.11: 同时匹配标准base64和base64url
        if not re.match(r'^[A-Za-z0-9+/_\-=]+$', s):
            return False
        # 尝试标准base64
        try:
            base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
            return True
        except (ValueError, base64.binascii.Error):
            pass
        # 尝试base64url
        try:
            base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
            return True
        except (ValueError, base64.binascii.Error):
            pass
        return False
    except (ValueError, base64.binascii.Error):
        logging.debug("is_base64 failed", exc_info=True)
        return False


def decode_b64(c: str) -> str:
    """Base64 解码（增强版：标准/base64url/多层嵌套/Clash专用格式）"""
    c = c.strip()
    for attempt in range(3):  # v30.11: 最多尝试3层嵌套base64
        m = len(c) % 4
        padded = c + "=" * ((4 - m) % 4) if m else c
        decoded = None
        # 尝试标准base64
        try:
            decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        except (ValueError, base64.binascii.Error):
            pass
        # 尝试base64url（-替换+，_替换/）
        if decoded is None:
            try:
                decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
            except (ValueError, base64.binascii.Error):
                pass
        if decoded is None:
            return c  # 无法解码，返回原始内容
        # 检查解码结果是否包含协议链接
        if "://" in decoded:
            return decoded
        # 检查解码结果是否还是base64（嵌套编码）
        if is_base64(decoded):
            c = decoded
            continue
        # 解码结果不含协议链接也不是base64，返回
        return decoded
    return c  # 超过3层嵌套，返回原始内容


def deep_decode_line(line: str) -> list:
    """v30.11: 深度解码单行——尝试base64解码后提取协议链接
    处理场景：
    - 单行base64编码的协议链接（vmess://base64data）
    - base64嵌套：整行base64解码后得到多个协议链接
    - Clash订阅中base64编码的节点段
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return []
    results = []

    # 场景1：已是协议链接
    if '://' in line:
        return [line]

    # 场景2：整行是base64编码
    if is_base64(line):
        decoded = decode_b64(line)
        if decoded and decoded != line:
            for sub_line in decoded.splitlines():
                sub_line = sub_line.strip()
                if sub_line and '://' in sub_line:
                    results.append(sub_line)
                elif is_base64(sub_line):
                    # 二次base64
                    d2 = decode_b64(sub_line)
                    if d2 and d2 != sub_line:
                        for sub2 in d2.splitlines():
                            sub2 = sub2.strip()
                            if sub2 and '://' in sub2:
                                results.append(sub2)
            if results:
                return results
            # base64解码后无协议链接，但解码成功→可能是JSON/其他格式
            for sub_line in decoded.splitlines():
                sub_line = sub_line.strip()
                if sub_line and not sub_line.startswith('#'):
                    results.append(sub_line)
            if results:
                return results

    # 场景3：vmess://后跟base64（标准格式）
    if line.startswith('vmess://'):
        return [line]  # vmess解析器内部会处理base64

    return [line] if line else []


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

    # ===== 一级：国内优质源（最高权重） =====
    tier1_domestic = [
        # 核心国内源
        "ermaozi", "peasoft", "aiboboxx", "mfuu", "freefq", "kxswa",
        "llywhn", "adiwzx", "changfengoss", "mymysub", "yeahwu",
        "mksshare", "bulianglin", "yiiss", "free18", "shaoyouvip",
        "yonggekkk", "vxiaodong", "wxloststar", "ONGKB",
        # 国内 Clash/Mihomo 源
        "aiboboxx/clashfree", "ermaozi.*clash", "peasoft.*meta",
        # 国内聚合源
        "anaer/Sub", "Pawdroid/Free-servers",
    ]
    for kw in tier1_domestic:
        if kw in u:
            return 10

    # ===== 二级：亚洲地区专用源 =====
    tier2_asia = [
        # mahdibland 亚洲分区
        "mahdibland.*hk", "mahdibland.*jp", "mahdibland.*sg",
        "mahdibland.*tw", "mahdibland.*kr", "mahdibland.*th",
        "mahdibland.*vn", "mahdibland.*my", "mahdibland.*id",
        "mahdibland.*ph", "mahdibland.*asia",
        # Epodonios 亚洲分区
        "Epodonios.*hk", "Epodonios.*jp", "Epodonios.*sg",
        "Epodonios.*tw", "Epodonios.*kr",
        # 其他亚洲源
        "xingsin", "chengaikun", "NastyaFan",
    ]
    for kw in tier2_asia:
        if kw in u:
            return 8

    # ===== 三节：协议类型权重 =====
    if "vless" in u or "hysteria2" in u:
        return 7
    if "trojan" in u:
        return 6

    # ===== 四级：国际聚合源 =====
    tier4_aggregator = ["mahdibland", "Epodonios", "barry-far", "roosterkid"]
    for kw in tier4_aggregator:
        if kw in u:
            return 5

    # 默认权重
    return 3
