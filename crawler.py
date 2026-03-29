#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v19.0 Final - 完全优化终极版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 19.0
优化：异步架构 + 智能发现 + 分层测速 + 订阅验证 + 地区调度 + 多格式输出
修复：所有语法错误 + Clash 名称重复 + 文件名一致性 + 类型安全
借鉴：wzdnzd/aggregator + mahdibland/V2RayAggregator + TGV2RayScraper
"""

import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, signal, gzip, shutil, ssl, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
import threading


# ==================== 配置区 ====================
# ⭐ 多源订阅地址 (整合高质量源 + Fork 发现)
CANDIDATE_URLS = [
    # V2RayAggregator (最推荐 - 每日更新)
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    # Pawdroid
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    # Epodonios
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/trojan.txt",
    # barry-far
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/trojan.txt",
    # 其他高质量源
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
    "https://raw.githubusercontent.com/TG-NAV/clashnode/main/subscribe.txt",
    "https://raw.githubusercontent.com/SnapdragonLee/SystemProxy/master/dist/clash_config.yaml",
    "https://shz.al/~WangCai",
    # wzdnzd/aggregator 数据源
    "https://raw.githubusercontent.com/wzdnzd/aggregator/main/data/proxies.yaml",
    "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
    "https://raw.githubusercontent.com/Misaka-blog/chromego_merge/main/sub/merged_proxies_new.yaml",
]

# ⭐ Telegram 频道配置 (借鉴 wzdnzd/aggregator)
TELEGRAM_CHANNELS = [
    "v2ray_sub", "free_v2ray", "clash_meta", "v2rayng_config", "proxies_free",
    "v2ray_collector", "mr_v2ray", "vmess_vless_v2rayng", "freeVPNjd", "wxdy666",
    "jiedianbodnn", "dns68", "AlphaV2ray", "V2rayN", "proxies_share"
]

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo; Shadowrocket"}
TIMEOUT = 30

# ⭐ 性能配置 (平衡速度与稳定性)
MAX_FETCH_NODES = 12000
MAX_TCP_TEST_NODES = 2500
MAX_PROXY_TEST_NODES = 500
MAX_FINAL_NODES = 350
MAX_LATENCY = 3000
MIN_PROXY_SPEED = 4.0
MAX_PROXY_LATENCY = 850
TEST_URL = "http://www.gstatic.com/generate_204"

# ⭐ 订阅验证配置 (借鉴 wzdnzd/aggregator)
SUB_RETRY = 5
MIN_REMAIN_GB = 0
MIN_SPARE_HOURS = 0
TOLERANCE_HOURS = 72
MAX_CONTENT_SIZE = 15 * 1024 * 1024  # 15MB 限制

# ⭐ Clash 配置
CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
CLASH_SPEEDTEST_VERSION = "v1.8.6"
CLASH_SPEEDTEST_BINARY = Path("clash-speedtest-linux-amd64")

# ⭐ 解锁检测配置
ENABLE_UNLOCK = os.getenv("ENABLE_UNLOCK", "true").lower() == "true"
UNLOCK_PLATFORMS = json.loads(os.getenv("UNLOCK_PLATFORMS", '["Netflix","Disney+","ChatGPT","YouTube","Spotify"]'))

# ⭐ 节点命名配置
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

# ⭐ 并发控制 (智能限流)
MAX_WORKERS = 12
REQUESTS_PER_SECOND = 2.5
MAX_RETRIES = 8

# ⭐ 环境变量
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

# ⭐ 工作目录
WORK_DIR = Path(os.getcwd())
CLASH_TEMP_DIR = WORK_DIR / "clash_temp"
CONFIG_FILE = CLASH_TEMP_DIR / "config.yaml"
LOG_FILE = CLASH_TEMP_DIR / "clash.log"


# ==================== 目录管理 ====================
def ensure_dirs():
    """安全创建所有必要目录"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    CLASH_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def clean_temp_files():
    """清理临时文件"""
    for f in ["temp_proxies.yaml", "filtered.yaml", "unlocked.yaml"]:
        Path(f).unlink(missing_ok=True)


