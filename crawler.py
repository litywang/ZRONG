#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v28.1 - httpx高性能版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 28.1
优化：httpx连接池 + HTTP/2 + sources.yaml配置外置
核心原则：三层严格过滤 + 全量优质源 + 零语法错误 + 最佳稳定性
"""

import httpx
import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, signal, gzip, shutil, ssl, urllib.request, urllib.error, urllib.parse
requests.packages.urllib3.disable_warnings()

# ========== httpx 同步客户端（高性能连接池 + HTTP/2）==========
_http_client = None
def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=8.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            follow_redirects=True,
            verify=False
            # http2=True 需要 pip install httpx[http2]，Actions环境未安装，暂时禁用
        )
    return _http_client
import ipaddress
from cn_cidr_data import CN_IP_RANGES as _CN_IP_RANGES_RAW
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
from functools import lru_cache
import threading
import random
from datetime import datetime

# ==================== 配置区 ====================
# v28.3: 可用率修复 — 恢复gstatic.com，改MAX_FINAL_NODES控制TCP补充上限
_yaml_urls, _yaml_chans = [], []
_cfg_path = Path(__file__).parent / "sources.yaml"
if _cfg_path.exists():
    try:
        with open(_cfg_path, encoding="utf-8") as _f:
            _data = yaml.safe_load(_f) or {}
            _yaml_urls = _data.get("candidate_urls", [])
            _yaml_chans = _data.get("telegram_channels", [])
        print(f"[sources.yaml] loaded {_yaml_urls.__len__()} urls / {_yaml_chans.__len__()} tg channels")
    except Exception as _e:
        print(f"[sources.yaml] load failed, fallback to inline: {_e}")

_INLINE_CANDIDATE_URLS = [
    # ============ 内联回退列表（sources.yaml 不存在时使用） ============
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/kxswa/v2rayfree/main/v2ray",
    "https://raw.githubusercontent.com/llywhn/v2ray-subscribe/main/v2ray.txt",
    
    # ============ 国际稳定源 ============
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/trojan.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/trojan.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SS.json",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/VMESS.json",
    "https://raw.githubusercontent.com/baaif/Subconverter/master/sub/sub.ini",
    "https://shz.al/~WangCai",
    # ============ 额外高质量源 ============
    "https://raw.githubusercontent.com/fishball-2048/Subconverter/main/Sub/subconverter_subscribe.ini",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/SagerNet/sing-box/develop/Configs/proxies.json",
    "https://raw.githubusercontent.com/XTLS/Xray-core/master/examples/config.json",
    # v28.0: api.mrx.one 假token 已移除（由 sources.yaml 管理）
    # ============ 国内额外优质源 ============
    "https://raw.githubusercontent.com/adiwzx/freenode/main/v2ray.txt",
    "https://raw.githubusercontent.com/xingsin/test/main/list",
    "https://raw.githubusercontent.com/vxiaodong/zgq/main/sub",
    "https://raw.githubusercontent.com/changfengoss/pro/main/sub",
    "https://raw.githubusercontent.com/mymysub/V2raySubscribe/main/v2ray",
    "https://raw.githubusercontent.com/wxloststar/v2ray_sub/master/v2ray.txt",
    "https://raw.githubusercontent.com/aiboboxx/clashfree/main/clash",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yaml",
    "https://raw.githubusercontent.com/yonggekkk/yonggekkk.github.io/master/v2raylink.txt",
    "https://raw.githubusercontent.com/ONGKB/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/yeahwu/v2ray-wuzhi/main/v2ray",
    "https://raw.githubusercontent.com/v2ray-free/v2ray-free/master/v2ray",
    "https://raw.githubusercontent.com/ssrsub/ssr/master/v2ray",
    # ============ 国际额外源 ============
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/ss.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/ss.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/sub_merge.txt",
    # ============ v25新增国内友好源 ============
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mksshare/mksshare.github.io/main/sub",
    "https://raw.githubusercontent.com/yiiss/ProxyScrape/main/sub",
    "https://raw.githubusercontent.com/bulianglin/demo/main/sub",
    "https://raw.githubusercontent.com/chengaikun/V2RayNode/main/list",
    "https://raw.githubusercontent.com/xream/awesome-vpn/main/sub",
    "https://raw.githubusercontent.com/FreeFlyingMan/v2rayfree/main/v2ray",
    "https://raw.githubusercontent.com/NastyaFan/mihomo-clash/main/proxy",
    # ============ v25: 2026-04-20 最新大陆优质源（12个高频维护） ============
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml",
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt",
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/all.yaml",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/base64.txt",
    "https://raw.githubusercontent.com/a2470982985/getNode/main/clash.yaml",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://nodesfree.github.io/clashnode/clash.yaml",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/tuic.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
]
CANDIDATE_URLS = _yaml_urls if _yaml_urls else _INLINE_CANDIDATE_URLS


TELEGRAM_CHANNELS = (_yaml_chans or [
    "v2ray_free", "freev2rayng", "v2rayng_free", "sub_free",
    "vmessfree", "vlessfree", "trojanfree", "proxiesdaily",
    "clashnode", "freeclash", "freeproxy", "v2ray_share",
    "v2raydaily", "clashmeta", "mr_v2ray", "wxdy666",
    "dns68", "jriedian", "AlphaV2ray", "proxies_share",
    "freev2ray", "clashvpn", "v2rayngvpn", "freeVPNjd",
    "hysteria2_free", "SSR_V2Ray", "FreeNodeVPN", "proxy_node",
    "clash_daily", "SpeedNode",
])

HEADERS_POOL = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Accept-Encoding": "gzip, deflate, br", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Connection": "keep-alive"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15", "Accept": "*/*", "Accept-Encoding": "gzip, deflate, br", "Accept-Language": "zh-CN,zh;q=0.9", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1", "Accept": "*/*", "Accept-Encoding": "gzip, deflate, br", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"},
]
TIMEOUT = 8

MAX_FETCH_NODES = int(os.getenv("MAX_FETCH_NODES", 5000))     # v25: 扩大候选池（原3000）
MAX_TCP_TEST_NODES = int(os.getenv("MAX_TCP_TEST_NODES", 1200)) # v25: TCP翻倍（原600，匹配README 10s阈值）
MAX_PROXY_TEST_NODES = int(os.getenv("MAX_PROXY_TEST_NODES", 1200)) # v28.4: 全量进入Clash测速，不再浪费第一层合格节点
MAX_FINAL_NODES = int(os.getenv("MAX_FINAL_NODES", 150))       # v28.4: 150够用（TCP补充几乎无效，不凑数）
MAX_LATENCY = int(os.getenv("MAX_LATENCY", 10000))             # v25: TCP延迟放宽至10s（原5000，匹配README）
MIN_PROXY_SPEED = 0.0         # 取消速度限制，只看能否连通
MAX_PROXY_LATENCY = int(os.getenv("MAX_PROXY_LATENCY", 3000))  # v28.3: 保持3s阈值剔除极慢节点
TEST_URL = "http://www.gstatic.com/generate_204"  # v28.3: 恢复gstatic.com（国际出口才是代理核心指标）

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

MAX_WORKERS = 50
REQUESTS_PER_SECOND = 6.0     # v25: 提速（原3.0，Actions美国机房可承受）
MAX_RETRIES = 1

# 订阅源抓取并发（降速防封）
FETCH_WORKERS = 30

# ⚡ GitHub Fork 发现限制（最大耗时来源）
MAX_FORK_REPOS = int(os.getenv("MAX_FORK_REPOS", 60))  # v25: 提升fork发现量（原30）
MAX_FORK_URLS = 1500  # Fork URL总数上限

# ===== GitHub 多镜像池（v25: 扩展至8个，按速度排序，2026-04实测）=====
SUB_MIRRORS = [
    "https://gh.llkk.cc/",           # ~700ms  最快
    "https://ghproxy.net/",           # ~900ms  v25新增
    "https://gh-proxy.com/",          # ~1500ms
    "https://mirror.ghproxy.com/",    # ~1800ms v25新增
    "https://raw.iqiq.io/",           # ~2100ms
    "https://gh.api.99988866.xyz/",   # ~3000ms v25新增
    "https://ghps.cc/",               # ~3500ms v25新增
    "https://ghfast.top/",            # ~4000ms v25新增
]

# ===== CN IP 段过滤（精确 CIDR，来自 APNIC 官方数据，4219条）=====
# 由 cn_cidr_data.py 提供，替代原来的 /8 粒度（33条），大幅降低误杀率
CN_IP_RANGES = _CN_IP_RANGES_RAW

# ===== CN 域名黑名单正则 ======
CN_DOMAIN_BLACKLIST_RE = re.compile(
    r'\.(cn|cyou|top|xyz|cc|mojcn|cnmjin|qpon|'
    r'hk[\-_]?db|entry\.v\d+|internal\.(?:hk|tw|jp|sg)|bk[\-_]?hk\.node|'
    r'mobgslb\.tbcache|mobgslb\.tengine|tbcache\.com|tengine\.alicdn)\d*'
    r'|(?:^|[\.\-])(?:v\d+|node)\d*\.hk[\-_]?(?:db|internal)|'
    r'fastcoke|mojcn\.com|cnmjin\.net', re.I)

# ===== 非代理端口黑名单 ======
NON_PROXY_PORTS = {2377, 2376, 2375, 9200, 9300, 27017, 27018, 27019, 6379, 11211, 5432, 3306, 8086}

# ===== Reality 安全域名 ======
REALITY_SAFE_DOMAINS = {'reality.dev', 'v2fly.org', 'matsuri.biz', 'poi.moe',
                         '233boys.dev', 'ssrsub.com', 'justmysocks.net', 'flow.kkjiang.com'}

# ===== 协议优先级评分（v25: Reality大幅提权，Hysteria2/TUIC提权 - 大陆友好）=====
PROTOCOL_SCORE = {"vless": 10, "trojan": 9, "vmess": 8, "hysteria2": 9, "anytls": 7,
                  "hysteria": 6, "tuic": 7, "snell": 5, "http": 4, "socks5": 4, "ss": 3, "ssr": 1}

# ===== 端口质量评分 ======
HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}

# ===== 亚洲区域 ======
ASIA_REGIONS = ["HK", "TW", "JP", "SG", "KR", "TH", "VN", "MY", "ID"]  # v25: 扩展亚洲区域（原5个→9个，增加东南亚）

# ===== 并发配置 ======
MAX_CONCURRENT_FETCH = 3
MAX_CONCURRENT_TCP = 60

# ===== DNS 缓存 ======
_DNS_CACHE = {}
DNS_CACHE_TTL = 300

# ===== 历史稳定性记录 ======
_HISTORY_SCORES = {}

# ===== 网络基准 ======
_NETWORK_BASELINE = {"latency": 9999, "verified": False}

# ===== GitHub 直推配置 ======
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
GIST_ID = os.getenv("GIST_ID", "dc87627768298a4f6af8281cad97dfa3")

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

# ⭐ 新增：GitHub Fork 基础仓库（扩展版 - 更多优质源）
GITHUB_BASE_REPOS = [
    # ============ 国内优质源（优先） ============
    "ermaozi/get_subscribe",                 # 🥇 国内维护，更新快
    "peasoft/NoMoreWalls",                   # 🥈 国内热门，节点多
    "aiboboxx/v2rayfree",                    # 国内免费节点
    "freefq/free",                           # freefq 大神集合
    "mfuu/v2ray",                            # 国内聚合
    "kxswa/v2rayfree",                       # 国内源
    "llywhn/v2ray-subscribe",                # 国内更新快
    "baaif/Subconverter",                    # 转换工具
    
    # ============ 国际核心源 ============
    "wzdnzd/aggregator",                     # 聚合工具鼻祖
    "mahdibland/V2RayAggregator",            # V2RayAggregator 主力
    "PuddinCat/BestClash",                   # BestClash 高质量
    "roosterkid/openproxylist",              # 公开代理列表
    "anaer/Sub",                             # anaer 订阅汇总
    "MrMohebi/xray-proxy-grabber-telegram", # xray+Telegram 双驱动
    "jasonliu747/v2rayssr",                  # SSR+V2Ray混合
    "fslzhang/clash_config",                 # Clash 配置整理
    "xream/awesome-vpn",                     # VPN 资源汇总
    "FreeFlyingMan/v2rayfree",               # 中文社区热门
    "NastyaFan/mihomo-clash",                # Mihomo 专用
    "chengaikun/V2RayNode",                  # V2Ray 节点汇总
    "xiefei/V2RayConfig",                    # V2Ray 配置
    # ============ 新增优质源 ============
    "adiwzx/freenode",
    "xingsin/test",
    "vxiaodong/zgq",
    "changfengoss/pro",
    "mymysub/V2raySubscribe",
    "wxloststar/v2ray_sub",
    "yonggekkk/yonggekkk.github.io",
    "ONGKB/V2RayAggregator",
    "yeahwu/v2ray-wuzhi",
    "v2ray-free/v2ray-free",
    "ssrsub/ssr",
    # ============ v25新增优质源 ============
    "Pawdroid/Free-servers",               # v25: 国内常用免费订阅
    "mksshare/mksshare.github.io",         # v25: mks分享
    "yiiss/ProxyScrape",                   # v25: 代理爬虫
    "bulianglin/demo",                     # v25: 不良林demo
]


# ========== DNS 缓存（带TTL）==========requests.packages.urllib3.disable_warnings()

def resolve_domain(domain, timeout=3):
    if not domain or not isinstance(domain, str):
        return None
    now = time.time()
    if domain in _DNS_CACHE:
        ip, ts = _DNS_CACHE[domain]
        if now - ts < DNS_CACHE_TTL:
            return ip
    try:
        old_to = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        ip = socket.gethostbyname(domain)
        socket.setdefaulttimeout(old_to)
        _DNS_CACHE[domain] = (ip, now)
        return ip
    except Exception:
        _DNS_CACHE[domain] = (None, now)
        return None

# ========== CN 过滤工具 ==========
def is_pure_ip(s):
    if not s: return False
    s = s.strip()
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', s): return True
    if ':' in s and re.match(r'^[0-9a-fA-F:]+$', s): return True
    return False

def is_cn_proxy_domain(server):
    if not server or is_pure_ip(server): return False
    sl = server.lower()
    for safe in REALITY_SAFE_DOMAINS:
        if sl.endswith(safe) or sl == safe: return False
    if CN_DOMAIN_BLACKLIST_RE.search(server): return True
    return False

# ===== CN IP 快速查找表（预计算，用于4219条CIDR高效匹配）=====
_CN_IP_SET = set()  # /8 前缀 → 快速排除非CN
_CN_IP_NETS = []    # 精确CIDR列表

def _init_cn_lookup():
    """初始化CN IP查找表"""
    global _CN_IP_SET, _CN_IP_NETS
    for net in CN_IP_RANGES:
        _CN_IP_NETS.append(net)
        # 记录/8前缀用于快速排除
        _CN_IP_SET.add(net.network_address.packed[:1])

_init_cn_lookup()

def is_cn_proxy_ip(ip_str):
    """精确CN IP判断（4219条CIDR，先/8快排再精确匹配）"""
    if not ip_str: return None
    try:
        ip = ipaddress.ip_address(ip_str)
    except Exception: return None
    # 快速排除：如果/8前缀不在CN集合中，肯定不是CN
    if isinstance(ip, ipaddress.IPv4Address):
        first_octet = ip.packed[:1]
        if first_octet not in _CN_IP_SET:
            return False
    # 精确匹配
    for cidr in _CN_IP_NETS:
        if ip in cidr: return True
    return False

def check_node_reachability(server, timeout=3.0):
    if not server: return False, "空server"
    if is_pure_ip(server): return True, "纯IP"
    if is_cn_proxy_domain(server): return False, "CN域名"
    resolved_ip = resolve_domain(server, timeout=timeout)
    if resolved_ip and is_cn_proxy_ip(resolved_ip):
        return False, f"CN IP({resolved_ip})"
    return True, "通过"

def is_reality_friendly(p):
    t = p.get("type", "")
    if t == "vless" and p.get("reality-opts"): return True
    name = p.get("name", "").lower()
    return any(k in name for k in ["reality", "real-", "vlss", "lima", "fly", "ssrsub"])

def record_history(server_ip, port, latency):
    key = (server_ip, port)
    if key not in _HISTORY_SCORES: _HISTORY_SCORES[key] = []
    _HISTORY_SCORES[key].append(latency)
    if len(_HISTORY_SCORES[key]) > 10: _HISTORY_SCORES[key] = _HISTORY_SCORES[key][-10:]

def history_stability_score(server_ip, port):
    key = (server_ip, port)
    if key not in _HISTORY_SCORES or not _HISTORY_SCORES[key]: return 0
    scores = _HISTORY_SCORES[key]
    n = len(scores)
    success_rate = sum(1 for s in scores if s < 9999) / n
    avg = sum(scores) / n
    variance = sum((s - avg) ** 2 for s in scores) / n
    std = variance ** 0.5
    return max(0, int(success_rate * 500 - min(std * 2, 200)))

# ========== 网络基准检测 ==========
def check_network_baseline():
    global _NETWORK_BASELINE
    for target, port in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
        lat = _tcp_ping(target, port, timeout=2.0)
        if lat < 9999:
            _NETWORK_BASELINE["latency"] = min(_NETWORK_BASELINE["latency"], lat)
            _NETWORK_BASELINE["verified"] = True
    return _NETWORK_BASELINE["latency"]

# ========== TLS 握手检测 ==========
def tls_handshake_ok(host, port, timeout=5.0):
    if not host: return True, "ok"
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            with ctx.wrap_socket(sock, server_hostname=host): pass
            return True, "ok"
        except ssl.SSLError as e:
            err = str(e)
            if 'HANDSHAKE_FAILURE' in err or 'SSLV3' in err: return False, "handshake_fail"
            return True, "ok"
    except Exception: return True, "ok"

# ========== HTTP HEAD 检测 ==========
def http_head_check(host, port, timeout=3.0):
    if not host: return False
    try:
        import http.client
        if port in (443, 8443, 8080):
            try:
                conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl._create_unverified_context())
                conn.request("HEAD", "/", headers={"User-Agent": "curl/7.83.1"})
                resp = conn.getresponse()
                conn.close()
                return resp.status < 500
            except: pass
        if port in (80, 8080, 8888):
            try:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)
                conn.request("HEAD", "/", headers={"User-Agent": "curl/7.83.1"})
                resp = conn.getresponse()
                conn.close()
                return resp.status < 500
            except: pass
        return False
    except: return False

# ========== 丢包率检测 ==========
def packet_loss_check(host, port, timeout=2.0, attempts=3):
    if not host: return 0, attempts, False
    success = 0
    for _ in range(attempts):
        lat = _tcp_ping(host, port, timeout=timeout)
        if lat < 9999: success += 1
        time.sleep(0.15)
    return success, attempts, success >= 2

# ========== 二次 TCP 验证 ==========
def tcp_verify(host, port, timeout=1.5):
    if not host: return False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        s.close()
        return True
    except: return False

# ========== 内部 TCP Ping（兼容旧名 tcp_ping）==========
def _tcp_ping(host, port, timeout=2.5):
    if not host: return 9999
    try:
        start = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        s.close()
        return round((time.time() - start) * 1000, 1)
    except: return 9999


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
    session.headers.update(random.choice(HEADERS_POOL))
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
    
    # 每个 fork 的潜在路径（精简到3个最高频路径）
    potential_paths = [
        "proxies.yaml", 
        "subscription.txt",
        "v2ray.txt",
    ]
    
    # 并行获取所有 base repo 的 fork 列表
    def fetch_forks(base):
        # ⚡ 只取最新的 MAX_FORK_REPOS 个 fork
        url = f"https://api.github.com/repos/{base}/forks?per_page={MAX_FORK_REPOS}&sort=newest"
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
    
    # ⚡ 限制总URL数量，避免爬取时间过长
    all_urls_to_check = list(set(all_urls_to_check))
    if len(all_urls_to_check) > MAX_FORK_URLS:
        random.shuffle(all_urls_to_check)
        all_urls_to_check = all_urls_to_check[:MAX_FORK_URLS]
    
    print(f"   🔗 构建 {len(all_urls_to_check)} 个潜在 URL（跳过验证，直接拉取）...")
    
    subs = all_urls_to_check
    print(f"✅ GitHub Fork 共发现 {len(subs)} 个候选来源\n")
    return subs


def check_url_fast(u):
    """【v25】跳过 HEAD 验证，直接返回 True（零验证直拉策略）"""
    return True

def check_url(u):
    """【v25】跳过 HEAD 验证（零验证直拉策略，统一入口）"""
    return True


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


def parse_ssr(node):
    """解析 SSR:// 链接（v25: 修复 split 逻辑，兼容 IPv6 和含冒号密码）"""
    try:
        if not node.startswith("ssr://"): return None
        raw = base64.b64decode(node[6:] + "=" * (4 - len(node[6:]) % 4)).decode("utf-8", errors="ignore")
        # SSR 格式: server:port:protocol:method:obfs:base64pass/?obfsparam=xxx&remark=xxx
        parts = raw.split("/?")
        main = parts[0]
        params_str = parts[1] if len(parts) > 1 else ""
        
        # 修复: 用 rsplit 从右边拆分，避免 server 含 IPv6 冒号时错位
        # 格式固定为 6 段: server:port:protocol:method:obfs:base64pass
        segments = main.split(":")
        if len(segments) < 6: return None
        b64pass = segments[-1]
        obfs = segments[-2]
        method = segments[-3]
        protocol = segments[-4]
        port_str = segments[-5]
        server = ":".join(segments[:-5])  # 剩余部分为 server（兼容 IPv6）
        
        try:
            port = int(port_str)
        except ValueError:
            return None
        password = base64.b64decode(b64pass + "=" * (4 - len(b64pass) % 4)).decode("utf-8", errors="ignore")
        
        # 从参数提取备注名称
        name = ""
        if params_str:
            params = parse_qs(params_str)
            remark_b64 = params.get("remarks", [""])[0]
            if remark_b64:
                name = base64.b64decode(remark_b64 + "=" * (4 - len(remark_b64) % 4)).decode("utf-8", errors="ignore")
        
        if not name:
            uid = generate_unique_id({'server': server, 'port': port})
            name = f"SR-{uid}"
        
        # 提取 obfsparam 和 protoparam
        obfs_param = ""
        proto_param = ""
        if params_str:
            params = parse_qs(params_str)
            obfs_param_b64 = params.get("obfsparam", [""])[0]
            if obfs_param_b64:
                obfs_param = base64.b64decode(obfs_param_b64 + "=" * (4 - len(obfs_param_b64) % 4)).decode("utf-8", errors="ignore")
            proto_param_b64 = params.get("protoparam", [""])[0]
            if proto_param_b64:
                proto_param = base64.b64decode(proto_param_b64 + "=" * (4 - len(proto_param_b64) % 4)).decode("utf-8", errors="ignore")
        
        proxy = {
            "name": name, "type": "ssr", "server": server, "port": port,
            "protocol": protocol, "method": method, "obfs": obfs,
            "password": password, "udp": True,
        }
        if obfs_param: proxy["obfs-param"] = obfs_param
        if proto_param: proxy["protocol-param"] = proto_param
        return proxy
    except: return None


