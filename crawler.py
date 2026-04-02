#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v22.4 - 性能极速版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 22.4
优化：大幅精简源 + 高并发 + 严格阈值 → 目标耗时 < 30分钟
核心原则：三層严格检测 + 全量优质源 + 零语法错误 + 最佳稳定性
"""

import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, signal, gzip, shutil, ssl, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
import threading
import random
from datetime import datetime

# ==================== 配置区 ====================
CANDIDATE_URLS = [
    # ============ 核心订阅源（精简到10个高质量） ============
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://shz.al/~WangCai",
]

TELEGRAM_CHANNELS = [
    # ============ 核心频道（精简到12个高质量） ============
    "v2ray_free", "freev2rayng", "v2rayng_free", "sub_free",
    "vmessfree", "vlessfree", "trojanfree", "ssfree",
    "proxiesdaily", "clashnode", "freeclash", "freeproxy",
]

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo; Shadowrocket"}
TIMEOUT = 15  # 缩短超时时间

MAX_FETCH_NODES = 1500  # 减少抓取上限
MAX_TCP_TEST_NODES = 200   # 减少TCP测试
MAX_PROXY_TEST_NODES = 80  # 减少代理测试
MAX_FINAL_NODES = 60       # 减少最终输出
MAX_LATENCY = 1500         # 更严格的延迟阈值
MIN_PROXY_SPEED = 0.05     # 更高的速度要求
MAX_PROXY_LATENCY = 2500
TEST_URL = "http://www.gstatic.com/generate_204"

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

MAX_WORKERS = 30  # 大幅提高并发
REQUESTS_PER_SECOND = 3.0  # 提高请求频率
MAX_RETRIES = 2  # 减少重试

# 订阅源抓取专用高并发
FETCH_WORKERS = 50  # 抓取并发数

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"

USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 11; Mobile; rv:84.0) Gecko/84.0 Firefox/84.0",
]

# ⭐ 新增：GitHub Fork 基础仓库（核心，精简版）
GITHUB_BASE_REPOS = [
    # ============ 国内优质源（优先，只保留核心） ============
    "ermaozi/get_subscribe",                 # 国内维护，更新快
    "peasoft/NoMoreWalls",                   # 国内热门
    "aiboboxx/v2rayfree",                    # 国内免费节点
    "freefq/free",                           # freefq 大神
    
    # ============ 国际核心源（精简到5个） ============
    "wzdnzd/aggregator",                     # 聚合工具鼻祖
    "mahdibland/V2RayAggregator",            # V2RayAggregator 主力
    "PuddinCat/BestClash",                   # BestClash 高质量
    "roosterkid/openproxylist",              # 公开代理列表
    "anaer/Sub",                             # anaer 订阅汇总
]


def ensure_clash_dir():
    """安全创建目录"""
    if WORK_DIR.exists() and not WORK_DIR.is_dir():
        try:
            WORK_DIR.unlink()
        except: pass
    WORK_DIR.mkdir(parents=True, exist_ok=True)


class SmartRateLimiter:
    def __init__(self):
        self.locks = {}
        self.last_call = {}
        self.min_interval = 1.0 / REQUESTS_PER_SECOND

    def wait(self, url=""):
        domain = urlparse(url).netloc or "default"
        if domain not in self.locks:
            self.locks[domain] = threading.Lock()
            self.last_call[domain] = 0
        with self.locks[domain]:
            now = time.time()
            elapsed = now - self.last_call[domain]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call[domain] = time.time()


limiter = SmartRateLimiter()


def create_session():
    session = requests.Session()
    retry = Retry(total=MAX_RETRIES, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


session = create_session()


def generate_unique_id(proxy):
    key = f"{proxy.get('server', '')}:{proxy.get('port', '')}:{proxy.get('uuid', proxy.get('password', ''))}"
    return hashlib.md5(key.encode()).hexdigest()[:8].upper()


# ⭐ 新增：GitHub Fork 发现功能（从 v21.0 复制完整实现）
def discover_github_forks():
    """全面发掘 GitHub Fork 的高质量订阅源 - 并行优化版"""
    print("🔍 动态发现 GitHub Fork...")
    subs = []
    
    # 每个 fork 的潜在路径（精简到6个高频路径）
    potential_paths = [
        "proxies.yaml", 
        "all.txt",
        "subscription.txt",
        "v2ray.txt",
        "vmess.txt",
        "config.yaml",
    ]
    
    # 并行获取所有 base repo 的 fork 列表
    def fetch_forks(base):
        url = f"https://api.github.com/repos/{base}/forks?per_page=100&sort=newest"
        try:
            resp = session.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return []
    
    # 并行获取 fork 列表
    all_forks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_forks, base): base for base in GITHUB_BASE_REPOS}
        for future in as_completed(futures):
            forks = future.result()
            all_forks.extend(forks)
            if forks:
                print(f"   📦 {futures[future]}: {len(forks)} forks")
    
    print(f"   📊 共获取 {len(all_forks)} 个 fork...")
    
    # 批量构建所有潜在 URL
    all_urls_to_check = []
    for fork in all_forks:
        if fork.get("full_name") and fork.get("fork"):
            fullname = fork["full_name"]
            branch = fork.get("default_branch", "main")
            for path in potential_paths:
                raw_url = f"https://raw.githubusercontent.com/{fullname}/{branch}/{path}"
                all_urls_to_check.append(raw_url)
    
    print(f"   🔗 构建 {len(all_urls_to_check)} 个潜在 URL（跳过验证，直接拉取）...")
    
    # 直接去重加入，不验证——让 fetch_and_parse 自然淘汰无效源
    subs = list(set(all_urls_to_check))
    print(f"✅ GitHub Fork 共发现 {len(subs)} 个候选来源\n")
    return subs


def check_url_fast(u):
    """快速URL验证（缩短超时）"""
    try:
        return session.head(u, timeout=5, allow_redirects=True).status_code == 200
    except:
        return False


def check_url(u):
    limiter.wait(u)
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False


def strip_url(u):
    """关键修复：确保 URL 无空格"""
    if u: return u.strip().replace("\n", "").replace(" ", "")
    return ""


# ⭐ 节点解析器（保持不变）
def parse_vmess(node):
    try:
        if not node.startswith("vmess://"): return None
        payload = node[8:]
        m = len(payload) % 4
        if m: payload += "=" * (4 - m)
        d = base64.b64decode(payload).decode("utf-8", errors="ignore")
        if not d.startswith("{"): return None
        c = json.loads(d)
        
        # 从 ps 字段提取原始名称
        original_name = c.get("ps", "")
        if not original_name:
            uid = generate_unique_id({'server': c.get('add') or c.get('host'), 'port': int(c.get('port', 443)), 'uuid': c.get('id')})
            original_name = f"VM-{uid}"
        
        p = {
            "name": original_name, "type": "vmess", "server": c.get("add") or c.get("host", ""),
            "port": int(c.get("port", 443)), "uuid": c.get("id", ""), "alterId": int(c.get("aid", 0)),
            "cipher": "auto", "udp": True, "skip-cert-verify": True
        }
        net = c.get("net", "tcp").lower()
        if net in ["ws", "h2", "grpc"]: p["network"] = net
        if c.get("tls") == "tls" or c.get("security") == "tls":
            p["tls"] = True
            p["sni"] = c.get("sni") or c.get("host") or p["server"]
        if net == "ws":
            wo = {}
            if c.get("path"): wo["path"] = c.get("path")
            if c.get("host"): wo["headers"] = {"Host": c.get("host")}
            if wo: p["ws-opts"] = wo
        return p if p["server"] and p["uuid"] else None
    except: return None


def parse_vless(node):
    try:
        if not node.startswith("vless://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        uuid = p_url.username or ""
        if not uuid: return None
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        sec = gp("security")
        
        # 从 URL fragment 提取原始名称
        original_name = p_url.fragment if p_url.fragment else f"VL-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'uuid': uuid})}"
        
        proxy = {
            "name": original_name, "type": "vless", "server": p_url.hostname, "port": int(p_url.port or 443),
            "uuid": uuid, "udp": True, "skip-cert-verify": True
        }
        if sec in ["tls", "reality"]:
            proxy["tls"] = True
            proxy["sni"] = gp("sni") or proxy["server"]
        if sec == "reality":
            pbk, sid = gp("pbk"), gp("sid")
            if pbk and sid: proxy["reality-opts"] = {"public-key": pbk, "short-id": sid}
            else: return None
        fp = gp("fp")
        proxy["client-fingerprint"] = fp if fp else "chrome"
        flow = gp("flow")
        if flow: proxy["flow"] = flow
        tp = gp("type")
        if tp == "ws":
            proxy["network"] = "ws"
            wo = {}
            if gp("path"): wo["path"] = gp("path")
            if gp("host"): wo["headers"] = {"Host": gp("host")}
            if wo: proxy["ws-opts"] = wo
        return proxy
    except: return None


def parse_trojan(node):
    try:
        if not node.startswith("trojan://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        pwd = p_url.username or unquote(p_url.path.strip("/"))
        if not pwd: return None
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        
        # 从 URL fragment 提取原始名称
        original_name = p_url.fragment if p_url.fragment else f"TJ-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})}"
        
        proxy = {
            "name": original_name, "type": "trojan", "server": p_url.hostname, "port": int(p_url.port or 443),
            "password": pwd, "udp": True, "skip-cert-verify": True, "sni": gp("sni") or p_url.hostname
        }
        alpn = gp("alpn")
        if alpn: proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        fp = gp("fp")
        if fp: proxy["client-fingerprint"] = fp
        return proxy
    except: return None


def parse_ss(node):
    try:
        if not node.startswith("ss://"): return None
        parts = node[5:].split("#")
        info = parts[0]
        # 从 URL fragment 提取原始名称
        original_name = parts[1] if len(parts) > 1 else None
        try:
            decoded = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8", errors="ignore")
            method_pwd, server_info = decoded.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        except:
            method_pwd, server_info = info.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        server, port = server_info.split(":", 1)
        
        # 如果没有原始名称，生成默认名称
        if not original_name:
            original_name = f"SS-{generate_unique_id({'server': server, 'port': int(port), 'password': pwd})}"
        
        return {"name": original_name, "type": "ss", "server": server, "port": int(port), "cipher": method, "password": pwd, "udp": True}
    except: return None


def parse_hysteria2(node):
    """解析 hysteria2:// 链接"""
    try:
        if not node.startswith("hysteria2://") and not node.startswith("hy2://"): return None
        prefix = "hysteria2://" if node.startswith("hysteria2://") else "hy2://"
        p_url = urlparse(node)
        if not p_url.hostname: return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        uid = generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})
        proxy = {
            "name": f"H2-{uid}", "type": "hysteria2", "server": p_url.hostname,
            "port": int(p_url.port or 443), "password": pwd, "udp": True, "skip-cert-verify": True
        }
        sni = gp("sni")
        if sni: proxy["sni"] = sni
        elif p_url.hostname: proxy["sni"] = p_url.hostname
        obfs = gp("obfs")
        if obfs: proxy["obfs"] = obfs
        obfs_password = gp("obfs-password")
        if obfs_password: proxy["obfs-password"] = obfs_password
        insecure = gp("insecure")
        if insecure == "1": proxy["skip-cert-verify"] = True
        fp = gp("fp")
        if fp: proxy["client-fingerprint"] = fp
        return proxy if proxy["server"] else None
    except: return None