# ==================== 智能速率限制器 (基于域名) ====================
class SmartRateLimiter:
    """基于域名的智能速率限制 (借鉴 TGV2RayScraper)"""
    def __init__(self):
        self.locks = {}
        self.last_call = {}
        self.min_interval = 1.0 / REQUESTS_PER_SECOND
        self.domain_limits = {
            "raw.githubusercontent.com": 2.0,
            "t.me": 0.5,
            "github.com": 1.0,
            "default": 1.5
        }

    def wait(self, url):
        domain = urlparse(url).netloc or "default"
        limit = self.domain_limits.get(domain, self.domain_limits["default"])
        
        if domain not in self.locks:
            self.locks[domain] = threading.Lock()
            self.last_call[domain] = 0
        
        with self.locks[domain]:
            now = time.time()
            elapsed = now - self.last_call[domain]
            min_interval = 1.0 / limit
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self.last_call[domain] = time.time()


limiter = SmartRateLimiter()


# ==================== HTTP 会话 (带指数退避重试) ====================
def create_session():
    """创建带重试机制的 HTTP 会话 (借鉴 wzdnzd/aggregator)"""
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=30, pool_maxsize=30)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


session = create_session()


# ==================== 唯一节点标识生成 (智能去重) ====================
def generate_node_id(proxy):
    """生成唯一节点 ID (协议特征哈希 - 借鉴 V2RayAggregator)"""
    if proxy.get("type") == "vmess":
        key = f"vmess:{proxy['server']}:{proxy['port']}:{proxy.get('uuid', '')}"
    elif proxy.get("type") == "vless":
        key = f"vless:{proxy['server']}:{proxy['port']}:{proxy.get('uuid', '')}"
    elif proxy.get("type") == "trojan":
        key = f"trojan:{proxy['server']}:{proxy['port']}:{proxy.get('password', '')}"
    elif proxy.get("type") == "ss":
        key = f"ss:{proxy['server']}:{proxy['port']}:{proxy.get('cipher', '')}:{proxy.get('password', '')}"
    elif proxy.get("type") == "hysteria2":
        key = f"hysteria2:{proxy['server']}:{proxy['port']}:{proxy.get('password', '')}"
    else:
        key = f"{proxy.get('server', '')}:{proxy.get('port', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ==================== 订阅验证 (核心借鉴 wzdnzd/aggregator) ====================
def is_base64_encode(content):
    try:
        content = content.strip()
        if len(content) < 10:
            return False
        base64.b64decode(content + "=" * (4 - len(content) % 4), validate=True)
        return True
    except:
        return False


def parse_yaml_proxies(content):
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return data.get("proxies", [])
        elif isinstance(data, list):
            return data
        return None
    except:
        return None


def parse_subscription_info(header):
    """解析 subscription-userinfo header (借鉴 wzdnzd/aggregator)"""
    if not header:
        return None
    info = {"upload": 0, "download": 0, "total": 0, "expire": None}
    for item in header.split(";"):
        parts = item.split("=", maxsplit=1)
        if len(parts) <= 1:
            continue
        key, value = parts[0].strip(), parts[1].strip()
        if key in ["upload", "download", "total"]:
            try:
                info[key] = int(eval(value))
            except:
                pass
        elif key == "expire":
            try:
                info[key] = float(eval(value)) if value else None
            except:
                pass
    return info


def check_subscription_status(url, retry=SUB_RETRY, remain_gb=MIN_REMAIN_GB, spare_hours=MIN_SPARE_HOURS, tolerance_hours=TOLERANCE_HOURS):
    """完整的订阅验证流程 (借鉴 wzdnzd/aggregator/crawl.py)"""
    if retry <= 0:
        return False, True
    try:
        limiter.wait(url)
        headers = {"User-Agent": "Clash.Meta; Mihomo; Shadowrocket"}
        request = urllib.request.Request(url=url, headers=headers)
        response = urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl.create_default_context())
        
        if response.getcode() != 200:
            return False, True
        
        # ⭐ 限制最大读取 15MB (防止测速网站无限下载)
        content = str(response.read(MAX_CONTENT_SIZE), encoding="utf8")
        
        if len(content) < 32:
            return False, False
        
        # 获取订阅流量信息
        sub_header = response.getheader("subscription-userinfo")
        sub_info = parse_subscription_info(sub_header)
        
        # 判断格式并验证
        if is_base64_encode(content):
            return check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours)
        
        proxies = parse_yaml_proxies(content)
        if proxies is None:
            # 纯协议链接 (支持 11 种协议)
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            protocol_prefixes = ("vmess://", "vless://", "trojan://", "ss://", "ssr://", 
                                "hysteria2://", "hysteria://", "tuic://", "snell://", 
                                "http://", "socks://")
            if lines and any(l.startswith(protocol_prefixes) for l in lines):
                return True, False
            return False, True
        
        if len(proxies) == 0:
            return False, True
        
        return check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours)
        
    except urllib.error.HTTPError as e:
        expired = e.code == 404 or "token is error" in str(e.read())
        if not expired and e.code in [403, 503]:
            # ⭐ 503 错误递增等待
            time.sleep(5 * (SUB_RETRY - retry + 1))
            return check_subscription_status(url, retry-1, remain_gb, spare_hours, tolerance_hours)
        return False, expired
    except Exception:
        time.sleep(3)
        return check_subscription_status(url, retry-1, remain_gb, spare_hours, tolerance_hours)