def parse_http_proxy(node):
    """解析 http:// / https:// 代理链接"""
    try:
        if not node.startswith("http://") and not node.startswith("https://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        # 格式: http://user:pass@server:port#name 或 http://server:port
        username = unquote(p_url.username or "")
        password = unquote(p_url.password or "")
        name = p_url.fragment if p_url.fragment else f"HT-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 80)})}"
        ptype = "https" if node.startswith("https://") else "http"
        proxy = {
            "name": name, "type": ptype, "server": p_url.hostname,
            "port": int(p_url.port or 443 if ptype == "https" else 80),
        }
        if username: proxy["username"] = username
        if password: proxy["password"] = password
        return proxy
    except: return None


def parse_socks(node):
    """解析 socks5:// 链接"""
    try:
        if not node.startswith("socks5://") and not node.startswith("socks4://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        username = unquote(p_url.username or "")
        password = unquote(p_url.password or "")
        name = p_url.fragment if p_url.fragment else f"SK-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 1080)})}"
        ptype = "socks5" if node.startswith("socks5://") else "socks4"
        proxy = {
            "name": name, "type": ptype, "server": p_url.hostname,
            "port": int(p_url.port or 1080),
        }
        if username: proxy["username"] = username
        if password: proxy["password"] = password
        return proxy
    except: return None


def parse_anytls(node):
    """解析 anytls:// 链接 (AnyTLS协议)"""
    try:
        if not node.startswith("anytls://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        name = p_url.fragment if p_url.fragment else "AT-" + generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443)})
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        proxy = {
            "name": name, "type": "anytls", "server": p_url.hostname,
            "port": int(p_url.port or 443), "udp": True, "skip-cert-verify": True,
        }
        sni = gp("sni")
        if sni: proxy["sni"] = sni
        elif p_url.hostname: proxy["sni"] = p_url.hostname
        fp = gp("fp")
        if fp: proxy["client-fingerprint"] = fp
        return proxy if proxy["server"] else None
    except: return None


def parse_snell(node):
    """解析 snell:// 链接"""
    try:
        if not node.startswith("snell://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        name = p_url.fragment if p_url.fragment else f"SN-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443)})}"
        proxy = {
            "name": name, "type": "snell", "server": p_url.hostname,
            "port": int(p_url.port or 443), "psk": pwd, "udp": True
        }
        obfs = gp("obfs")
        if obfs: proxy["obfs-opts"] = {"mode": obfs}
        version = gp("version")
        if version: proxy["version"] = int(version)
        return proxy if proxy["server"] else None
    except: return None