def parse_tuic(node):
    """解析 tuic:// 链接"""
    try:
        if not node.startswith("tuic://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        uuid_val = p_url.username or ""
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        uid = generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': uuid_val})
        proxy = {
            "name": f"TU-{uid}", "type": "tuic", "server": p_url.hostname,
            "port": int(p_url.port or 443), "uuid": uuid_val, "password": uuid_val,
            "udp": True, "skip-cert-verify": True
        }
        sni = gp("sni")
        if sni: proxy["sni"] = sni
        fp = gp("fp")
        if fp: proxy["client-fingerprint"] = fp
        alpn = gp("alpn")
        if alpn: proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        return proxy if proxy["server"] else None
    except: return None


def parse_hysteria(node):
    """解析 hysteria:// 链接（v1）"""
    try:
        if not node.startswith("hysteria://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        uid = generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})
        proxy = {
            "name": f"HY-{uid}", "type": "hysteria", "server": p_url.hostname,
            "port": int(p_url.port or 443), "password": pwd, "udp": True,
            "skip-cert-verify": True, "protocol": "udp"
        }
        sni = gp("sni")
        if sni: proxy["sni"] = sni
        obfs = gp("obfs")
        if obfs: proxy["obfs"] = obfs
        auth_str = gp("auth")
        if auth_str: proxy["auth_str"] = auth_str
        alpn = gp("alpn")
        if alpn: proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        insecure = gp("insecure")
        if insecure == "1": proxy["skip-cert-verify"] = True
        return proxy if proxy["server"] else None
    except: return None


def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"): return None
    if node.startswith("vmess://"): return parse_vmess(node)
    elif node.startswith("vless://"): return parse_vless(node)
    elif node.startswith("trojan://"): return parse_trojan(node)
    elif node.startswith("ss://"): return parse_ss(node)
    elif node.startswith("hysteria2://") or node.startswith("hy2://"): return parse_hysteria2(node)
    elif node.startswith("hysteria://"): return parse_hysteria(node)
    elif node.startswith("tuic://"): return parse_tuic(node)
    return None


# ⭐ YAML 订阅源解析
def parse_yaml_proxies(content):
    """解析 YAML 格式的 Clash/Mihomo 订阅，提取 proxies 列表"""
    try:
        data = yaml.safe_load(content)
        if not data or not isinstance(data, dict):
            return []
        # 支持 proxies: / Proxy: 两种键名
        proxies = data.get("proxies") or data.get("Proxy") or []
        if not isinstance(proxies, list):
            return []
        results = []
        for p in proxies:
            if not isinstance(p, dict) or not p.get("server"):
                continue
            ptype = (p.get("type") or "").lower()
            # 只认 Mihomo/Clash 支持的协议
            if ptype not in ("vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2", "tuic",
                             "wireguard", "shadowtls"):
                continue
            # 基本校验：必须有 server + port
            try:
                port = int(p.get("port", 0))
                if port <= 0:
                    continue
            except (ValueError, TypeError):
                continue
            # 保留原始名称，如果没有则生成唯一 ID
            original_name = p.get("name", "")
            if not original_name:
                key = f"{p['server']}:{port}:{p.get('uuid', p.get('password', ''))}"
                h = hashlib.md5(key.encode()).hexdigest()[:8].upper()
                ptype_tag = {"vmess":"VM","vless":"VL","trojan":"TJ","ss":"SS","ssr":"SR",
                             "hysteria":"HY","hysteria2":"H2","tuic":"TU","wireguard":"WG","shadowtls":"ST"}
                original_name = f"{ptype_tag.get(ptype,'XX')}-{h}"
            p["name"] = original_name
            results.append(p)
        return results
    except Exception:
        return []


def is_yaml_content(content):
    """判断内容是否为 YAML 订阅源"""
    # 快速判断：如果内容包含 proxies: 或 Proxy: 关键字且含有 server 字段
    c_lower = content[:2000].lower()
    return ("proxies:" in c_lower or "proxy:" in c_lower) and ("server:" in c_lower)


# ⭐ 辅助工具（保持不变）
def get_region(name):
    """根据节点名称检测区域 - 增强版，支持英文名、旗帜emoji、城市名"""
    nl = name.lower()
    
    # 香港检测
    if any(k in nl for k in ["hk", "hongkong", "港", "hong kong", "🇭🇰", "香港", "深港", "沪港", "京港"]):
        return "🇭🇰", "HK"
    # 台湾检测
    elif any(k in nl for k in ["tw", "taiwan", "台", "🇹🇼", "台湾", "臺灣", "台北", "台中", "新北", "taipei"]):
        return "🇹🇼", "TW"
    # 日本检测
    elif any(k in nl for k in ["jp", "japan", "日", "🇯🇵", "日本", "东京", "大阪", "tokyo", "osaka", "川日", "泉日", "埼玉"]):
        return "🇯🇵", "JP"
    # 新加坡检测
    elif any(k in nl for k in ["sg", "singapore", "新", "🇸🇬", "新加坡", "狮城", "沪新", "京新", "深新"]):
        return "🇸🇬", "SG"
    # 韩国检测
    elif any(k in nl for k in ["kr", "korea", "韩", "🇰🇷", "韩国", "韓", "首尔", "春川", "seoul"]):
        return "🇰🇷", "KR"
    # 美国检测
    elif any(k in nl for k in ["us", "usa", "美", "🇺🇸", "美国", "美利坚", "洛杉矶", "硅谷", "纽约", "united states", "america", "los angeles", "new york"]):
        return "🇺🇸", "US"
    # 英国检测
    elif any(k in nl for k in ["uk", "britain", "英", "🇬🇧", "英国", "伦敦", "united kingdom", "london", "england"]):
        return "🇬🇧", "UK"
    # 德国检测
    elif any(k in nl for k in ["de", "germany", "德", "🇩🇪", "德国", "法兰克福", "frankfurt", "berlin"]):
        return "🇩🇪", "DE"
    # 法国检测
    elif any(k in nl for k in ["fr", "france", "法", "🇫🇷", "法国", "巴黎", "paris"]):
        return "🇫🇷", "FR"
    # 加拿大检测
    elif any(k in nl for k in ["ca", "canada", "加", "🇨🇦", "加拿大", "渥太华", "多伦多", "toronto", "vancouver"]):
        return "🇨🇦", "CA"
    # 澳大利亚检测
    elif any(k in nl for k in ["au", "australia", "澳", "🇦🇺", "澳大利亚", "澳洲", "悉尼", "sydney", "melbourne"]):
        return "🇦🇺", "AU"
    # 荷兰检测
    elif any(k in nl for k in ["nl", "netherlands", "荷", "🇳🇱", "荷兰", "阿姆斯特丹", "amsterdam"]):
        return "🇳🇱", "NL"
    # 俄罗斯检测
    elif any(k in nl for k in ["ru", "russia", "俄", "🇷🇺", "俄罗斯", "莫斯科", "moscow"]):
        return "🇷🇺", "RU"
    # 印度检测
    elif any(k in nl for k in ["in", "india", "印", "🇮🇳", "印度", "孟买", "mumbai", "delhi"]):
        return "🇮🇳", "IN"
    # 巴西检测
    elif any(k in nl for k in ["br", "brazil", "巴", "🇧🇷", "巴西", "圣保罗", "sao paulo"]):
        return "🇧🇷", "BR"
    # 阿根廷检测
    elif any(k in nl for k in ["ar", "argentina", "阿", "🇦🇷", "阿根廷", "buenos aires"]):
        return "🇦🇷", "AR"
    # 泰国检测
    elif any(k in nl for k in ["th", "thailand", "泰", "🇹🇭", "泰国", "曼谷", "bangkok"]):
        return "🇹🇭", "TH"
    # 越南检测
    elif any(k in nl for k in ["vn", "vietnam", "越", "🇻🇳", "越南", "胡志明", "hanoi"]):
        return "🇻🇳", "VN"
    # 马来西亚检测
    elif any(k in nl for k in ["my", "malaysia", "马", "🇲🇾", "马来西亚", "吉隆坡", "kuala lumpur"]):
        return "🇲🇾", "MY"
    # 菲律宾检测
    elif any(k in nl for k in ["ph", "philippines", "菲", "🇵🇭", "菲律宾", "马尼拉", "manila"]):
        return "🇵🇭", "PH"
    # 印尼检测
    elif any(k in nl for k in ["id", "indonesia", "印尼", "🇮🇩", "雅加达", "jakarta"]):
        return "🇮🇩", "ID"
    # 墨西哥检测
    elif any(k in nl for k in ["mx", "mexico", "墨", "🇲🇽", "墨西哥"]):
        return "🇲🇽", "MX"
    # 意大利检测
    elif any(k in nl for k in ["it", "italy", "意", "🇮🇹", "意大利", "米兰", "罗马", "milan", "rome"]):
        return "🇮🇹", "IT"
    # 西班牙检测
    elif any(k in nl for k in ["es", "spain", "西", "🇪🇸", "西班牙", "马德里", "madrid"]):
        return "🇪🇸", "ES"
    # 瑞士检测
    elif any(k in nl for k in ["ch", "switzerland", "瑞", "🇨🇭", "瑞士", "苏黎世", "zurich"]):
        return "🇨🇭", "CH"
    # 奥地利检测
    elif any(k in nl for k in ["at", "austria", "奥", "🇦🇹", "奥地利", "维也纳", "vienna"]):
        return "🇦🇹", "AT"
    # 瑞典检测
    elif any(k in nl for k in ["se", "sweden", "瑞典", "🇸🇪", "斯德哥尔摩", "stockholm"]):
        return "🇸🇪", "SE"
    # 波兰检测
    elif any(k in nl for k in ["pl", "poland", "波", "🇵🇱", "波兰", "华沙", "warsaw"]):
        return "🇵🇱", "PL"
    # 土耳其检测
    elif any(k in nl for k in ["tr", "turkey", "土", "🇹🇷", "土耳其", "伊斯坦布尔", "istanbul"]):
        return "🇹🇷", "TR"
    # 南非检测
    elif any(k in nl for k in ["za", "south africa", "南非", "🇿🇦", "约翰内斯堡", "johannesburg"]):
        return "🇿🇦", "ZA"
    # 阿联酋检测
    elif any(k in nl for k in ["ae", "uae", "迪", "🇦🇪", "阿联酋", "迪拜", "dubai", "abu dhabi"]):
        return "🇦🇪", "AE"
    # 以色列检测
    elif any(k in nl for k in ["il", "israel", "以", "🇮🇱", "以色列", "特拉维夫", "tel aviv"]):
        return "🇮🇱", "IL"
    # 爱尔兰检测
    elif any(k in nl for k in ["ie", "ireland", "爱尔兰", "🇮🇪", "都柏林", "dublin"]):
        return "🇮🇪", "IE"
    # 葡萄牙检测
    elif any(k in nl for k in ["pt", "portugal", "葡", "🇵🇹", "葡萄牙", "里斯本", "lisbon"]):
        return "🇵🇹", "PT"
    # 捷克检测
    elif any(k in nl for k in ["cz", "czech", "捷", "🇨🇿", "捷克", "布拉格", "prague"]):
        return "🇨🇿", "CZ"
    # 罗马尼亚检测
    elif any(k in nl for k in ["ro", "romania", "罗", "🇷🇴", "罗马尼亚", "布加勒斯特", "bucharest"]):
        return "🇷🇴", "RO"
    # 匈牙利检测
    elif any(k in nl for k in ["hu", "hungary", "匈", "🇭🇺", "匈牙利", "布达佩斯", "budapest"]):
        return "🇭🇺", "HU"
    # 希腊检测
    elif any(k in nl for k in ["gr", "greece", "希", "🇬🇷", "希腊", "雅典", "athens"]):
        return "🇬🇷", "GR"
    # 芬兰检测
    elif any(k in nl for k in ["fi", "finland", "芬", "🇫🇮", "芬兰", "赫尔辛基", "helsinki"]):
        return "🇫🇮", "FI"
    # 丹麦检测
    elif any(k in nl for k in ["dk", "denmark", "丹", "🇩🇰", "丹麦", "哥本哈根", "copenhagen"]):
        return "🇩🇰", "DK"
    # 挪威检测
    elif any(k in nl for k in ["no", "norway", "挪", "🇳🇴", "挪威", "奥斯陆", "oslo"]):
        return "🇳🇴", "NO"
    # 比利时检测
    elif any(k in nl for k in ["be", "belgium", "比", "🇧🇪", "比利时", "布鲁塞尔", "brussels"]):
        return "🇧🇪", "BE"
    # 新西兰检测
    elif any(k in nl for k in ["nz", "new zealand", "新西兰", "🇳🇿", "奥克兰", "auckland"]):
        return "🇳🇿", "NZ"
    # 智利检测
    elif any(k in nl for k in ["cl", "chile", "智", "🇨🇱", "智利", "圣地亚哥", "santiago"]):
        return "🇨🇱", "CL"
    # 哥伦比亚检测
    elif any(k in nl for k in ["co", "colombia", "哥", "🇨🇴", "哥伦比亚", "波哥大", "bogota"]):
        return "🇨🇴", "CO"
    # 秘鲁检测
    elif any(k in nl for k in ["pe", "peru", "秘", "🇵🇪", "秘鲁", "利马", "lima"]):
        return "🇵🇪", "PE"
    # 乌克兰检测
    elif any(k in nl for k in ["ua", "ukraine", "乌", "🇺🇦", "乌克兰", "基辅", "kiev", "kyiv"]):
        return "🇺🇦", "UA"
    # 哈萨克斯坦检测
    elif any(k in nl for k in ["kz", "kazakhstan", "哈", "🇰🇿", "哈萨克斯坦", "阿拉木图", "almaty"]):
        return "🇰🇿", "KZ"
    
    return "🌍", "OT"


def is_asia(p):
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in [
        "hk", "hongkong", "港",
        "tw", "taiwan", "台",
        "jp", "japan", "日",
        "sg", "singapore", "新加坡", "新",
        "kr", "korea", "韩",
        "asia", "hkt",
        "th", "thailand", "泰",
        "vn", "vietnam", "越",
        "my", "malaysia", "马",
        "id", "indonesia", "印"
    ])


def is_china_mainland(p):
    """判断是否为内地直连节点（一般不可用，用于过滤）"""
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in [
        "cn", "china", "中国", "国内", "直连", "direct",
        "北京", "上海", "广州", "深圳", "成都", "杭州"
    ])