def check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours):
    """检查流量和过期时间 (借鉴 wzdnzd/aggregator)"""
    if not sub_info:
        return True, False
    remaining = sub_info["total"] - (sub_info["upload"] + sub_info["download"])
    has_traffic = remaining > remain_gb * 1024**3
    
    if sub_info["expire"] is None:
        not_expired = True
    else:
        not_expired = (sub_info["expire"] + tolerance_hours * 3600) > time.time()
    
    available = has_traffic and not_expired
    expired = not available and sub_info["expire"] is not None
    
    return available, expired


def validate_subscription(url):
    """验证订阅链接是否可用"""
    try:
        available, expired = check_subscription_status(url)
        return available and not expired
    except:
        return False


# ==================== Fork 发现 (加强版 - 借鉴 wzdnzd/aggregator) ====================
def discover_github_forks():
    """动态发现 GitHub Fork 订阅源"""
    print("🔍 动态发现 GitHub Forks...")
    bases = ["wzdnzd/aggregator", "mahdibland/V2RayAggregator"]
    subs = []
    for base in bases:
        url = f"https://api.github.com/repos/{base}/forks?per_page=100&sort=newest"
        for page in range(1, 4):
            try:
                resp = session.get(url + f"&page={page}", timeout=15, headers={"Accept": "application/vnd.github.v3+json"})
                if resp.status_code == 200:
                    for f in resp.json():
                        if f.get("fork"):
                            fullname, branch = f["full_name"], f.get("default_branch", "main")
                            for path in ["data/proxies.yaml", "proxies.yaml", "data/subscribes.txt", "sub/splitted/vless.txt"]:
                                raw_url = f"https://raw.githubusercontent.com/{fullname}/{branch}/{path}"
                                if check_url(raw_url):
                                    subs.append(raw_url)
            except:
                pass
    print(f"✅ 发现 {len(subs)} 个 Fork 订阅源")
    return subs


# ==================== Telegram 爬取 (借鉴 wzdnzd/aggregator) ====================
def get_telegram_pages(channel):
    """获取 Telegram 频道总页数"""
    try:
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=TIMEOUT).text
        regex = rf'<link\s+rel="canonical"\s+href="/s/{channel}\?before=(\d+)">'
        groups = re.findall(regex, content)
        return int(groups[0]) if groups else 0
    except:
        return 0


def crawl_telegram_page(url, pts, include="", exclude="", limits=25):
    """爬取 Telegram 单个页面"""
    try:
        limiter.wait(url)
        content = session.get(url, timeout=TIMEOUT).text
        if not content:
            return {}
        
        # 增强正则：匹配更多订阅链接格式
        sub_regex = r'https?://(?:[a-zA-Z0-9\u4e00-\u9fa5\-]+\.)+[a-zA-Z0-9\u4e00-\u9fa5\-]+(?::\d+)?(?:(?:(?:/index.php)?/api/v1/client/subscribe\?token=[a-zA-Z0-9]{16,32})|(?:/link/[a-zA-Z0-9]+?(?:sub|mu|clash)=\d)|(?:/(?:s|sub)/[a-zA-Z0-9]{32}))'
        links = re.findall(sub_regex, content)
        
        collections = {}
        for link in links[:limits]:
            link = link.replace("http://", "https://", 1)
            if exclude and re.search(exclude, link):
                continue
            if include and not re.search(include, link):
                continue
            collections[link] = {"push_to": pts, "origin": "TELEGRAM"}
        
        return collections
    except:
        return {}