def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"): return None
    if node.startswith("vmess://"): return parse_vmess(node)
    elif node.startswith("vless://"): return parse_vless(node)
    elif node.startswith("trojan://"): return parse_trojan(node)
    elif node.startswith("ss://"): return parse_ss(node)
    elif node.startswith("ssr://"): return parse_ssr(node)
    elif node.startswith("hysteria2://") or node.startswith("hy2://"): return parse_hysteria2(node)
    elif node.startswith("hysteria://"): return parse_hysteria(node)
    elif node.startswith("tuic://"): return parse_tuic(node)
    elif node.startswith("snell://"): return parse_snell(node)
    elif node.startswith("socks5://") or node.startswith("socks4://"): return parse_socks(node)
    elif node.startswith("http://") or node.startswith("https://"): return parse_http_proxy(node)
    elif node.startswith("anytls://"): return parse_anytls(node)
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
            # 只认 Mihomo/Clash 支持的协议（扩展版）
            if ptype not in ("vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2", "tuic",
                             "wireguard", "shadowtls", "snell", "http", "socks5", "anytls"):
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
def get_region(name, server=None, sni=None):
    """根据节点名称检测区域 - v27: 修复emoji flag识别 + 域名fallback + sni支持
    server: 可选，节点server字段，用于从域名后缀反推地区（如 .kr/.sg/.vn）
    sni: 可选，节点sni字段，用于从域名后缀反推地区（优先级高于server）
    """
    nl = name.lower()
    # v25 FIX: Regional Indicator emoji flag (如🇭🇰) 由两个U+1F1Ex字符组成
    # 当后接数字时(🇭🇰1)，re.split无法拆开，导致二字母匹配全部失败
    # 修复：先去除Regional Indicator字符对，再用普通分隔符分词
    nl_no_flag = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', nl)
    tokens = set(re.split(r'[\s\-_|,.:;/()（）【】\[\]{}]+', nl_no_flag))

    # 辅助函数：区分真正的二字母ASCII代码 vs emoji/多字符
    def match(keywords):
        for k in keywords:
            if len(k) == 2 and k.isalpha() and k.isascii():
                if k in tokens:
                    return True
            else:
                if k in nl:
                    return True
        return False
    
    # 香港检测
    if match(["hk", "hongkong", "港", "hong kong", "🇭🇰", "香港", "深港", "沪港", "京港"]):
        return "🇭🇰", "HK"
    # 台湾检测
    elif match(["tw", "taiwan", "台", "🇹🇼", "台湾", "臺灣", "台北", "台中", "新北", "taipei"]):
        return "🇹🇼", "TW"
    # 日本检测
    elif match(["jp", "japan", "日", "🇯🇵", "日本", "东京", "大阪", "tokyo", "osaka", "川日", "泉日", "埼玉"]):
        return "🇯🇵", "JP"
    # 新加坡检测
    elif match(["sg", "singapore", "新", "🇸🇬", "新加坡", "狮城", "沪新", "京新", "深新"]):
        return "🇸🇬", "SG"
    # 韩国检测
    elif match(["kr", "korea", "韩", "🇰🇷", "韩国", "韓", "首尔", "春川", "seoul"]):
        return "🇰🇷", "KR"
    # 美国检测
    elif match(["us", "usa", "美", "🇺🇸", "美国", "美利坚", "洛杉矶", "硅谷", "纽约", "united states", "america", "los angeles", "new york"]):
        return "🇺🇸", "US"
    # 英国检测
    elif match(["uk", "britain", "英", "🇬🇧", "英国", "伦敦", "united kingdom", "london", "england"]):
        return "🇬🇧", "UK"
    # 德国检测
    elif match(["de", "germany", "德", "🇩🇪", "德国", "法兰克福", "frankfurt", "berlin"]):
        return "🇩🇪", "DE"
    # 法国检测
    elif match(["fr", "france", "法", "🇫🇷", "法国", "巴黎", "paris"]):
        return "🇫🇷", "FR"
    # 加拿大检测
    elif match(["ca", "canada", "加", "🇨🇦", "加拿大", "渥太华", "多伦多", "toronto", "vancouver"]):
        return "🇨🇦", "CA"
    # 澳大利亚检测
    elif match(["au", "australia", "澳", "🇦🇺", "澳大利亚", "澳洲", "悉尼", "sydney", "melbourne"]):
        return "🇦🇺", "AU"
    # 荷兰检测
    elif match(["nl", "netherlands", "荷", "🇳🇱", "荷兰", "阿姆斯特丹", "amsterdam"]):
        return "🇳🇱", "NL"
    # 俄罗斯检测
    elif match(["ru", "russia", "俄", "🇷🇺", "俄罗斯", "莫斯科", "moscow"]):
        return "🇷🇺", "RU"
    # 印度检测（v25: 修复 "in" 误匹配，改用词边界检查）
    elif match(["india", "印", "🇮🇳", "印度", "孟买", "mumbai", "delhi"]) or re.search(r'\bin\b', nl):
        return "🇮🇳", "IN"
    # 巴西检测
    elif match(["br", "brazil", "巴", "🇧🇷", "巴西", "圣保罗", "sao paulo"]):
        return "🇧🇷", "BR"
    # 阿根廷检测
    elif match(["ar", "argentina", "阿", "🇦🇷", "阿根廷", "buenos aires"]):
        return "🇦🇷", "AR"
    # 泰国检测
    elif match(["th", "thailand", "泰", "🇹🇭", "泰国", "曼谷", "bangkok"]):
        return "🇹🇭", "TH"
    # 越南检测
    elif match(["vn", "vietnam", "越", "🇻🇳", "越南", "胡志明", "hanoi"]):
        return "🇻🇳", "VN"
    # 马来西亚检测
    elif match(["my", "malaysia", "马", "🇲🇾", "马来西亚", "吉隆坡", "kuala lumpur"]):
        return "🇲🇾", "MY"
    # 菲律宾检测
    elif match(["ph", "philippines", "菲", "🇵🇭", "菲律宾", "马尼拉", "manila"]):
        return "🇵🇭", "PH"
    # 印尼检测
    elif match(["id", "indonesia", "印尼", "🇮🇩", "雅加达", "jakarta"]):
        return "🇮🇩", "ID"
    # 墨西哥检测
    elif match(["mx", "mexico", "墨", "🇲🇽", "墨西哥"]):
        return "🇲🇽", "MX"
    # 意大利检测
    elif match(["it", "italy", "意", "🇮🇹", "意大利", "米兰", "罗马", "milan", "rome"]):
        return "🇮🇹", "IT"
    # 西班牙检测
    elif match(["es", "spain", "西", "🇪🇸", "西班牙", "马德里", "madrid"]):
        return "🇪🇸", "ES"
    # 瑞士检测
    elif match(["ch", "switzerland", "瑞", "🇨🇭", "瑞士", "苏黎世", "zurich"]):
        return "🇨🇭", "CH"
    # 奥地利检测
    elif match(["at", "austria", "奥", "🇦🇹", "奥地利", "维也纳", "vienna"]):
        return "🇦🇹", "AT"
    # 瑞典检测
    elif match(["se", "sweden", "瑞典", "🇸🇪", "斯德哥尔摩", "stockholm"]):
        return "🇸🇪", "SE"
    # 波兰检测
    elif match(["pl", "poland", "波", "🇵🇱", "波兰", "华沙", "warsaw"]):
        return "🇵🇱", "PL"
    # 土耳其检测
    elif match(["tr", "turkey", "土", "🇹🇷", "土耳其", "伊斯坦布尔", "istanbul"]):
        return "🇹🇷", "TR"
    # 南非检测
    elif match(["za", "south africa", "南非", "🇿🇦", "约翰内斯堡", "johannesburg"]):
        return "🇿🇦", "ZA"
    # 阿联酋检测
    elif match(["ae", "uae", "迪", "🇦🇪", "阿联酋", "迪拜", "dubai", "abu dhabi"]):
        return "🇦🇪", "AE"
    # 以色列检测
    elif match(["il", "israel", "以", "🇮🇱", "以色列", "特拉维夫", "tel aviv"]):
        return "🇮🇱", "IL"
    # 爱尔兰检测
    elif match(["ie", "ireland", "爱尔兰", "🇮🇪", "都柏林", "dublin"]):
        return "🇮🇪", "IE"
    # 葡萄牙检测
    elif match(["pt", "portugal", "葡", "🇵🇹", "葡萄牙", "里斯本", "lisbon"]):
        return "🇵🇹", "PT"
    # 捷克检测
    elif match(["cz", "czech", "捷", "🇨🇿", "捷克", "布拉格", "prague"]):
        return "🇨🇿", "CZ"
    # 罗马尼亚检测
    elif match(["ro", "romania", "罗", "🇷🇴", "罗马尼亚", "布加勒斯特", "bucharest"]):
        return "🇷🇴", "RO"
    # 匈牙利检测
    elif match(["hu", "hungary", "匈", "🇭🇺", "匈牙利", "布达佩斯", "budapest"]):
        return "🇭🇺", "HU"
    # 希腊检测
    elif match(["gr", "greece", "希", "🇬🇷", "希腊", "雅典", "athens"]):
        return "🇬🇷", "GR"
    # 芬兰检测
    elif match(["fi", "finland", "芬", "🇫🇮", "芬兰", "赫尔辛基", "helsinki"]):
        return "🇫🇮", "FI"
    # 丹麦检测
    elif match(["dk", "denmark", "丹", "🇩🇰", "丹麦", "哥本哈根", "copenhagen"]):
        return "🇩🇰", "DK"
    # 挪威检测
    elif match(["no", "norway", "挪", "🇳🇴", "挪威", "奥斯陆", "oslo"]):
        return "🇳🇴", "NO"
    # 比利时检测
    elif match(["be", "belgium", "比", "🇧🇪", "比利时", "布鲁塞尔", "brussels"]):
        return "🇧🇪", "BE"
    # 新西兰检测
    elif match(["nz", "new zealand", "新西兰", "🇳🇿", "奥克兰", "auckland"]):
        return "🇳🇿", "NZ"
    # 智利检测
    elif match(["cl", "chile", "智", "🇨🇱", "智利", "圣地亚哥", "santiago"]):
        return "🇨🇱", "CL"
    # 哥伦比亚检测
    elif match(["co", "colombia", "哥", "🇨🇴", "哥伦比亚", "波哥大", "bogota"]):
        return "🇨🇴", "CO"
    # 秘鲁检测
    elif match(["pe", "peru", "秘", "🇵🇪", "秘鲁", "利马", "lima"]):
        return "🇵🇪", "PE"
    # 乌克兰检测
    elif match(["ua", "ukraine", "乌", "🇺🇦", "乌克兰", "基辅", "kiev", "kyiv"]):
        return "🇺🇦", "UA"
    # 哈萨克斯坦检测
    elif match(["kz", "kazakhstan", "哈", "🇰🇿", "哈萨克斯坦", "阿拉木图", "almaty"]):
        return "🇰🇿", "KZ"
    
    # 默认处理：无法识别地区，尝试基于 server 推测，否则给个合理的默认
    # 尝试匹配常见的通用模式
    if match(["private", "vpn", "proxy", "network"]):
        return "🌐", "NET"  # 网络通用
    
    # v27 FIX: 移除数字检查限制，对所有节点都尝试从域名后缀反推
    # 优先检查 sni（通常是CDN域名，含更多信息），再检查 server
    hosts_to_check = []
    if sni:
        hosts_to_check.append(sni.lower())
    if server:
        hosts_to_check.append(server.lower())
    
    for srv in hosts_to_check:
        # 从右向左取最后两个部分做模糊匹配
        parts = srv.split(".")
        for i in range(max(0, len(parts)-2), len(parts)):
            seg = ".".join(parts[i:])
            # TLD/常见域名后缀 → 国家/地区
            if seg.endswith(".kr") or "kr." in srv:
                return "🇰🇷", "KR"
            if seg.endswith(".sg") or ".com.sg" in srv or ".net.sg" in srv:
                return "🇸🇬", "SG"
            if seg.endswith(".vn") or "vn." in srv:
                return "🇻🇳", "VN"
            if seg.endswith(".th") or "th." in srv:
                return "🇹🇭", "TH"
            if seg.endswith(".my") or "my." in srv:
                return "🇲🇾", "MY"
            if seg.endswith(".id") or ".co.id" in srv or ".or.id" in srv:
                return "🇮🇩", "ID"
            if seg.endswith(".ph") or ".com.ph" in srv:
                return "🇵🇭", "PH"
            if seg.endswith(".jp") or ".co.jp" in srv or ".ne.jp" in srv:
                return "🇯🇵", "JP"
            if seg.endswith(".hk") or ".com.hk" in srv or ".net.hk" in srv:
                return "🇭🇰", "HK"
            if seg.endswith(".tw") or ".com.tw" in srv or ".net.tw" in srv:
                return "🇹🇼", "TW"
            if seg.endswith(".au") or ".com.au" in srv:
                return "🇦🇺", "AU"
            if srv.endswith(".uk") or srv.endswith(".co.uk"):
                return "🇬🇧", "UK"
            if seg.endswith(".de") or ".de." in srv:
                return "🇩🇪", "DE"
            if seg.endswith(".fr") or ".fr." in srv:
                return "🇫🇷", "FR"
            if seg.endswith(".nl") or ".nl." in srv:
                return "🇳🇱", "NL"
            if seg.endswith(".ru") or ".ru." in srv:
                return "🇷🇺", "RU"
            if seg.endswith(".us") or ".us." in srv:
                return "🇺🇸", "US"
            if seg.endswith(".br") or ".com.br" in srv:
                return "🇧🇷", "BR"
            if seg.endswith(".ca") or ".ca." in srv:
                return "🇨🇦", "CA"
            if seg.endswith(".in") or ".co.in" in srv or ".net.in" in srv:
                return "🇮🇳", "IN"
            if seg.endswith(".it") or ".it." in srv:
                return "🇮🇹", "IT"
            if seg.endswith(".es") or ".es." in srv:
                return "🇪🇸", "ES"
            if seg.endswith(".tr") or ".com.tr" in srv:
                return "🇹🇷", "TR"
            if seg.endswith(".pl") or ".pl." in srv:
                return "🇵🇱", "PL"
            if seg.endswith(".cz") or ".cz." in srv:
                return "🇨🇿", "CZ"
            if seg.endswith(".ar") or ".com.ar" in srv:
                return "🇦🇷", "AR"
            if srv.endswith(".cl") or srv.endswith(".co.cl"):
                return "🇨🇱", "CL"
            if seg.endswith(".mx") or ".mx." in srv:
                return "🇲🇽", "MX"
            if seg.endswith(".ae") or ".ae." in srv:
                return "🇦🇪", "AE"
            if seg.endswith(".il") or ".il." in srv:
                return "🇮🇱", "IL"
            if seg.endswith(".ie") or ".ie." in srv:
                return "🇮🇪", "IE"
            if seg.endswith(".nz") or ".nz." in srv:
                return "🇳🇿", "NZ"
            if seg.endswith(".ch") or ".ch." in srv:
                return "🇨🇭", "CH"
            if seg.endswith(".at") or ".at." in srv:
                return "🇦🇹", "AT"
            if seg.endswith(".se") or ".se." in srv:
                return "🇸🇪", "SE"
            if seg.endswith(".pt") or ".pt." in srv:
                return "🇵🇹", "PT"
            if seg.endswith(".ro") or ".ro." in srv:
                return "🇷🇴", "RO"
            if seg.endswith(".hu") or ".hu." in srv:
                return "🇭🇺", "HU"
            if seg.endswith(".fi") or ".fi." in srv:
                return "🇫🇮", "FI"
            if seg.endswith(".dk") or ".dk." in srv:
                return "🇩🇰", "DK"
            if seg.endswith(".no") or ".no." in srv:
                return "🇳🇴", "NO"
            if seg.endswith(".be") or ".be." in srv:
                return "🇧🇪", "BE"
            if seg.endswith(".za") or ".za." in srv:
                return "🇿🇦", "ZA"
            if seg.endswith(".kz") or ".kz." in srv:
                return "🇰🇿", "KZ"
            if seg.endswith(".ua") or ".ua." in srv:
                return "🇺🇦", "UA"
            if seg.endswith(".bg") or ".bg." in srv:
                return "🇧🇬", "BG"
            if seg.endswith(".gr") or ".gr." in srv:
                return "🇬🇷", "GR"
            # v27: 新增更多国家后缀
            if seg.endswith(".ir") or ".ir." in srv:
                return "🇮🇷", "IR"
            if seg.endswith(".pk") or ".pk." in srv:
                return "🇵🇰", "PK"
            if seg.endswith(".bd") or ".bd." in srv:
                return "🇧🇩", "BD"
            if seg.endswith(".ng") or ".ng." in srv:
                return "🇳🇬", "NG"
            if seg.endswith(".eg") or ".eg." in srv:
                return "🇪🇬", "EG"
            if seg.endswith(".ke") or ".ke." in srv:
                return "🇰🇪", "KE"
            if srv.endswith(".co") or srv.endswith(".com.co"):
                return "🇨🇴", "CO"
            if seg.endswith(".pe") or ".pe." in srv:
                return "🇵🇪", "PE"
            if seg.endswith(".ve") or ".ve." in srv:
                return "🇻🇪", "VE"
            if seg.endswith(".ec") or ".ec." in srv:
                return "🇪🇨", "EC"
    
    return "🌐", "NET"