def filter_quality(p):
    """节点质量过滤（借鉴 wzdnzd/aggregator）"""
    name = p.get("name", "").lower()
    
    # 排除关键词
    exclude_keywords = [
        "过期", "到期", "失效", "测试", "test", "expire", "expired",
        "广告", "推广", "vip", "付费", "premium", "paid",
        "限速", "slow", "慢", "2x", "3x", "5x",  # 高倍率节点
    ]
    for kw in exclude_keywords:
        if kw in name:
            return False
    
    # 排除内地直连节点（一般不可用）
    if is_china_mainland(p):
        return False
    
    return True


def is_base64(s):
    try:
        s = s.strip()
        if len(s) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s + "=" * (4 - len(s) % 4), validate=True)
        return True
    except:
        return False


def decode_b64(c):
    try:
        c = c.strip()
        m = len(c) % 4
        if m: c += "=" * (4 - m)
        d = base64.b64decode(c).decode("utf-8", errors="ignore")
        return d if "://" in d else c
    except:
        return c


def fetch(url):
    limiter.wait(url)
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def tcp_ping(host, port, to=1.0):  # 缩短超时到1秒
    if not host:
        return 9999.0
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(to)
        st = time.time()
        s.connect((host, port))
        s.close()
        return round((time.time() - st) * 1000, 1)
    except:
        return 9999.0