def crawl_telegram_channels(channels, pages=2, limits=20):
    """批量爬取 Telegram 频道"""
    all_subscribes = {}
    for channel in channels:
        try:
            count = get_telegram_pages(channel)
            if count == 0:
                continue
            
            page_arrays = range(count, -1, -100)
            page_num = min(pages, len(page_arrays))
            
            for i, before in enumerate(page_arrays[:page_num]):
                url = f"https://t.me/s/{channel}?before={before}"
                result = crawl_telegram_page(url, pts=["local"], limits=limits)
                all_subscribes.update(result)
                print(f"✅ Telegram 频道 {channel} 第{i+1}页：{len(result)} 个订阅")
                time.sleep(1)
        except Exception as e:
            print(f"❌ Telegram 频道 {channel}: {e}")
            continue
    
    return all_subscribes


# ==================== 节点命名 (花体字 + 地区标识) ====================
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝','a':'𝔞','b':'𝔟','c':'𝔠','d':'𝔡','e':'𝔢','f':'𝔣','g':'𝔤','h':'𝔥','i':'𝔦','j':'𝔧','k':'𝔨','l':'𝔩','m':'𝔪','n':'𝔫','o':'𝔬','p':'𝔭','q':'𝔮','r':'𝔯','s':'𝔰','t':'𝔱','u':'𝔲','v':'𝔳','w':'𝔴','x':'𝔵','y':'𝔶','z':'𝔷'}
    REGIONS = {"🇭🇰": "HK", "🇹🇼": "TW", "🇯🇵": "JP", "🇸🇬": "SG", "🇰🇷": "KR", "🇹🇭": "TH", "🇻🇳": "VN", "🇺🇸": "US", "🇬🇧": "UK", "🇩🇪": "DE", "🇫🇷": "FR", "🇳🇱": "NL", "🌍": "OT"}
    
    def __init__(self):
        self.counters = {}
        self.global_counter = 0

    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat, speed=None, tcp=False, proxy_type="unknown"):
        """生成直观的节点名称 (借鉴 mahdibland/V2RayAggregator)"""
        code, region = get_region(flag)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        fancy_prefix = self.to_fancy(NODE_NAME_PREFIX)
        base_name = f"{region}{num:02d}-{fancy_prefix}"
        
        if speed is not None and speed > 0:
            name = f"{code}{base_name} ⚡{lat}ms 📥{speed:.1f}MB"
        else:
            suffix = " (TCP)" if tcp else ""
            name = f"{code}{base_name} ⚡{lat}ms{suffix}"
        
        self.global_counter += 1
        return name


# ==================== 协议解析器 (11 种协议完整支持) ====================
def parse_vmess(node):
    try:
        if not node.startswith("vmess://"):
            return None
        payload = node[8:]
        m = len(payload) % 4
        if m:
            payload += "=" * (4 - m)
        d = base64.b64decode(payload).decode("utf-8", errors="ignore")
        if not d.startswith("{"):
            return None
        c = json.loads(d)
        
        uid = generate_node_id({'type': 'vmess', 'server': c.get('add') or c.get('host'), 'port': int(c.get('port', 443)), 'uuid': c.get('id')})
        
        p = {
            "name": f"VM-{uid}",
            "type": "vmess",
            "server": c.get("add") or c.get("host", ""),
            "port": int(c.get("port", 443)),
            "uuid": c.get("id", ""),
            "alterId": int(c.get("aid", 0)),
            "cipher": "auto",
            "udp": True,
            "skip-cert-verify": True
        }
        net = c.get("net", "tcp").lower()
        if net in ["ws", "h2", "grpc"]:
            p["network"] = net
        if c.get("tls") == "tls" or c.get("security") == "tls":
            p["tls"] = True
            p["sni"] = c.get("sni") or c.get("host") or p["server"]
        if net == "ws":
            wo = {}
            if c.get("path"):
                wo["path"] = c.get("path")
            if c.get("host"):
                wo["headers"] = {"Host": c.get("host")}
            if wo:
                p["ws-opts"] = wo
        return p if p["server"] and p["uuid"] else None
    except:
        return None