def is_asia(p):
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    # v25: 二字母代码改用词边界匹配，防止 "in"/"id"/"my" 等子串误匹配
    tokens = set(re.split(r'[\s\-_|,.:;/()（）【】\[\]{}]+', t))
    asia_2letter = {"hk", "tw", "jp", "sg", "kr", "th", "vn", "my", "id"}
    asia_long = ["hongkong", "港", "taiwan", "台", "japan", "日",
                 "singapore", "新加坡", "新", "korea", "韩", "asia", "hkt",
                 "thailand", "泰", "vietnam", "越", "malaysia", "马",
                 "indonesia", "印"]
    # 二字母精确匹配token
    if tokens & asia_2letter:
        return True
    # 长关键词子串匹配
    return any(k in t for k in asia_long)


def is_china_mainland(p):
    """判断是否为内地直连节点（一般不可用，用于过滤）"""
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    tokens = set(re.split(r'[\s\-_|,.:;/()（）【】\[\]{}]+', t))
    cn_2letter = {"cn"}
    cn_long = ["china", "中国", "国内", "直连", "direct",
               "北京", "上海", "广州", "深圳", "成都", "杭州"]
    if tokens & cn_2letter:
        return True
    return any(k in t for k in cn_long)


def filter_quality(p):
    """【v24 大陆友好版】节点质量过滤，含 CN IP/域名黑名单 + 非代理端口过滤"""
    name = p.get("name", "").lower()

    # 仅排除明显无效的
    exclude_keywords = ["过期", "到期", "失效", "expire", "expired", "广告", "推广", "官网", "购买"]
    for kw in exclude_keywords:
        if kw in name:
            return False

    # 排除内地直连
    if is_china_mainland(p):
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

    # 服务器检查
    server = p.get("server", "")
    if not server or len(server) < 4:
        return False

    # CN IP 段过滤（v24）：域名 DNS 解析 + IP 段判断
    if is_pure_ip(server):
        if is_cn_proxy_ip(server):
            return False
    else:
        reach, _ = check_node_reachability(server, timeout=2.0)
        if not reach:
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
    """【v28.1 httpx优化】GitHub URL 多镜像池遍历 + HTTP/2"""
    limiter.wait(url)
    client = get_http_client()
    headers = random.choice(HEADERS_POOL)
    is_github = "github" in url.lower() or "raw.githubusercontent" in url

    # 非GitHub URL：直连 + 重试
    if not is_github:
        for attempt in range(2):
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text.strip()
                elif resp.status_code in (403, 429):
                    time.sleep(3)
                    continue
            except Exception:
                time.sleep(1)
        return ""

    # GitHub: 镜像池 + 原始URL兜底
    all_urls = []
    for mirror in SUB_MIRRORS:
        if mirror:
            mirror_host = mirror.rstrip("/").replace("https://", "")
            all_urls.append(url.replace("raw.githubusercontent.com", mirror_host))
    all_urls.append(url)

    for try_url in all_urls:
        for attempt in range(2):
            try:
                resp = client.get(try_url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text.strip()
                    if text.startswith("<!") or text.startswith("<html"):
                        continue
                    if len(text) > 50:
                        return text
                elif resp.status_code in (403, 429, 503):
                    time.sleep(random.uniform(2.0, 5.0))
                    continue
            except Exception:
                time.sleep(random.uniform(0.5, 1.5))
    return ""


def tcp_ping(host, port, to=1.5):
    """【v24】TCP Ping，支持丢包检测历史记录"""
    if not host: return 9999.0
    try:
        st = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(to)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        s.close()
        lat = round((time.time() - st) * 1000, 1)
        record_history(host, port, lat)
        return lat
    except:
        record_history(host, port, 9999)
        return 9999.0
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
            resp = requests.get(TEST_URL, proxies=px, timeout=5, allow_redirects=False)  # ⚡ 5s超时
            lat = (time.time() - start) * 1000
            if resp.status_code in [200, 204, 301, 302]:
                # ⚡ 跳过测速，只测连通性，大幅节省时间
                # v28.2: 支持 baidu.com(200) 和 gstatic.com(204) 两种响应格式
                result = {"success": True, "latency": round(lat, 1), "speed": 0.0, "error": ""}
            else:
                result["error"] = f"Status:{resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:60]
        return result


# ⭐ 节点命名（优化版：无后缀）
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝'}

    def __init__(self):
        self.counters = {}

    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat, speed=None, tcp=False, server=None, sni=None):
        """【v27】简短命名，含区域emoji + 编号 + 哥特体后缀
        flag: 原始节点名称（或emoji字符串）
        server: 节点server字段，用于域名fallback
        sni: 节点sni字段，用于域名fallback（优先级高于server）
        """
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        # v26: 添加哥特体后缀 -𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
        return f"{code}{num}-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"