# ==================== Telegram 爬取 (借鉴 wzdnzd/aggregator) ====================
def is_valid_url(url):
    """⭐ 新增：URL 有效性检查（核心优化）"""
    if not url or len(url) < 10:
        return False
    
    # 去除前后空白字符（关键！）
    url = url.strip().rstrip('.,;:')
    
    # 协议检查
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    
    # 排除无效域名
    invalid_domains = ["t.me", "telegram.org"]
    if any(domain in url for domain in invalid_domains):
        return False
    
    return True


def clean_url(url):
    """🔥 新增：URL 规范化（比 wzdnzd 更全面）"""
    if not url:
        return ""
    
    # 移除所有不可见字符和换行符
    cleaned = re.sub(r'\s+', '', url)
    
    # 统一协议为 https
    cleaned = cleaned.replace("http://", "https://", 1)
    
    # 去除尾部标点
    cleaned = cleaned.rstrip('.,;:!?"\\')
    
    # 长度检查
    if len(cleaned) < 15:
        return ""
    
    # 域名长度检查
    domain = urlparse(cleaned).netloc
    if not domain or len(domain) < 4:
        return ""
    
    return cleaned


def check_subscription_quality(url):
    """⭐ 新增：订阅质量快速筛查（借鉴 wzdnzd）"""
    quality_indicators = [
        "token=",
        "/subscribe/",
        "/api/v1/client/",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        "/link/"
    ]
    
    url_lower = url.lower()
    match_count = sum(1 for indicator in quality_indicators if indicator in url_lower)
    
    # 至少需要匹配 1 个高质量标记
    return match_count >= 1


