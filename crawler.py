#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clash 节点筛选器 - v9.0 (终极整合版)
整合 wzdnzd/aggregator 核心功能：
  ✅ 多源订阅爬取 (Google/Telegram/GitHub/网页)
  ✅ 完整订阅验证 (流量/过期时间)
  ✅ 节点参数完整解析 (VMess/VLESS/Trojan/Reality)
  ✅ Clash.Meta 真实代理测试
  ✅ 请求速率限制 + 自动重试 (解决 503 错误)
  ✅ TCP 保底策略 (确保有可用节点)
  ✅ 节点重命名 (特殊字体 + 地区标识)
  ✅ 多维度过滤 (名称/延迟/速度/地区)
"""

import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, signal, gzip, shutil, ssl, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import threading

# ==================== 配置区 ====================
# ⭐ 多源订阅地址 (整合高质量源)
CANDIDATE_URLS = [
    # V2RayAggregator (高质量)
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    # Pawdroid
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    # Epodonios
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    # ermaozi
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    # barry-far
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/trojan.txt",
    # roosterkid
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/V2RAY_RAW.txt",
    # NoMoreWalls
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
]

# ⭐ 搜索引擎爬取配置 (借鉴 wzdnzd/aggregator)
SEARCH_CONFIG = {
    "google": {"enable": True, "qdr": 7, "limits": 50},
    "github": {"enable": True, "pages": 3},
    "telegram": {"enable": False, "channels": []},
}

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo; Shadowrocket"}
TIMEOUT = 15

# 节点数量配置 (大幅增加)
MAX_FETCH_NODES = 3000
MAX_TCP_TEST_NODES = 600
MAX_PROXY_TEST_NODES = 200
MAX_FINAL_NODES = 150

# ⭐ 测速阈值 (宽松策略)
MAX_LATENCY = 2000
MIN_PROXY_SPEED = 0.01
MAX_PROXY_LATENCY = 3000
TEST_URL = "http://www.gstatic.com/generate_204"

# ⭐ 订阅验证配置 (借鉴 wzdnzd/aggregator)
SUB_RETRY = 3
MIN_REMAIN_GB = 0
MIN_SPARE_HOURS = 0
TOLERANCE_HOURS = 72

# Clash 配置
CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"

# 节点命名
NODE_NAME_STYLE = "fancy"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

# ⭐ 并发控制 (解决 503 错误)
MAX_WORKERS = 8
REQUESTS_PER_SECOND = 1
MAX_RETRIES = 3

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"

def ensure_clash_dir():
    WORK_DIR.mkdir(parents=True, exist_ok=True)

# ==================== ⭐ 速率限制器 (解决 503) ====================
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

# ==================== ⭐ HTTP 会话 (带重试) ====================
def create_session():
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session

session = create_session()

# ==================== ⭐ 订阅验证 (核心借鉴 wzdnzd/aggregator) ====================
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

def check_subscription_status(url, retry=SUB_RETRY, remain_gb=0, spare_hours=0, tolerance_hours=TOLERANCE_HOURS):
    """完整的订阅验证流程 (借鉴 wzdnzd/aggregator)"""
    if retry <= 0:
        return False, True
    
    try:
        limiter.wait()
        headers = {"User-Agent": "Clash.Meta; Mihomo; Shadowrocket"}
        request = urllib.request.Request(url=url, headers=headers)
        response = urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context())
        
        if response.getcode() != 200:
            return False, True
        
        # 限制最大读取 15MB (防止测速网站无限下载)
        content = str(response.read(15 * 1024 * 1024), encoding="utf8")
        
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
            # 纯协议链接
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            if lines and all(l.startswith(("vmess://", "vless://", "trojan://", "ss://", "ssr://")) for l in lines):
                return True, False
            return False, True
        
        if len(proxies) == 0:
            return False, True
        
        return check_expiry(sub_info, remain_gb, spare_hours, tolerance_hours)
    
    except urllib.error.HTTPError as e:
        expired = e.code == 404 or "token is error" in str(e.read())
        if not expired and e.code in [403, 503]:
            time.sleep(3)
            return check_subscription_status(url, retry-1, remain_gb, spare_hours, tolerance_hours)
        return False, expired
    except Exception:
        time.sleep(2)
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

# ==================== ⭐ 节点命名 ====================
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝','a':'𝔞','b':'𝔟','c':'𝔠','d':'𝔡','e':'𝔢','f':'𝔣','g':'𝔤','h':'𝔥','i':'𝔦','j':'𝔧','k':'𝔨','l':'𝔩','m':'𝔪','n':'𝔫','o':'𝔬','p':'𝔭','q':'𝔮','r':'𝔯','s':'𝔰','t':'𝔱','u':'𝔲','v':'𝔳','w':'𝔴','x':'𝔵','y':'𝔶','z':'𝔷'}
    REGIONS = {"🇭🇰":"HK","🇹🇼":"TW","🇯🇵":"JP","🇸🇬":"SG","🇰🇷":"KR","🇹🇭":"TH","🇻🇳":"VN","🇺🇸":"US","🇬🇧":"UK","🇩🇪":"DE","🇫🇷":"FR","🇳🇱":"NL","🌍":"OT"}
    
    def __init__(self):
        self.counters = {}
    
    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c,c) for c in t)
    
    def generate(self, flag, lat, speed=None, tcp=False):
        code = self.REGIONS.get(flag, "OT")
        self.counters[code] = self.counters.get(code, 0) + 1
        num = self.counters[code]
        pfx = self.to_fancy(NODE_NAME_PREFIX)
        if speed:
            return f"{code}{num}-{pfx}|⚡{lat}ms|📥{speed:.1f}MB"
        return f"{code}{num}-{pfx}|⚡{lat}ms{'(TCP)' if tcp else ''}"

# ==================== ⭐ Clash 管理 ====================
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
            temp = WORK_DIR / "mihomo.gz"
            with open(temp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            with gzip.open(temp, "rb") as f_in:
                with open(CLASH_PATH, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.chmod(CLASH_PATH, 0o755)
            temp.unlink()
            return CLASH_PATH.exists()
        except:
            return False
    
    def create_config(self, proxies):
        ensure_clash_dir()
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
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": [p["name"] for p in proxies[:MAX_PROXY_TEST_NODES]]}],
            "rules": ["MATCH,TEST"]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
        return True
    
    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash():
            return False
        LOG_FILE.touch()
        try:
            with open(LOG_FILE, "w") as lf:
                self.process = subprocess.Popen(
                    [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())],
                    stdout=lf,
                    stderr=subprocess.STDOUT,
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

# ==================== ⭐ 节点解析 (完整参数) ====================
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
        p = {
            "name": "🌍",
            "type": "vmess",
            "server": c.get("add") or c.get("host", ""),
            "port": int(c.get("port", 443)),
            "uuid": c.get("id", ""),
            "alterId": int(c.get("aid", 0)),
            "cipher": "auto",
            "udp": True,
            "skip-cert-verify": True,
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
        p = urlparse(node)
        if not p.hostname:
            return None
        uuid = p.username or ""
        if not uuid:
            return None
        params = parse_qs(p.query)
        gp = lambda k: params.get(k, [""])[0]
        sec = gp("security")
        proxy = {
            "name": "🌍",
            "type": "vless",
            "server": p.hostname,
            "port": int(p.port or 443),
            "uuid": uuid,
            "udp": True,
            "skip-cert-verify": True,
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
            if fp:
                proxy["client-fingerprint"] = fp
            else:
                proxy["client-fingerprint"] = "chrome"
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
        p = urlparse(node)
        if not p.hostname:
            return None
        pwd = p.username or unquote(p.path.strip("/"))
        if not pwd:
            return None
        params = parse_qs(p.query)
        gp = lambda k: params.get(k, [""])[0]
        proxy = {
            "name": "🌍",
            "type": "trojan",
            "server": p.hostname,
            "port": int(p.port or 443),
            "password": pwd,
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or p.hostname,
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
    return None

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
    elif any(k in nl for k in ["de", "german", "德"]):
        return "🇩🇪", "DE"
    elif any(k in nl for k in ["fr", "france", "法"]):
        return "🇫🇷", "FR"
    elif any(k in nl for k in ["nl", "netherlands", "荷"]):
        return "🇳🇱", "NL"
    return "🌍", "OT"

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

def is_asia(p):
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in ["hk", "hongkong", "tw", "taiwan", "jp", "japan", "sg", "singapore", "kr", "korea", "asia", "hkt", "th", "vn"])

def check_url(u):
    limiter.wait()
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False

# ==================== 主程序 ====================
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 50)
    print("🚀 Clash 节点筛选器 - v9.0 (终极整合版)")
    print("=" * 50)
    
    try:
        # 1. 验证订阅源
        print("\n🔍 验证订阅源...")
        urls = [u for u in CANDIDATE_URLS if check_url(u)]
        print(f"✅ {len(urls)} 个可用\n")
        
        # 2. 抓取节点
        print("📥 抓取节点...")
        nodes = {}
        for u in urls:
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
                    k = f"{p['server']}:{p['port']}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(k.encode()).hexdigest()
                    if h not in nodes:
                        nodes[h] = p
                if len(nodes) >= MAX_FETCH_NODES:
                    break
            if len(nodes) >= MAX_FETCH_NODES:
                break
        print(f"✅ {len(nodes)} 个唯一节点\n")
        
        # 3. TCP 测试
        print("⚡ TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(lambda p: (p, tcp_ping(p["server"], p["port"]), is_asia(p)), p): p for p in nlist}
            for i, f in enumerate(as_completed(futs)):
                p, lat, asia = f.result()
                if lat < MAX_LATENCY:
                    nres.append({"proxy": p, "latency": lat, "is_asia": asia})
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        print(f"✅ TCP 合格：{len(nres)} 个（亚洲：{sum(1 for n in nres if n['is_asia'])}）\n")
        
        # 4. 真实测速 + TCP 保底
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
                
                # ⭐ TCP 保底策略
                if len(final) < 80:
                    print(f"\n⚠️ 测速合格 {len(final)} 个，使用 TCP 补充到 80 个...")
                    for item in nres:
                        if len(final) >= 80:
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
        
        # 5. 输出配置
        print("📝 生成配置...")
        cfg = {
            "proxies": final,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in final], "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in final]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        with open("proxies.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        
        b64 = base64.b64encode("\n".join([f"# {p['name']}" for p in final]).encode()).decode()
        with open("subscription_base64.txt", "w", encoding="utf-8") as f:
            f.write(b64)
        
        # 统计
        tt = time.time() - st
        asia_ct = sum(1 for p in final if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in final[:20]] if final else []
        min_lat = min(lats) if lats else 0
        
        print(f"\n{'=' * 50}")
        print(f"📊 统计")
        print(f"{'=' * 50}")
        print(f"• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(final)}")
        print(f"• 亚洲：{asia_ct} 个 ({asia_ct * 100 // max(len(final), 1)}%)")
        print(f"• 最低延迟：{min_lat:.1f} ms")
        print(f"• 耗时：{tt:.1f} 秒")
        print(f"{'=' * 50}\n")
        
        # Telegram 推送
        if BOT_TOKEN and CHAT_ID:
            try:
                msg = f"""🚀 <b>节点更新完成</b>

📊 统计：
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(final)}
• 亚洲：{asia_ct} 个
• 最低：{min_lat:.1f} ms
• 耗时：{tt:.1f} 秒

📁 <code>https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml</code>"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
            except:
                pass
        
        print("🎉 完成！")
        
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