# ⭐ 协议链接转换（扩展版）
def format_proxy_to_link(p):
    """将代理对象转换为协议链接"""
    try:
        ptype = p.get("type", "")
        name_enc = urllib.parse.quote(p.get("name", "node"), safe="")
        
        if ptype == "vmess":
            data = {"v": "2", "ps": p["name"], "add": p["server"], "port": p["port"], 
                    "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"), 
                    "type": "none", "host": p.get("sni", ""), "path": p.get("ws-opts", {}).get("path", ""), 
                    "tls": "tls" if p.get("tls") else ""}
            return "vmess://" + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()
        
        elif ptype == "trojan":
            pwd_enc = urllib.parse.quote(p.get('password', ''), safe='')
            sni = p.get('sni', p.get('server', ''))
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?sni={sni}#{name_enc}"
        
        elif ptype == "vless":
            uuid = p.get('uuid', '')
            security = "tls" if p.get('tls') or p.get('reality') else "none"
            flow = p.get('flow', '')
            params = f"type={p.get('network', 'tcp')}&security={security}"
            if flow: params += f"&flow={flow}"
            if p.get('sni'): params += f"&sni={p['sni']}"
            return f"vless://{uuid}@{p['server']}:{p['port']}?{params}#{name_enc}"
        
        elif ptype == "ss":
            auth = f"{p['cipher']}:{p['password']}"
            auth_enc = base64.b64encode(auth.encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{name_enc}"
        
        elif ptype == "ssr":
            # SSR 格式较复杂，输出为 YAML 格式注释
            return f"# {p['name']} (SSR)"
        
        elif ptype == "hysteria2":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            params = f"insecure=1"
            if p.get('sni'): params += f"&sni={p['sni']}"
            return f"hysteria2://{pwd}@{p['server']}:{p['port']}?{params}#{name_enc}"
        
        elif ptype == "hysteria":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            return f"hysteria://{pwd}@{p['server']}:{p['port']}#{name_enc}"
        
        elif ptype == "tuic":
            uuid = p.get('uuid', '')
            params = "congestion_control=cubic"
            if p.get('sni'): params += f"&sni={p['sni']}"
            return f"tuic://{uuid}:{uuid}@{p['server']}:{p['port']}?{params}#{name_enc}"
        
        elif ptype == "snell":
            pwd = urllib.parse.quote(p.get('psk', ''), safe='')
            return f"snell://{pwd}@{p['server']}:{p['port']}#{name_enc}"
        
        elif ptype == "socks5":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            return f"socks5://{auth}{p['server']}:{p['port']}#{name_enc}"
        
        elif ptype == "http":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            scheme = "https" if p.get('tls') else "http"
            return f"{scheme}://{auth}{p['server']}:{p['port']}#{name_enc}"
        
        return f"# {p['name']}"
    except:
        return f"# {p.get('name', 'unknown')}"


# ⭐ 主程序（集成 Fork 发现）
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 50)
    print("🚀 聚合订阅爬虫 v25.0 - 大陆友好全面优化版")
    print("作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 25.0")
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
                server = proxy.get("server", "")
                port = proxy.get("port", 0)
                if not server or not port: return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                host = server.split(":")[0] if ":" in server else server
                lat = tcp_ping(host, port)
                if lat >= 9999: return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # 丢包率检测（v24）
                ok, total, usable = packet_loss_check(host, port, timeout=2.0, attempts=3)
                if not usable: return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # TLS 握手检测（v24）
                if proxy.get("tls") == True or port == 443:
                    tls_ok, _ = tls_handshake_ok(host, port)
                    if not tls_ok: return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                return {"proxy": proxy, "latency": float(lat), "is_asia": is_asia(proxy),
                        "hist_score": history_stability_score(host, port)}
            except Exception:
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
        # 提高并发数用于 TCP 测试（大幅提高）
        tcp_workers = 200  # 100 → 200
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
        nres.sort(key=lambda x: (
            -x["is_asia"],
            -(1 if is_reality_friendly(x["proxy"]) else 0),  # v25: Reality节点优先
            -PROTOCOL_SCORE.get(x["proxy"].get("type", ""), 0) / 10.0,  # v25: 协议评分加权
            x["latency"]
        ))
        asia_count = sum(1 for n in nres if n["is_asia"])
        print(f"✅ 第一层合格：{len(nres)} 个（亚洲：{asia_count}，占比：{asia_count*100//max(len(nres),1)}%）\n")
        
        # 7. 真实测速 + TCP 保底（保留）
        print("🚀 真实代理测速...\n")
        final = []
        tested = set()
        
        if len(nres) > 0:
            tprox = [n["proxy"] for n in nres[:MAX_PROXY_TEST_NODES]]
            if clash.create_config(tprox) and clash.start():
                proxy_ok = True
                print("📊 测速中...\n")
                tprox_list = nres[:MAX_PROXY_TEST_NODES]
                
                # ⚡ 并发测试代理（原来是串行，改为并发大幅提速）
                def test_one(item):
                    p = item["proxy"]
                    r = clash.test_proxy(p["name"])
                    return item, p, r
                
                with ThreadPoolExecutor(max_workers=20) as tex:
                    test_futures = {tex.submit(test_one, item): item for item in tprox_list}
                    done_count = 0
                    for future in as_completed(test_futures):
                        try:
                            item, p, r = future.result(timeout=8)
                            done_count += 1
                            k = f"{p['server']}:{p['port']}"
                            if r["success"] and r["latency"] < MAX_PROXY_LATENCY:
                                srv = p.get("server", "")
                                sni_val = p.get("sni", "") or p.get("servername", "")
                                # v27 FIX: 也取 ws-opts 里的 Host（WS 域名通常比 server 更精确）
                                ws_opts = p.get("ws-opts", {})
                                ws_host = (
                                    ws_opts.get("headers", {}).get("Host", "")
                                    if isinstance(ws_opts, dict)
                                    else ""
                                )
                                if ws_host:
                                    sni_val = ws_host
                                fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                                p["name"] = namer.generate(fl, int(r["latency"]), r["speed"], tcp=False, server=srv, sni=sni_val)
                                final.append(p)
                                tested.add(k)
                                print(f"   ✅ {p['name']}")
                            if len(final) >= MAX_FINAL_NODES:
                                break
                            if done_count % 10 == 0:
                                print(f"   进度：{done_count}/{len(tprox_list)} | 合格：{len(final)}")
                        except: pass
                clash.stop()
                
                # v28.3: 改用 MAX_FINAL_NODES，不再硬编码180
                if len(final) < MAX_FINAL_NODES:
                    print(f"\n⚠️ 测速合格 {len(final)} 个/{MAX_FINAL_NODES} 目标，使用 TCP 补充...\n")
                    for item in nres:
                        if len(final) >= MAX_FINAL_NODES: break
                        p = item["proxy"]
                        k = f"{p['server']}:{p['port']}"
                        if k in tested: continue
                        # v26: 严格限制TCP补充条件
                        if item["is_asia"] and item["latency"] < 400:  # v26: 800→400
                            # CN IP 过滤
                            server = p.get("server", "")
                            host = server.split(":")[0] if ":" in server else server
                            reach, _ = check_node_reachability(host, timeout=1.5)
                            if not reach: continue
                            srv = p.get("server", "")
                            sni_val = p.get("sni", "") or p.get("servername", "")
                            ws_opts = p.get("ws-opts", {})
                            ws_host = (
                                ws_opts.get("headers", {}).get("Host", "")
                                if isinstance(ws_opts, dict) else ""
                            )
                            if ws_host:
                                sni_val = ws_host
                            fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                            # v26: TCP补充节点添加标记
                            p["name"] = namer.generate(fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val) + "[TCP]"
                            final.append(p)
                            tested.add(k)
                            print(f"   [TCP] {p['name']}")
                        elif item["latency"] < 200:  # v26: 400→200
                            server = p.get("server", "")
                            host = server.split(":")[0] if ":" in server else server
                            reach, _ = check_node_reachability(host, timeout=1.5)
                            if not reach: continue
                            srv = p.get("server", "")
                            sni_val = p.get("sni", "") or p.get("servername", "")
                            ws_opts = p.get("ws-opts", {})
                            ws_host = (
                                ws_opts.get("headers", {}).get("Host", "")
                                if isinstance(ws_opts, dict) else ""
                            )
                            if ws_host:
                                sni_val = ws_host
                            fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                            # v26: TCP补充节点添加标记
                            p["name"] = namer.generate(fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val) + "[TCP]"
                            final.append(p)
                            tested.add(k)
                            print(f"   [TCP] {p['name']}")
                        tested.add(k)
        
        final = final[:MAX_FINAL_NODES]
        
        # v25: 最终排序 — 亚洲+Reality+协议评分综合加权
        def final_sort_key(p):
            asia = 1 if is_asia(p) else 0
            reality = 1 if is_reality_friendly(p) else 0
            proto_score = PROTOCOL_SCORE.get(p.get("type", ""), 0)
            return (-asia, -reality, -proto_score)
        
        final.sort(key=final_sort_key)
        
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
        
        print("\n" + "=" * 180)
        print("📊 统计结果")
        print("=" * 180)
        print(f"• Fork 来源：{len(fork_subs)}")
        print(f"• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总：{len(all_urls)}")
        print(f"• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}")
        print(f"• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)")
        print(f"• 最低延迟：{min_lat:.1f} ms")
        print(f"• 耗时：{tt:.1f} 秒")
        print("=" * 180 + "\n")
        
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