def get_telegram_pages(channel):
    """🔧 修复：兼容新旧两种 HTML 结构"""
    try:
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=TIMEOUT).text
        
        # ⭐ 优化正则（借鉴 wzdnzd）- 多种格式兼容
        patterns = [
            rf'<meta\s+content="/s/{channel}\?before=(\d+)">?',
            rf'<link[^>]*href=["\']?/s/{channel}/?\??before=(\d+)["\']?[^>]*>',
            rf'/s/{channel}[^"]*before=(\d+)',
        ]
        
        for pattern in patterns:
            groups = re.findall(pattern, content, re.IGNORECASE)
            if groups and groups[0].isdigit():
                return int(groups[0])
        
        # 降级策略：尝试访问频道主页判断是否存在
        resp = session.get(f"https://t.me/{channel}", timeout=10)
        if resp.status_code == 200 and channel in resp.url:
            return 1  # 至少有一页
        
        return 0
    except Exception as e:
        print(f"⚠️ {channel} 页码获取失败：{str(e)[:50]}")
        return 0


def crawl_telegram_page(url, limits=25):
    """🔧 修复：全面增强 URL 提取（完全借鉴 wzdnzd）"""
    try:
        limiter.wait(url)
        headers = {
            "User-Agent": random.choice(USER_AGENT_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        content = session.get(url, timeout=TIMEOUT, headers=headers).text
        
        if not content or len(content) < 100:
            return {}
        
        collections = {}
        
        # ⭐ wzdnzd 核心：多级正则匹配（完整移植）
        patterns = [
            # 模式 1: 标准订阅链接
            r'https?://[a-zA-Z0-9\u4e00-\u9fa5\-]+\.[a-zA-Z0-9\u4e00-\u9fa5\-]+(?::\d+)?(?:/.*)?(?:sub|subscribe|token)[^\s<>]*',
            
            # 模式 2: GitHub Raw 链接
            r'https?://raw\.githubusercontent\.com/[a-zA-Z0-9\-]+/[a-zA-Z0-9\-]+/[a-zA-Z0-9\-]+/(.*\.txt|.*\.yaml|.*\.yml)',
            
            # 模式 3: 通用域名 + 路径
            r'https?://(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z0-9\-]+/(?:(?:sub|subscribe)/|link/[a-zA-Z0-9]+|api/v[0-9]/client/subscribe)',
        ]
        
        all_links = []
        for pattern in patterns:
            all_links.extend(re.findall(pattern, content))
        
        # ⭐ wzdnzd 核心：去重和质量过滤（直接采用）
        processed_urls = set()
        valid_links = []
        
        for link in all_links[:limits * 2]:  # 放宽初始收集量
            # 步骤 1: URL 清理（关键）
            link = clean_url(link)
            
            # 步骤 2: 有效性检查
            if not link or not is_valid_url(link):
                continue
            
            # 步骤 3: 去重（集合去重）
            if link in processed_urls:
                continue
            processed_urls.add(link)
            
            # 步骤 4: 质量筛选（提高纯度）
            if check_subscription_quality(link):
                valid_links.append(link)
        
        # 最终限制输出数量
        for link in valid_links[:limits]:
            collections[link] = {"origin": "TELEGRAM"}
        
        if collections:
            print(f"   ✅ 该页面发现 {len(collections)} 个有效订阅链接")
        else:
            print(f"   ⚠️ 该页面未发现有效订阅链接：{url[:60]}")
        
        return collections
        
    except requests.exceptions.Timeout:
        print(f"   ⏱️ 请求超时：{url[:60]}")
        return {}
    except Exception as e:
        print(f"   ❌ 爬取异常：{str(e)[:50]}")
        return {}


def crawl_telegram_channels(channels, pages=2, limits=20):
    """🔧 修复：批量爬取优化 - 并行版本"""
    all_subscribes = {}
    
    def crawl_single_channel(channel):
        """单个频道爬取"""
        channel_subs = {}
        try:
            count = get_telegram_pages(channel)
            if count == 0:
                return channel_subs, channel, "no_pages"
            
            page_arrays = range(count, -1, -100)
            page_num = min(pages, len(page_arrays))
            
            for i, before in enumerate(page_arrays[:page_num]):
                url = f"https://t.me/s/{channel}?before={before}"
                result = crawl_telegram_page(url, limits=limits)
                
                for link, meta in result.items():
                    if link not in channel_subs:
                        channel_subs[link] = meta
                
                time.sleep(random.uniform(0.1, 0.3))  # 缩短延时
                
            return channel_subs, channel, "ok"
        except Exception as e:
            return channel_subs, channel, str(e)[:50]
    
    # 并行爬取所有频道
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(crawl_single_channel, ch): ch for ch in channels}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            channel_subs, channel, status = future.result()
            
            for link, meta in channel_subs.items():
                if link not in all_subscribes:
                    all_subscribes[link] = meta
            
            tg_count = len([c for c in all_subscribes.values() if c["origin"] == "TELEGRAM"])
            print(f"📄 [{completed}/{len(channels)}] {channel}: {len(channel_subs)} 个 | 总计: {tg_count}")
    
    return all_subscribes


# ⭐ Clash 管理（保持不变）
class ClashManager:
    def __init__(self):
        self.process = None
        ensure_clash_dir()

    def download_clash(self):
        if CLASH_PATH.exists(): return True
        url = f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz"
        try:
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code != 200: return False
            temp = WORK_DIR / "mihomo.gz"
            with open(temp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192): f.write(chunk)
            with gzip.open(temp, "rb") as f_in:
                with open(CLASH_PATH, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.chmod(CLASH_PATH, 0o755)
            temp.unlink(missing_ok=True)
            return CLASH_PATH.exists()
        except: return False

    def create_config(self, proxies):
        ensure_clash_dir()
        names = []
        seen = set()
        for i, p in enumerate(proxies[:MAX_PROXY_TEST_NODES]):
            name = p["name"]
            if name in seen: name = f"{name}-{i}"
            seen.add(name)
            names.append(name)
            p["name"] = name
        config = {
            "port": CLASH_PORT, "socks-port": CLASH_PORT + 1, "allow-lan": False, "mode": "rule",
            "log-level": "error", "external-controller": f"127.0.0.1:{CLASH_API_PORT}",
            "secret": "", "ipv6": False, "unified-delay": True, "tcp-concurrent": True,
            "proxies": proxies[:MAX_PROXY_TEST_NODES],
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": names}],
            "rules": ["MATCH,TEST"]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
        return True

    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash(): return False
        LOG_FILE.touch()
        try:
            cmd = [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid, cwd=str(WORK_DIR.absolute()))
            for i in range(30):
                time.sleep(1)
                if self.process.poll() is not None:
                    try:
                        out, _ = self.process.communicate(timeout=2)
                        print(f"   ❌ Clash 崩溃:\n{out[:300]}")
                    except: print("   ❌ Clash 崩溃")
                    return False
                try:
                    if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                        print("   ✅ Clash API 就绪")
                        return True
                except: pass
            print("   ⏱️ Clash 启动超时")
            return False
        except Exception as e:
            print(f"   💥 Clash 启动异常：{e}")
            return False

    def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except: pass
            self.process = None

    def test_proxy(self, name):
        result = {"success": False, "latency": 9999.0, "speed": 0.0, "error": ""}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST", json={"name": name}, timeout=2)
            time.sleep(0.05)  # 极短等待
            px = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            start = time.time()
            resp = requests.get(TEST_URL, proxies=px, timeout=4, allow_redirects=False)
            lat = (time.time() - start) * 1000
            if resp.status_code in [200, 204, 301, 302]:
                sp_start = time.time()
                try:
                    # 更小的测速文件，更短超时
                    sp_resp = requests.get("https://speed.cloudflare.com/__down?bytes=131072", proxies=px, timeout=5)
                    sp = len(sp_resp.content) / max(0.2, time.time() - sp_start) / (1024 * 1024)
                    result = {"success": True, "latency": round(lat, 1), "speed": round(sp, 2), "error": ""}
                except: result["speed"] = 0.0
            else: result["error"] = f"Status:{resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:60]
        return result


# ⭐ 节点命名（保持不变）
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝'}
    REGIONS = {"🇭🇰": "HK", "🇹🇼": "TW", "🇯🇵": "JP", "🇸🇬": "SG", "🇰🇷": "KR", "🇺🇸": "US", "🌍": "OT"}

    def __init__(self):
        self.counters = {}

    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat, speed=None, tcp=False):
        code, region = get_region(flag)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        pfx = self.to_fancy(NODE_NAME_PREFIX)
        if speed:
            return f"{code}{num}-{pfx}|⚡{lat}ms|📥{speed:.1f}MB"
        return f"{code}{num}-{pfx}|⚡{lat}ms{'(TCP)' if tcp else ''}"


# ⭐ 协议链接转换（保持不变）
def format_proxy_to_link(p):
    try:
        if p["type"] == "vmess":
            data = {"v": "2", "ps": p["name"], "add": p["server"], "port": p["port"], "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"), "type": "none", "host": p.get("sni", ""), "path": p.get("ws-opts", {}).get("path", ""), "tls": "tls" if p.get("tls") else ""}
            return "vmess://" + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()
        elif p["type"] == "trojan":
            pwd_enc = urllib.parse.quote(p.get('password', ''), safe='')
            sni = p.get('sni', p.get('server', ''))
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?sni={sni}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "vless":
            return f"vless://{p['uuid']}@{p['server']}:{p['port']}?type={p.get('network', 'tcp')}&security={'tls' if p.get('tls') else 'none'}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "ss":
            auth_enc = base64.b64encode(f"{p['cipher']}:{p['password']}".encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{urllib.parse.quote(p['name'], safe='')}"
        return f"# {p['name']}"
    except:
        return f"# {p['name']}"


# ⭐ 主程序（集成 Fork 发现）
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 50)
    print("🚀 聚合订阅爬虫 v22.4 - 性能极速版")
    print("作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 22.4")
    print("=" * 50)
    
    all_urls = []
    
    try:
        # 1. GitHub Fork 发现（新增加）
        print("\n🔍 GitHub Fork 发现...\n")
        fork_subs = discover_github_forks()
        all_urls.extend(fork_subs)
        print(f"✅ Fork 来源：{len(fork_subs)} 个\n")
        
        # 2. Telegram 频道爬取（保留）
        print("📱 爬取 Telegram 频道...\n")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=1, limits=20)
        tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
        all_urls.extend(tg_urls)
        print(f"✅ Telegram 订阅：{len(tg_urls)} 个\n")
        
        # 3. 固定订阅源（直接加入，跳过验证，由后续 fetch_and_parse 自然淘汰）
        print("📥 加载固定订阅源...\n")
        fixed_urls = [strip_url(u) for u in CANDIDATE_URLS if strip_url(u)]
        all_urls.extend(fixed_urls)
        print(f"✅ 固定订阅源：{len(fixed_urls)} 个（跳过验证，直接拉取）\n")
        
        # 4. 去重
        all_urls = list(set(all_urls))
        print(f"📊 总订阅源：{len(all_urls)} 个\n")
        
        # 5. 抓取节点（并行优化）
        print("📥 抓取节点...\n")
        nodes = {}
        yaml_count = 0  # 统计 YAML 源解析数
        txt_count = 0
        
        def fetch_and_parse(url):
            """并行获取并解析节点（支持 txt + yaml 两种格式）"""
            local_nodes = {}
            c = fetch(url)
            if not c: return local_nodes, False
            
            # 判断是否为 YAML 订阅源
            if is_yaml_content(c):
                yaml_nodes = parse_yaml_proxies(c)
                for p in yaml_nodes:
                    k = f"{p['server']}:{p.get('port',0)}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(k.encode()).hexdigest()
                    if h not in local_nodes:
                        local_nodes[h] = p
                return local_nodes, True
            
            # 普通文本订阅（协议链接）
            if is_base64(c): c = decode_b64(c)
            for l in c.splitlines():
                l = l.strip()
                if not l or l.startswith("#"): continue
                p = parse_node(l)
                if p:
                    k = f"{p['server']}:{p['port']}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(k.encode()).hexdigest()
                    if h not in local_nodes:
                        local_nodes[h] = p
            return local_nodes, False
        
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:  # 使用高并发
            futures = {ex.submit(fetch_and_parse, u): u for u in all_urls}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                local_nodes, is_yaml = future.result()
                for h, p in local_nodes.items():
                    if h not in nodes:
                        nodes[h] = p
                if is_yaml: yaml_count += 1
                else: txt_count += 1
                if completed % 50 == 0:  # 减少打印频率
                    print(f"   进度: {completed}/{len(all_urls)} | 节点: {len(nodes)}")
                if len(nodes) >= MAX_FETCH_NODES:
                    break
        
        print(f"✅ 唯一节点：{len(nodes)} 个 (YAML源: {yaml_count}, TXT源: {txt_count})\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        # 5.5 节点质量过滤（借鉴 wzdnzd/aggregator）
        print("🔍 节点质量过滤...\n")
        before_filter = len(nodes)
        nodes = {h: p for h, p in nodes.items() if filter_quality(p)}
        after_filter = len(nodes)
        print(f"✅ 质量过滤：{before_filter} → {after_filter} 个（排除 {before_filter - after_filter} 个低质量节点）\n")
        
        if not nodes:
            print("❌ 过滤后无有效节点!")
            return
        
        # 6. TCP 测试（提高并发）
        print("⚡ 第一层：TCP 延迟测试...\n")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        
        def test_tcp_node(proxy):
            try:
                lat = tcp_ping(proxy["server"], proxy["port"])
                return {"proxy": proxy, "latency": float(lat), "is_asia": is_asia(proxy)}
            except Exception:
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
        
        # 提高并发数用于 TCP 测试（大幅提高）
        tcp_workers = 100  # 100并发
        with ThreadPoolExecutor(max_workers=tcp_workers) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=2)  # 缩短超时
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                    completed += 1
                    if completed % 50 == 0:
                        print(f"   进度：{completed}/{len(nlist)} | 合格：{len(nres)}")
                except: pass
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in nres if n["is_asia"])
        print(f"✅ 第一层合格：{len(nres)} 个（亚洲：{asia_count}）\n")
        
        # 7. 真实测速 + TCP 保底（保留）
        print("🚀 真实代理测速...\n")
        final = []
        tested = set()
        
        if len(nres) > 0:
            tprox = [n["proxy"] for n in nres[:MAX_PROXY_TEST_NODES]]
            if clash.create_config(tprox) and clash.start():
                proxy_ok = True
                print("📊 测速中...\n")
                for i, item in enumerate(nres[:MAX_PROXY_TEST_NODES]):
                    p = item["proxy"]
                    r = clash.test_proxy(p["name"])
                    k = f"{p['server']}:{p['port']}"
                    if r["success"] and r["latency"] < MAX_PROXY_LATENCY:
                        if r["speed"] >= MIN_PROXY_SPEED or r["latency"] < 500:
                            fl, cd = get_region(p.get("name", ""))
                            p["name"] = namer.generate(fl, int(r["latency"]), r["speed"], tcp=False)
                            final.append(p)
                            tested.add(k)
                            print(f"   ✅ {p['name']}")
                    if len(final) >= MAX_FINAL_NODES: break
                    if (i + 1) % 10 == 0:
                        print(f"   进度：{i + 1}/{min(len(nres), MAX_PROXY_TEST_NODES)} | 合格：{len(final)}")
                clash.stop()
                
                if len(final) < 50:
                    print(f"\n⚠️ 测速合格 {len(final)} 个，使用 TCP 补充...\n")
                    for item in nres:
                        if len(final) >= 50: break
                        p = item["proxy"]
                        k = f"{p['server']}:{p['port']}"
                        if k in tested: continue
                        if item["is_asia"] and item["latency"] < 600:
                            fl, cd = get_region(p.get("name", ""))
                            p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                            final.append(p)
                            tested.add(k)
                            print(f"   📌 {p['name']} (TCP)")
                        elif item["latency"] < 300:
                            fl, cd = get_region(p.get("name", ""))
                            p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                            final.append(p)
                            tested.add(k)
                            print(f"   📌 {p['name']} (TCP)")
            else:
                print("⚠️ Clash 启动失败，使用 TCP 筛选...\n")
                for item in nres[:MAX_FINAL_NODES * 2]:
                    if len(final) >= MAX_FINAL_NODES: break
                    p = item["proxy"]
                    k = f"{p['server']}:{p['port']}"
                    if k in tested: continue
                    if item["is_asia"] and item["latency"] < 600:
                        fl, cd = get_region(p.get("name", ""))
                        p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                        final.append(p)
                        tested.add(k)
                    elif item["latency"] < 300:
                        fl, cd = get_region(p.get("name", ""))
                        p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                        final.append(p)
                        tested.add(k)
        
        final = final[:MAX_FINAL_NODES]
        print(f"\n✅ 最终：{len(final)} 个")
        print(f"📊 真实测速：{'✅' if proxy_ok else '❌'}\n")
        
        # 8. 输出配置（保留）
        print("📝 生成配置...\n")
        final_names = {}
        unique_final = []
        for p in final:
            original_name = p["name"]
            count = final_names.get(original_name, 0)
            if count > 0: p["name"] = f"{original_name}-{count}"
            final_names[original_name] = count + 1
            unique_final.append(p)
        
        cfg = {
            "proxies": unique_final,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in unique_final], "url": TEST_URL, "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in unique_final]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        with open("proxies.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        
        b64_lines = [format_proxy_to_link(p) for p in unique_final]
        with open("subscription.txt", "w", encoding="utf-8") as f:
            f.write('\n'.join(b64_lines))
        
        # 统计
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in unique_final[:20]] if unique_final else []
        min_lat = min(lats) if lats else 0
        
        print("\n" + "=" * 50)
        print("📊 统计结果")
        print("=" * 50)
        print(f"• Fork 来源：{len(fork_subs)}")
        print(f"• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总：{len(all_urls)}")
        print(f"• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}")
        print(f"• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)")
        print(f"• 最低延迟：{min_lat:.1f} ms")
        print(f"• 耗时：{tt:.1f} 秒")
        print("=" * 50 + "\n")
        
        # 9. Telegram 推送（保留）
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                ts = int(time.time())
                yaml_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml?t={ts}"
                txt_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt?t={ts}"
                repo_path = f"https://github.com/{REPO_NAME}/blob/main/"
                yaml_html_url = f"{repo_path}proxies.yaml"
                txt_html_url = f"{repo_path}subscription.txt"
                
                start_icon = "🚀"
                end_icon = "🎉"
                update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                msg = f"""{start_icon}<b>节点更新完成</b>{end_icon}

📊 <b>统计数据:</b>
• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总订阅：{len(all_urls)}
• Fork 来源：{len(fork_subs)}
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：<code>{len(unique_final)}</code> 个
• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)
• 最低延迟：{min_lat:.1f} ms
• 平均耗时：{tt:.1f} 秒
━━━━━━━━━━━━━━━━━━━━━━━

💾 <b>直链下载:</b>
YAML: <code>{yaml_raw_url}</code>
TXT: <code>{txt_raw_url}</code>

🌐 <b>网页查看:</b>
YAML: <a href="{yaml_html_url}">{yaml_html_url}</a>
TXT: <a href="{txt_html_url}">{txt_html_url}</a>

━━━━━━━━━━━━━━━━━━━━━━━

🌐 <b>支持协议:</b> VMess | VLESS | Trojan | SS | Hysteria2 | Hysteria | TUIC | WireGuard
👨‍💻 <b>作者:</b> 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶

<b>更新时间:</b> {update_time}"""
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                    timeout=10
                )
                print("✅ Telegram通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram推送失败：{e}")
        print("🎉 任务完成！")
        
    except Exception as e:
        print(f"\n❌ 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        clash.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