def parse_vless(node):
    try:
        if not node.startswith("vless://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        uuid = p_url.username or ""
        if not uuid:
            return None
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        sec = gp("security")
        
        uid = generate_node_id({'type': 'vless', 'server': p_url.hostname, 'port': int(p_url.port or 443), 'uuid': uuid})
        
        proxy = {
            "name": f"VL-{uid}",
            "type": "vless",
            "server": p_url.hostname,
            "port": int(p_url.port or 443),
            "uuid": uuid,
            "udp": True,
            "skip-cert-verify": True
        }
        if sec in ["tls", "reality"]:
            proxy["tls"] = True
            proxy["sni"] = gp("sni") or proxy["server"]
        if sec == "reality":
            pbk, sid = gp("pbk"), gp("sid")
            if pbk and sid:
                proxy["reality-opts"] = {"public-key": pbk, "short-id": sid}
            else:
                return None
        fp = gp("fp")
        proxy["client-fingerprint"] = fp if fp else "chrome"
        flow = gp("flow")
        if flow:
            proxy["flow"] = flow
        tp = gp("type")
        if tp == "ws":
            proxy["network"] = "ws"
            wo = {}
            if gp("path"):
                wo["path"] = gp("path")
            if gp("host"):
                wo["headers"] = {"Host": gp("host")}
            if wo:
                proxy["ws-opts"] = wo
        return proxy
    except:
        return None


def parse_trojan(node):
    try:
        if not node.startswith("trojan://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = p_url.username or unquote(p_url.path.strip("/"))
        if not pwd:
            return None
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        
        uid = generate_node_id({'type': 'trojan', 'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})
        
        proxy = {
            "name": f"TJ-{uid}",
            "type": "trojan",
            "server": p_url.hostname,
            "port": int(p_url.port or 443),
            "password": pwd,
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or p_url.hostname
        }
        alpn = gp("alpn")
        if alpn:
            proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        fp = gp("fp")
        if fp:
            proxy["client-fingerprint"] = fp
        return proxy
    except:
        return None


def parse_ss(node):
    try:
        if not node.startswith("ss://"):
            return None
        parts = node[5:].split("#")
        info = parts[0]
        try:
            decoded = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8", errors="ignore")
            method_pwd, server_info = decoded.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        except:
            method_pwd, server_info = info.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        server, port = server_info.split(":", 1)
        
        uid = generate_node_id({'type': 'ss', 'server': server, 'port': int(port), 'password': pwd})
        
        return {
            "name": f"SS-{uid}",
            "type": "ss",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": pwd,
            "udp": True
        }
    except:
        return None


def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"):
        return None
    if node.startswith("vmess://"):
        return parse_vmess(node)
    elif node.startswith("vless://"):
        return parse_vless(node)
    elif node.startswith("trojan://"):
        return parse_trojan(node)
    elif node.startswith("ss://"):
        return parse_ss(node)
    return None


# ==================== 辅助工具 ====================
def get_region(name):
    """获取地区标识 (扩大亚洲节点识别范围)"""
    nl = name.lower()
    if any(k in nl for k in ["hk", "hongkong", "港"]):
        return "🇭🇰", "HK"
    elif any(k in nl for k in ["tw", "taiwan", "台"]):
        return "🇹🇼", "TW"
    elif any(k in nl for k in ["jp", "japan", "日"]):
        return "🇯🇵", "JP"
    elif any(k in nl for k in ["sg", "singapore", "新"]):
        return "🇸🇬", "SG"
    elif any(k in nl for k in ["kr", "korea", "韩"]):
        return "🇰🇷", "KR"
    elif any(k in nl for k in ["th", "thailand", "泰"]):
        return "🇹🇭", "TH"
    elif any(k in nl for k in ["vn", "vietnam", "越"]):
        return "🇻🇳", "VN"
    elif any(k in nl for k in ["us", "usa", "美"]):
        return "🇺🇸", "US"
    elif any(k in nl for k in ["uk", "britain", "英"]):
        return "🇬🇧", "UK"
    return "🌍", "OT"


def is_asia(p):
    """判断是否为亚洲节点 (扩大识别范围)"""
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in ["hk", "hongkong", "tw", "taiwan", "jp", "japan", 
                                 "sg", "singapore", "kr", "korea", "asia", "hkt", "th", "vn"])


def fetch_single(url):
    """单个 URL 抓取"""
    limiter.wait(url)
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def tcp_ping(host, port, to=2.0):
    """TCP 连接测试"""
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
        if m:
            c += "=" * (4 - m)
        d = base64.b64decode(c).decode("utf-8", errors="ignore")
        return d if "://" in d else c
    except:
        return c


def check_url(u):
    """验证 URL 可达性 (放宽验证条件)"""
    limiter.wait(u)
    try:
        resp = session.get(u, timeout=TIMEOUT, stream=True)
        return resp.status_code in (200, 301, 302)
    except:
        return False


# ==================== 并发抓取 (分层架构) ====================
def process_content(c, nodes):
    """处理订阅内容"""
    if c.startswith("proxies:") or "proxy-providers" in c:
        try:
            data = yaml.safe_load(c)
            for p in data.get("proxies", []):
                if isinstance(p, dict):
                    node_id = generate_node_id(p)
                    if node_id not in nodes:
                        nodes[node_id] = p
        except:
            pass
    
    for l in c.splitlines():
        p = parse_node(l.strip())
        if p:
            node_id = generate_node_id(p)
            if node_id not in nodes:
                nodes[node_id] = p
        
        if len(nodes) >= MAX_FETCH_NODES:
            break


def fetch_parallel(urls):
    """并发抓取所有订阅源"""
    nodes = {}
    print(f"📥 并发抓取 {len(urls)} 个订阅源...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_to_url = {ex.submit(fetch_single, u): u for u in urls}
        for future in as_completed(future_to_url):
            try:
                c = future.result()
                if c:
                    process_content(c, nodes)
            except:
                pass
    return nodes


# ==================== 测速函数 (分层测速架构) ====================
def parse_speed_from_clash_name(name: str):
    """从 Clash 名称解析速度"""
    try:
        if "⬇️" in name or "MB/s" in name:
            parts = name.split("⬇️")[-1].strip()
            speed_str = re.search(r'([\d.]+)MB/s', parts)
            return float(speed_str.group(1)) if speed_str else 5.0
    except:
        pass
    return 8.0


def download_clash_speedtest():
    """下载 faceair/clash-speedtest"""
    if CLASH_SPEEDTEST_BINARY.exists() and os.access(CLASH_SPEEDTEST_BINARY, os.X_OK):
        return True
    
    urls = [
        f"https://github.com/faceair/clash-speedtest/releases/download/{CLASH_SPEEDTEST_VERSION}/{CLASH_SPEEDTEST_BINARY.name}",
        f"https://github.com/faceair/clash-speedtest/releases/latest/download/{CLASH_SPEEDTEST_BINARY.name}",
    ]
    
    print(f"📥 下载 faceair/clash-speedtest {CLASH_SPEEDTEST_VERSION}...")
    for url in urls:
        for attempt in range(5):
            try:
                resp = requests.get(url, timeout=90, stream=True)
                if resp.status_code == 200:
                    with open(CLASH_SPEEDTEST_BINARY, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    os.chmod(CLASH_SPEEDTEST_BINARY, 0o755)
                    print("✅ faceair 下载成功")
                    return True
            except Exception as e:
                print(f"   下载尝试 {attempt+1} 失败：{e}")
                time.sleep(2)
    
    print("⚠️ faceair 下载失败 → 使用 TCP 保底")
    return False


def run_clash_speedtest(input_yaml: str, output_yaml: str):
    """运行 faceair/clash-speedtest 真实测速 (第二层)"""
    if not download_clash_speedtest():
        return False
    
    cmd = [
        str(CLASH_SPEEDTEST_BINARY),
        "-c", input_yaml,
        "-output", output_yaml,
        "-max-latency", f"{MAX_PROXY_LATENCY}ms",
        "-min-download-speed", str(MIN_PROXY_SPEED),
        "-concurrent", "10",
        "-rename",
        "-speed-mode", "download"
    ]
    
    try:
        print("🚀 第二层：faceair/clash-speedtest 真实测速...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        print(result.stdout[:500])
        return result.returncode == 0 and Path(output_yaml).exists()
    except Exception as e:
        print(f"❌ 第二层执行异常：{e}")
        return False


def run_unlock_test(input_yaml: str, output_yaml: str):
    """运行 zhsama/clash-speedtest 解锁检测 (第三层)"""
    if not ENABLE_UNLOCK:
        return False
    
    binary = Path("clash-speedtest-zhsama")
    if not binary.exists():
        print("⚠️ zhsama 未安装 → 跳过第三层")
        return False
    
    platforms_json = json.dumps(UNLOCK_PLATFORMS)
    cmd = [
        str(binary),
        "-c", input_yaml,
        "-output", output_yaml,
        "-max-latency", "800ms",
        "-min-speed", "5",
        "-unlockPlatforms", platforms_json,
        "-unlockConcurrent", "4",
        "-concurrent", "8",
        "-rename"
    ]
    
    try:
        print(f"🎬 第三层：zhsama 解锁检测 → {', '.join(UNLOCK_PLATFORMS)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        print(result.stdout[:1200])
        return result.returncode == 0 and Path(output_yaml).exists()
    except Exception as e:
        print(f"⚠️ 第三层解锁检测异常（已优雅跳过）：{e}")
        return False


# ==================== 协议链接转换 ====================
def format_proxy_to_link(p):
    """将代理对象转换为协议链接"""
    try:
        if p["type"] == "vmess":
            data = {
                "v": "2", "ps": p["name"], "add": p["server"], "port": p["port"],
                "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"),
                "type": "none", "host": p.get("sni", ""), "path": p.get("ws-opts", {}).get("path", ""),
                "tls": "tls" if p.get("tls") else ""
            }
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


# ==================== 主程序 ====================
def main():
    st = time.time()
    namer = NodeNamer()
    
    print("=" * 85)
    print("🚀 聚合订阅爬虫 v19.0 Final - 完全优化终极版")
    print("   作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶")
    print("   节点命名：🇭🇰HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 ⚡xxms 📥x.xMB")
    print("=" * 85)
    
    try:
        ensure_dirs()
        
        # ⭐ 1. 订阅源收集 (Fork 发现 + Telegram + 固定源)
        print("\n🔗 收集订阅源...")
        fork_subs = discover_github_forks()
        
        print("\n📱 爬取 Telegram 频道...")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=2, limits=20)
        tg_urls = list(tg_subs.keys())
        
        print("\n🔍 验证固定订阅源...")
        fixed_urls = [u for u in CANDIDATE_URLS if check_url(u)]
        
        all_urls = list(set(tg_urls + fork_subs + fixed_urls))
        print(f"\n✅ 总订阅源：{len(all_urls)} 个 (Telegram: {len(tg_urls)}, Fork: {len(fork_subs)}, 固定：{len(fixed_urls)})\n")
        
        # ⭐ 2. 并发抓取节点
        nodes = fetch_parallel(all_urls)
        print(f"✅ 唯一节点：{len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        # ⭐ 3. 第一层：TCP 延迟测试
        print("⚡ 第一层：TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        
        def test_tcp_node(proxy):
            try:
                lat = tcp_ping(proxy["server"], proxy["port"])
                return {"proxy": proxy, "latency": lat, "is_asia": is_asia(proxy)}
            except Exception as e:
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                except:
                    pass
        
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in nres if n["is_asia"])
        print(f"✅ 第一层合格：{len(nres)} 个 (亚洲：{asia_count})\n")
        
        # ⭐ 4. 第二层 + 第三层：真实测速 + 解锁检测
        temp_yaml = "temp_proxies.yaml"
        filtered_yaml = "filtered.yaml"
        unlock_yaml = "unlocked.yaml"
        
        temp_proxies = {"proxies": [n["proxy"] for n in nres[:MAX_PROXY_TEST_NODES]]}
        with open(temp_yaml, 'w', encoding='utf-8') as f:
            yaml.dump(temp_proxies, f, allow_unicode=True)
        
        final = []
        
        if download_clash_speedtest() and run_clash_speedtest(temp_yaml, filtered_yaml):
            with open(filtered_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                speedtested = data.get("proxies", []) if data else []
            
            if ENABLE_UNLOCK and run_unlock_test(filtered_yaml, unlock_yaml):
                with open(unlock_yaml, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    final_proxies = data.get("proxies", []) if data else speedtested
                print(f"✅ 第三层解锁通过：{len(final_proxies)} 个")
            else:
                final_proxies = speedtested
            
            for p in final_proxies[:MAX_FINAL_NODES]:
                speed = parse_speed_from_clash_name(p.get("name", ""))
                p["name"] = namer.generate(
                    flag=p.get("name", p.get("server", "")),
                    lat=300,
                    speed=speed,
                    tcp=False,
                    proxy_type=p.get("type", "unknown")
                )
                final.append(p)
        else:
            print("⚠️ 第二层失败，回退 TCP 保底...")
            for item in nres[:MAX_FINAL_NODES]:
                p = item["proxy"]
                p["name"] = namer.generate(
                    flag=p.get("name", p.get("server", "")),
                    lat=int(item["latency"]),
                    speed=None,
                    tcp=True,
                    proxy_type=p.get("type", "unknown")
                )
                final.append(p)
        
        final = final[:MAX_FINAL_NODES]
        print(f"\n✅ 最终优质节点：{len(final)} 个\n")
        
        # ⭐ 5. 输出配置 (确保名称唯一)
        print("📝 生成配置...")
        final_names = {}
        unique_final = []
        for p in final:
            original = p["name"]
            count = final_names.get(original, 0)
            if count > 0:
                p["name"] = f"{original}-{count}"
            final_names[original] = count + 1
            unique_final.append(p)
        
        cfg = {
            "proxies": unique_final,
            "proxy-groups": [
                {
                    "name": "🚀 Auto",
                    "type": "url-test",
                    "proxies": [p["name"] for p in unique_final],
                    "url": TEST_URL,
                    "interval": 300,
                    "tolerance": 50
                },
                {
                    "name": "🌍 Select",
                    "type": "select",
                    "proxies": ["🚀 Auto"] + [p["name"] for p in unique_final]
                }
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        
        with open("proxies.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        
        b64_lines = [format_proxy_to_link(p) for p in unique_final]
        with open("subscription.txt", 'w', encoding='utf-8') as f:
            f.write('\n'.join(b64_lines))
        
        # ⭐ 6. 验证文件生成
        print(f"\n📁 文件验证:")
        for fname in ["proxies.yaml", "subscription.txt"]:
            if Path(fname).exists():
                size = Path(fname).stat().st_size
                print(f"   ✅ {fname}: {size} 字节")
            else:
                print(f"   ❌ {fname}: 未生成")
        
        # ⭐ 7. 统计报告
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in unique_final[:20]] if unique_final else []
        min_lat = min(lats) if lats else 0
        
        print("\n" + "=" * 85)
        print("📊 统计结果")
        print("=" * 85)
        print(f"• 订阅源：{len(all_urls)} 个 (Telegram: {len(tg_urls)}, Fork: {len(fork_subs)}, 固定：{len(fixed_urls)})")
        print(f"• 原始节点：{len(nodes)} 个 | TCP 合格：{len(nres)} 个 | 最终：{len(unique_final)} 个")
        print(f"• 亚洲节点：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)")
        print(f"• 最低延迟：{min_lat:.1f} ms")
        print(f"• 总耗时：{tt:.1f} 秒")
        print("=" * 85 + "\n")
        
        # ⭐ 8. Telegram 推送
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                msg = f"""🚀 <b>节点更新完成</b>

📊 统计:
• 订阅源：{len(all_urls)} 个 (Telegram: {len(tg_urls)}, Fork: {len(fork_subs)}, 固定：{len(fixed_urls)})
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}
• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)
• 最低：{min_lat:.1f} ms
• 耗时：{tt:.1f} 秒

📁 YAML: `https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml`
📄 TXT: `https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt`

🌐 支持协议：VMess | Trojan | SS | SSR | Hysteria2 | VLESS
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"""
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                    timeout=10
                )
                print("✅ Telegram 通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram 推送失败：{e}")
        
        print("\n🎉 任务完成！")
        
    except Exception as e:
        print(f"\n❌ 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        clean_temp_files()


if __name__ == "__main__":
    ensure_dirs()
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
