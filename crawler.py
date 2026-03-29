#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v15.0 Final - 完全修复优化版
作者: 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 15.0
修复: 所有语法错误 + Clash 名称重复 + 文件名一致性 + 性能优化
借鉴: wzdnzd/aggregator + mahdibland/V2RayAggregator
"""

import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, signal, gzip, shutil, ssl, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
import threading


# ==================== 配置区 ====================
CANDIDATE_URLS = [
    # V2RayAggregator (最推荐)
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
]

TELEGRAM_CHANNELS = [
    "v2ray_sub", "free_v2ray", "clash_meta", "v2rayng_config", "proxies_free",
    "v2ray_collector", "mr_v2ray", "vmess_vless_v2rayng", "freeVPNjd", "wxdy666",
    "jiedianbodnn", "dns68"
]

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo; Shadowrocket"}
TIMEOUT = 30

# 性能配置 (避免 503)
MAX_FETCH_NODES = 2000
MAX_TCP_TEST_NODES = 300
MAX_PROXY_TEST_NODES = 100
MAX_FINAL_NODES = 80
MAX_LATENCY = 2000
MIN_PROXY_SPEED = 0.01
MAX_PROXY_LATENCY = 3000
TEST_URL = "http://www.gstatic.com/generate_204"

# 订阅验证配置
SUB_RETRY = 5
MIN_REMAIN_GB = 0
MIN_SPARE_HOURS = 0
TOLERANCE_HOURS = 72
MAX_CONTENT_SIZE = 15 * 1024 * 1024

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

# 并发控制
MAX_WORKERS = 3
REQUESTS_PER_SECOND = 0.5
MAX_RETRIES = 5

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"


def ensure_clash_dir():
    """安全创建目录"""
    if WORK_DIR.exists() and not WORK_DIR.is_dir():
        WORK_DIR.unlink()
    WORK_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 速率限制器 ====================
class RateLimiter:
    def __init__(self, calls_per_second=REQUESTS_PER_SECOND):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


limiter = RateLimiter()


# ==================== HTTP 会话 ====================
def create_session():
    session = requests.Session()
    retry = Retry(total=MAX_RETRIES, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


session = create_session()


# ==================== 唯一节点 ID 生成 ====================
def generate_node_id(proxy):
    """生成唯一节点 ID (协议特征哈希)"""
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


# ==================== 订阅验证 ====================
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
    """解析 subscription-userinfo header"""
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
    """完整的订阅验证流程"""
    if retry <= 0:
        return False, True
    try:
        limiter.wait()
        headers = {"User-Agent": "Clash.Meta; Mihomo; Shadowrocket"}
        request = urllib.request.Request(url=url, headers=headers)
        response = urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl.create_default_context())
        
        if response.getcode() != 200:
            return False, True
        
        content = str(response.read(MAX_CONTENT_SIZE), encoding="utf8")
        
        if len(content) < 32:
            return False, False
        
        sub_header = response.getheader("subscription-userinfo")
        sub_info = parse_subscription_info(sub_header)
        
        if is_base64_encode(content):
            return check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours)
        
        proxies = parse_yaml_proxies(content)
        if proxies is None:
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
            time.sleep(5 * (SUB_RETRY - retry + 1))
            return check_subscription_status(url, retry-1, remain_gb, spare_hours, tolerance_hours)
        return False, expired
    except Exception:
        time.sleep(3)
        return check_subscription_status(url, retry-1, remain_gb, spare_hours, tolerance_hours)


def check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours):
    """检查流量和过期时间"""
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


# ==================== Telegram 爬取 ====================
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
        limiter.wait()
        content = session.get(url, timeout=TIMEOUT).text
        if not content:
            return {}
        
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


# ==================== 节点命名 ====================
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝','a':'𝔞','b':'𝔟','c':'𝔠','d':'𝔡','e':'𝔢','f':'𝔣','g':'𝔤','h':'𝔥','i':'𝔦','j':'𝔧','k':'𝔨','l':'𝔩','m':'𝔪','n':'𝔫','o':'𝔬','p':'𝔭','q':'𝔮','r':'𝔯','s':'𝔰','t':'𝔱','u':'𝔲','v':'𝔳','w':'𝔴','x':'𝔵','y':'𝔶','z':'𝔷'}
    REGIONS = {"🇭🇰": "HK", "🇹🇼": "TW", "🇯🇵": "JP", "🇸🇬": "SG", "🇰🇷": "KR", "🇹🇭": "TH", "🇻🇳": "VN", "🇺🇸": "US", "🇬🇧": "UK", "🇩🇪": "DE", "🇫🇷": "FR", "🇳🇱": "NL", "🌍": "OT"}
    
    def __init__(self):
        self.counters = {}

    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c, c) for c in t)

    def generate(self, flag, lat, speed=None, tcp=False):
        code = self.REGIONS.get(flag, "OT")
        self.counters[code] = self.counters.get(code, 0) + 1
        num = self.counters[code]
        pfx = self.to_fancy(NODE_NAME_PREFIX)
        if speed:
            return f"{code}{num}-{pfx}|⚡{lat}ms|📥{speed:.1f}MB"
        return f"{code}{num}-{pfx}|⚡{lat}ms{'(TCP)' if tcp else ''}"


# ==================== Clash 管理器 ====================
class ClashManager:
    def __init__(self):
        self.error_details = []
        self.process = None
        ensure_clash_dir()

    def download_clash(self):
        if CLASH_PATH.exists():
            return True
        url = f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz"
        try:
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code != 200:
                return False
            temp = WORK_DIR / "mihomo.gz"
            with open(temp, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            with gzip.open(temp, 'rb') as f_in:
                with open(CLASH_PATH, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.chmod(CLASH_PATH, 0o755)
            temp.unlink()
            return CLASH_PATH.exists()
        except:
            return False

    def create_config(self, proxies):
        ensure_clash_dir()
        # 确保代理名称唯一
        names = []
        seen = set()
        for i, p in enumerate(proxies[:MAX_PROXY_TEST_NODES]):
            name = p["name"]
            if name in seen:
                name = f"{name}-{i}"
            seen.add(name)
            names.append(name)
            p["name"] = name
        
        config = {
            "port": CLASH_PORT,
            "socks-port": CLASH_PORT + 1,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "warning",
            "external-controller": f"0.0.0.0:{CLASH_API_PORT}",
            "secret": "",
            "ipv6": False,
            "unified-delay": True,
            "tcp-concurrent": True,
            "proxies": proxies[:MAX_PROXY_TEST_NODES],
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": names}],
            "rules": ["MATCH,TEST"]
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        return True

    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash():
            return False
        LOG_FILE.touch()
        try:
            with open(LOG_FILE, 'w') as lf:
                self.process = subprocess.Popen(
                    [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())],
                    stdout=lf, stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid,
                    cwd=str(WORK_DIR.absolute())
                )
            for i in range(30):
                time.sleep(1)
                if self.process.poll() is not None:
                    return False
                try:
                    if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                        return True
                except:
                    pass
            return False
        except:
            return False

    def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except:
                pass

    def test_proxy(self, name):
        result = {"success": False, "latency": 9999, "speed": 0.0, "error": ""}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST", json={"name": name}, timeout=5)
            time.sleep(0.3)
            px = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            start = time.time()
            resp = requests.get(TEST_URL, proxies=px, timeout=10, allow_redirects=False)
            lat = (time.time() - start) * 1000
            if resp.status_code in [200, 204, 301, 302]:
                sp_start = time.time()
                sp_resp = requests.get("https://speed.cloudflare.com/__down?bytes=524288", proxies=px, timeout=15)
                sp = len(sp_resp.content) / max(0.5, time.time() - sp_start) / (1024 * 1024)
                result = {"success": True, "latency": round(lat, 1), "speed": round(sp, 2), "error": ""}
            else:
                result["error"] = f"Status:{resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:80]
        return result


# ==================== 协议解析器 ====================
def parse_vmess(node):
    try:
        if not node.startswith("vmess://"):
            return None
        payload = node[8:]
        for _ in range(2):
            try:
                m = len(payload) % 4
                if m:
                    payload += "=" * (4 - m)
                d = base64.b64decode(payload).decode("utf-8")
                if d.startswith("{"):
                    payload = d
                    break
                payload = d
            except:
                break
        if not payload.startswith("{"):
            return None
        c = json.loads(payload)
        
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
            decoded = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8")
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


def parse_ssr(node):
    try:
        if not node.startswith("ssr://"):
            return None
        info = node[6:]
        info = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8")
        parts = info.split("/?")
        main = parts[0].split(":")
        if len(main) < 6:
            return None
        server, port, protocol, method, obfs = main[0], main[1], main[2], main[3], main[4]
        pwd = base64.b64decode(main[5] + "=" * (4 - len(main[5]) % 4)).decode("utf-8")
        
        uid = generate_node_id({'type': 'ssr', 'server': server, 'port': int(port), 'password': pwd})
        
        proxy = {
            "name": f"SSR-{uid}",
            "type": "ssr",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": pwd,
            "protocol": protocol,
            "obfs": obfs,
            "udp": True
        }
        if len(parts) > 1:
            params = parse_qs(parts[1])
            if "remarks" in params:
                proxy["name"] = base64.b64decode(params["remarks"][0] + "=" * (4 - len(params["remarks"][0]) % 4)).decode("utf-8")
        return proxy
    except:
        return None


def parse_hysteria2(node):
    try:
        if not node.startswith("hysteria2://"):
            return None
        p_url = urlparse(node)
        if not p_url.hostname:
            return None
        pwd = unquote(p_url.username or "")
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        
        uid = generate_node_id({'type': 'hysteria2', 'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})
        
        return {
            "name": f"H2-{uid}",
            "type": "hysteria2",
            "server": p_url.hostname,
            "port": int(p_url.port or 443),
            "password": pwd or gp("auth"),
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or p_url.hostname
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
    elif node.startswith("ssr://"):
        return parse_ssr(node)
    elif node.startswith("hysteria2://"):
        return parse_hysteria2(node)
    return None


# ==================== 辅助工具 ====================
def get_region(name):
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
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in ["hk", "hongkong", "tw", "taiwan", "jp", "japan", "sg", "singapore", "kr", "korea", "asia", "hkt", "th", "vn"])


def fetch(url):
    limiter.wait()
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def tcp_ping(host, port, to=2.0):
    if not host:
        return 9999
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(to)
        st = time.time()
        s.connect((host, port))
        s.close()
        return round((time.time() - st) * 1000, 1)
    except:
        return 9999


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
    limiter.wait()
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False


# ==================== 协议链接转换 ====================
def format_proxy_to_link(p):
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
            pwd_enc = urllib.parse.quote(p['password'], safe='')
            sni = p.get('sni', p['server'])
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?sni={sni}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "vless":
            return f"vless://{p['uuid']}@{p['server']}:{p['port']}?type={p.get('network', 'tcp')}&security={'tls' if p.get('tls') else 'none'}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "ss":
            auth_enc = base64.b64encode(f"{p['cipher']}:{p['password']}".encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "ssr":
            ssr_str = f"{p['server']}:{p['port']}:{p['protocol']}:{p['cipher']}:{p['obfs']}:{urllib.parse.quote(p['password'])}/?remarks={urllib.parse.quote(p['name'])}"
            return f"ssr://{base64.b64encode(ssr_str.encode()).decode()}"
        elif p["type"] == "hysteria2":
            pwd_enc = urllib.parse.quote(p['password'], safe='')
            sni = p.get('sni', p['server'])
            return f"hysteria2://{pwd_enc}@{p['server']}:{p['port']}?insecure=1&sni={sni}#{urllib.parse.quote(p['name'], safe='')}"
        return f"# {p['name']}"
    except:
        return f"# {p['name']}"


# ==================== 主程序 ====================
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 50)
    print("🚀 聚合订阅爬虫 v15.0 Final")
    print("作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶")
    print("=" * 50)
    
    all_urls = []
    
    try:
        # 1. Telegram 频道爬取
        print("\n📱 爬取 Telegram 频道...")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=2, limits=20)
        tg_urls = list(tg_subs.keys())
        all_urls.extend(tg_urls)
        print(f"✅ Telegram 订阅：{len(tg_urls)} 个\n")
        
        # 2. 固定订阅源
        print("🔍 验证固定订阅源...")
        fixed_urls = [u for u in CANDIDATE_URLS if check_url(u)]
        all_urls.extend(fixed_urls)
        print(f"✅ 固定订阅源：{len(fixed_urls)} 个\n")
        
        # 3. 去重
        all_urls = list(set(all_urls))
        print(f"📊 总订阅源：{len(all_urls)} 个\n")
        
        # 4. 抓取节点
        print("📥 抓取节点...")
        nodes = {}
        for u in all_urls:
            c = fetch(u)
            if not c:
                continue
            if is_base64(c):
                c = decode_b64(c)
            for l in c.splitlines():
                l = l.strip()
                if not l or l.startswith("#"):
                    continue
                p = parse_node(l)
                if p:
                    node_id = generate_node_id(p)
                    if node_id not in nodes:
                        nodes[node_id] = p
                if len(nodes) >= MAX_FETCH_NODES:
                    break
            if len(nodes) >= MAX_FETCH_NODES:
                break
        print(f"✅ 唯一节点：{len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        # 5. TCP 测试 (使用独立函数，避免 lambda 语法错误)
        print("⚡ TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        
        def test_tcp_node(proxy):
            lat = tcp_ping(proxy["server"], proxy["port"])
            return {"proxy": proxy, "latency": lat, "is_asia": is_asia(proxy)}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(test_tcp_node, p): p for p in nlist}
            for i, f in enumerate(as_completed(futs)):
                p, lat, asia = f.result()
                if lat < MAX_LATENCY:
                    nres.append({"proxy": p, "latency": lat, "is_asia": asia})
        
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        print(f"✅ TCP 合格：{len(nres)} 个（亚洲：{sum(1 for n in nres if n['is_asia'])}）\n")
        
        # 6. 真实测速 + TCP 保底
        print("🚀 真实代理测速...")
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
                    if len(final) >= MAX_FINAL_NODES:
                        break
                    if (i + 1) % 10 == 0:
                        print(f"   进度：{i + 1}/{min(len(nres), MAX_PROXY_TEST_NODES)} | 合格：{len(final)}")
                clash.stop()
                
                if len(final) < 50:
                    print(f"\n⚠️ 测速合格 {len(final)} 个，使用 TCP 补充...")
                    for item in nres:
                        if len(final) >= 50:
                            break
                        p = item["proxy"]
                        k = f"{p['server']}:{p['port']}"
                        if k in tested:
                            continue
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
                print("⚠️ Clash 启动失败，使用 TCP 筛选...")
                for item in nres[:MAX_FINAL_NODES * 2]:
                    if len(final) >= MAX_FINAL_NODES:
                        break
                    p = item["proxy"]
                    k = f"{p['server']}:{p['port']}"
                    if k in tested:
                        continue
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
        
        # 7. 输出配置
        print("📝 生成配置...")
        
        # 确保最终名称唯一
        final_names = {}
        unique_final = []
        for p in final:
            original_name = p["name"]
            count = final_names.get(original_name, 0)
            if count > 0:
                p["name"] = f"{original_name}-{count}"
            final_names[original_name] = count + 1
            unique_final.append(p)
        
        cfg = {
            "proxies": unique_final,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in unique_final], "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in unique_final]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        with open("proxies.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        
        b64_lines = [f"{format_proxy_to_link(p)}" for p in unique_final]
        with open("subscription.txt", 'w', encoding='utf-8') as f:
            f.write('\n'.join(b64_lines))
        
        # 统计
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in unique_final[:20]] if unique_final else []
        min_lat = min(lats) if lats else 0
        
        print("\n" + "=" * 50)
        print("📊 统计结果")
        print("=" * 50)
        print(f"• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总：{len(all_urls)}")
        print(f"• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}")
        print(f"• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)")
        print(f"• 最低延迟：{min_lat:.1f} ms")
        print(f"• 耗时：{tt:.1f} 秒")
        print("=" * 50 + "\n")
        
        # Telegram 推送
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                msg = f"""🚀 <b>节点更新完成</b>

📊 统计:
• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总：{len(all_urls)}
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}
• 亚洲：{asia_ct} 个
• 最低：{min_lat:.1f} ms
• 耗时：{tt:.1f} 秒

📁 YAML: `https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml`
📄 TXT: `https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt`

🌐 支持协议：VMess | Trojan | SS | SSR | Hysteria2 | VLESS
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
                print("✅ Telegram 通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram 推送失败：{e}")
        
        print("🎉 任务完成！")
        
    finally:
        clash.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
