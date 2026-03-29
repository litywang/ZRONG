#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v13.0 Optimized - 完全可用版
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
    # 原有高质量源（保留）
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
    "https://shz.al/~WangCai",
    # 新增活跃源（2025-2026 推荐）
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_extracted_configs.txt",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/sub",
    "https://raw.githubusercontent.com/anaer/Sub/main/sub",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://sub.yxsw.org/sub",
    "https://api.v1.mk/sub",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
    "https://raw.githubusercontent.com/freefq/free/master/v2ray",
    "https://raw.githubusercontent.com/wzdnzd/aggregator/main/data/proxies.yaml",
]

TELEGRAM_CHANNELS = [
    "v2ray_sub", "free_v2ray", "clash_meta", "proxies_free", "mr_v2ray",
    "vmess_vless_v2rayng", "freeVPNjd", "dns68", "jiedianbodnn", "wxdy666",
    # 新增活跃频道（显著提升订阅量）
    "AlphaV2ray", "V2rayN", "proxies_share", "freev2ray", "ClashMeta", 
    "v2rayng_free", "sub_free", "v2ray_share", "hysteria2_free", "tuic_free"
]

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo"}
TIMEOUT = 30

MAX_FETCH_NODES = 8000          # 大幅提升
MAX_TCP_TEST_NODES = 2000       # 大幅提升
MAX_PROXY_TEST_NODES = 400      # 大幅提升
MAX_FINAL_NODES = 300           # 大幅提升（目标 300+ 可用节点）
MAX_LATENCY = 3000
MIN_PROXY_SPEED = 0.005         # 略微放宽，保留更多节点
MAX_PROXY_LATENCY = 3000
TEST_URL = "http://www.gstatic.com/generate_204"

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "Anftlity"   # 保留品牌，用于花体

MAX_WORKERS = 8                 # 提升并发
REQUESTS_PER_SECOND = 1.0       # 略微加快爬取
MAX_RETRIES = 5

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"


def ensure_clash_dir():
    """✅ 安全创建目录"""
    if WORK_DIR.exists() and not WORK_DIR.is_dir():
        WORK_DIR.unlink()
    WORK_DIR.mkdir(parents=True, exist_ok=True)


class RateLimiter:
    def __init__(self):
        self.min_interval = 1.0 / REQUESTS_PER_SECOND
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
    """✅ 生成唯一代理ID"""
    key = f"{proxy.get('server', '')}:{proxy.get('port', '')}:{proxy.get('uuid', proxy.get('password', ''))}"
    return hashlib.md5(key.encode()).hexdigest()[:8].upper()


def parse_vmess(node):
    try:
        if not node.startswith("vmess://"): return None
        payload = node[8:]
        m = len(payload) % 4
        if m: payload += "=" * (4 - m)
        d = base64.b64decode(payload).decode("utf-8", errors="ignore")
        if not d.startswith("{"): return None
        c = json.loads(d)
        p = {
            "name": f"VM-{generate_unique_id({'server': c.get('add') or c.get('host'), 'port': int(c.get('port', 443)), 'uuid': c.get('id')})}",
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
    except:
        return None


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
        proxy = {
            "name": f"VL-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'uuid': uuid})}",
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
        if flow: proxy["flow"] = flow
        tp = gp("type")
        if tp == "ws":
            proxy["network"] = "ws"
            wo = {}
            if gp("path"): wo["path"] = gp("path")
            if gp("host"): wo["headers"] = {"Host": gp("host")}
            if wo: proxy["ws-opts"] = wo
        return proxy
    except:
        return None


def parse_trojan(node):
    try:
        if not node.startswith("trojan://"): return None
        p_url = urlparse(node)
        if not p_url.hostname: return None
        pwd = p_url.username or unquote(p_url.path.strip("/"))
        if not pwd: return None
        params = parse_qs(p_url.query)
        gp = lambda k: params.get(k, [""])[0]
        proxy = {
            "name": f"TJ-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})}",
            "type": "trojan",
            "server": p_url.hostname,
            "port": int(p_url.port or 443),
            "password": pwd,
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or p_url.hostname
        }
        alpn = gp("alpn")
        if alpn: proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        fp = gp("fp")
        if fp: proxy["client-fingerprint"] = fp
        return proxy
    except:
        return None


def parse_ss(node):
    try:
        if not node.startswith("ss://"): return None
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
        return {
            "name": f"SS-{generate_unique_id({'server': server, 'port': int(port), 'password': pwd})}",
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
    if not node or node.startswith("#"): return None
    if node.startswith("vmess://"): return parse_vmess(node)
    elif node.startswith("vless://"): return parse_vless(node)
    elif node.startswith("trojan://"): return parse_trojan(node)
    elif node.startswith("ss://"): return parse_ss(node)
    return None


def discover_github_forks(base_repo="wzdnzd/aggregator", max_forks=80):
    """✅ 新增：GitHub Fork 动态发现（wzdnzd/aggregator 核心优化）"""
    print("🔍 动态发现 GitHub Forks...")
    url = f"https://api.github.com/repos/{base_repo}/forks?per_page=100&sort=newest"
    forks = []
    for page in range(1, 6):
        try:
            resp = session.get(url + f"&page={page}", timeout=15)
            if resp.status_code != 200: break
            forks.extend([f for f in resp.json() if f.get("fork")])
        except:
            break
    subs = []
    for f in forks[:max_forks]:
        fullname, branch = f["full_name"], f.get("default_branch", "main")
        for path in ["data/proxies.yaml", "proxies.yaml", "aggregate/data/proxies.yaml", "data/subscribes.txt", "sub/splitted/vless.txt", "sub/splitted/vmess.txt"]:
            raw_url = f"https://raw.githubusercontent.com/{fullname}/{branch}/{path}"
            if check_url(raw_url):
                subs.append(raw_url)
    print(f"✅ 发现 {len(subs)} 个 Fork 订阅源")
    return subs


def get_telegram_pages(channel):
    try:
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=TIMEOUT).text
        regex = rf'<link\s+rel="canonical"\s+href="/s/{channel}?before=(\d+)">'
        groups = re.findall(regex, content)
        return int(groups[0]) if groups else 0
    except:
        return 0


def crawl_telegram_page(url, limits=50):
    try:
        limiter.wait()
        content = session.get(url, timeout=TIMEOUT).text
        sub_regex = r'https?://[a-zA-Z0-9._-]+(?:\.[a-zA-Z0-9._-]+)+(?::\d+)?[^"\s<>]*?(?:sub|link|clash|base64|yaml)[^"\s<>]*'
        links = re.findall(sub_regex, content)
        collections = {}
        for link in links[:limits]:
            link = link.replace("http://", "https://", 1)
            if any(k in link for k in ["token=", "/link/", "sub", "clash"]):
                collections[link] = {"origin": "TELEGRAM"}
        return collections
    except:
        return {}


def crawl_telegram_channels(channels, pages=5, limits=50):
    all_subscribes = {}
    for channel in channels:
        try:
            count = get_telegram_pages(channel)
            if count == 0: continue
            page_arrays = range(count, -1, -100)
            page_num = min(pages, len(page_arrays))
            for i, before in enumerate(page_arrays[:page_num]):
                url = f"https://t.me/s/{channel}?before={before}"
                result = crawl_telegram_page(url, limits=limits)
                all_subscribes.update(result)
                print(f"✅ Telegram频道 {channel} 第{i+1}页：{len(result)} 个订阅")
                time.sleep(0.8)
        except Exception as e:
            print(f"❌ Telegram频道 {channel}: {e}")
            continue
    return all_subscribes


def fetch(url):
    limiter.wait()
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def check_url(u):
    limiter.wait()
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False


def tcp_ping(host, port, to=2.0):
    if not host: return 9999
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(to)
        st = time.time()
        s.connect((host, port))
        s.close()
        return round((time.time() - st) * 1000, 1)
    except:
        return 9999


def is_base64_encode(content):
    try:
        content = content.strip()
        if len(content) < 10: return False
        base64.b64decode(content + "=" * (4 - len(content) % 4), validate=True)
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


def get_region(name):
    nl = name.lower()
    if any(k in nl for k in ["hk", "hongkong", "港"]): return "🇭🇰", "HK"
    elif any(k in nl for k in ["tw", "taiwan", "台"]): return "🇹🇼", "TW"
    elif any(k in nl for k in ["jp", "japan", "日"]): return "🇯🇵", "JP"
    elif any(k in nl for k in ["sg", "singapore", "新"]): return "🇸🇬", "SG"
    elif any(k in nl for k in ["kr", "korea", "韩"]): return "🇰🇷", "KR"
    elif any(k in nl for k in ["us", "usa", "美"]): return "🇺🇸", "US"
    return "🌍", "OT"


def is_asia(p):
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in ["hk", "tw", "jp", "sg", "kr", "asia"])


class NodeNamer:
    """✅ 优化节点命名器 - 完全符合您要求：HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 风格（保留花体）"""
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝'}
    
    def __init__(self):
        self.counters = {}
        self.global_counter = 0

    def to_fancy(self, t):
        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat, speed=None, tcp=False, proxy_type="unknown"):
        code, region = get_region(flag)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        fancy_prefix = self.to_fancy(NODE_NAME_PREFIX)
        
        # 核心命名风格：HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
        base_name = f"{region}{num:02d}-{fancy_prefix}"
        
        # 添加质量信息（优化后更丰富但不破坏风格）
        if speed is not None and speed > 0:
            name = f"{code}{base_name} ⚡{lat}ms 📥{speed:.1f}MB"
        else:
            suffix = " (TCP)" if tcp else ""
            name = f"{code}{base_name} ⚡{lat}ms{suffix}"
        
        # 全局唯一性兜底
        self.global_counter += 1
        return name


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
            with open(temp, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            with gzip.open(temp, 'rb') as f_in:
                with open(CLASH_PATH, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.chmod(CLASH_PATH, 0o755)
            temp.unlink(missing_ok=True)
            return CLASH_PATH.exists()
        except:
            return False

    def create_config(self, proxies):
        ensure_clash_dir()
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
            "log-level": "error",
            "external-controller": f"127.0.0.1:{CLASH_API_PORT}",
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
            cmd = [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid, cwd=str(WORK_DIR.absolute()))
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
            self.process = None

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
                try:
                    sp_resp = requests.get("https://speed.cloudflare.com/__down?bytes=524288", proxies=px, timeout=15)
                    sp = len(sp_resp.content) / max(0.5, time.time() - sp_start) / (1024 * 1024)
                    result = {"success": True, "latency": round(lat, 1), "speed": round(sp, 2), "error": ""}
                except:
                    result["speed"] = 0.0
            else:
                result["error"] = f"Status:{resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:80]
        return result


def format_proxy_to_link(p):
    try:
        if p["type"] == "vmess":
            data = {"v": "2", "ps": p["name"], "add": p["server"], "port": p["port"], "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"), "type": "none", "host": p.get("sni", ""), "path": p.get("ws-opts", {}).get("path", ""), "tls": "tls" if p.get("tls") else ""}
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
        return f"# {p['name']}"
    except:
        return f"# {p['name']}"


def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 60)
    print("🚀 聚合订阅爬虫 v13.0 Optimized（节点命名：HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 风格）")
    print("=" * 60)
    
    try:
        # 1. GitHub Fork 动态发现 + Telegram + 固定源
        print("\n🔍 动态发现 GitHub Forks...")
        fork_subs = discover_github_forks()
        
        print("\n📱 爬取 Telegram 频道...")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=5, limits=50)
        tg_urls = list(tg_subs.keys())
        
        print("🔍 验证固定订阅源...")
        fixed_urls = [u for u in CANDIDATE_URLS if check_url(u)]
        
        all_urls = tg_urls + fork_subs + fixed_urls
        all_urls = list(set(all_urls))  # 去重
        print(f"✅ 总订阅源：{len(all_urls)} 个（Telegram:{len(tg_urls)} | Fork:{len(fork_subs)} | 固定:{len(fixed_urls)}）\n")
        
        # 2. 抓取节点（支持 YAML）
        print("📥 抓取节点...")
        nodes = {}
        for u in all_urls:
            c = fetch(u)
            if not c: continue
            if is_base64_encode(c):
                c = decode_b64(c)
            # 支持 YAML 格式
            if c.startswith("proxies:") or "proxy-providers" in c:
                try:
                    data = yaml.safe_load(c)
                    for p in data.get("proxies", []):
                        if isinstance(p, dict):
                            key = f"{p.get('server')}:{p.get('port')}:{p.get('uuid', p.get('password', ''))}"
                            h = hashlib.md5(key.encode()).hexdigest()
                            if h not in nodes:
                                nodes[h] = p
                except:
                    pass
            for l in c.splitlines():
                l = l.strip()
                if not l or l.startswith("#"): continue
                p = parse_node(l)
                if p:
                    key = f"{p['server']}:{p['port']}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(key.encode()).hexdigest()
                    if h not in nodes:
                        nodes[h] = p
                if len(nodes) >= MAX_FETCH_NODES:
                    break
            if len(nodes) >= MAX_FETCH_NODES:
                break
        print(f"✅ 唯一节点：{len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        # 3. TCP 测试
        print("⚡ TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        
        def test_tcp_node(proxy):
            lat = tcp_ping(proxy["server"], proxy["port"])
            return {"proxy": proxy, "latency": lat, "is_asia": is_asia(proxy)}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=TIMEOUT + 10)
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                    completed += 1
                    if completed % 100 == 0:
                        print(f"   进度：{completed}/{len(nlist)} | 合格：{len(nres)}")
                except:
                    continue
        
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in nres if n["is_asia"])
        print(f"✅ TCP 合格：{len(nres)} 个（亚洲：{asia_count}）\n")
        
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
                            p["name"] = namer.generate(
                                flag=p.get("name", p.get("server", "")),
                                lat=int(r["latency"]),
                                speed=r["speed"],
                                tcp=False,
                                proxy_type=p["type"]
                            )
                            final.append(p)
                            tested.add(k)
                            print(f"   ✅ {p['name']}")
                    
                    if len(final) >= MAX_FINAL_NODES:
                        break
                    
                    if (i + 1) % 20 == 0:
                        print(f"   进度：{i + 1}/{min(len(nres), MAX_PROXY_TEST_NODES)} | 合格：{len(final)}")
                
                clash.stop()
                
                # TCP补充
                if len(final) < MAX_FINAL_NODES:
                    print(f"\n⚠️ 测速合格 {len(final)} 个，使用 TCP 补充...")
                    for item in nres:
                        if len(final) >= MAX_FINAL_NODES:
                            break
                        p = item["proxy"]
                        k = f"{p['server']}:{p['port']}"
                        if k in tested: continue
                        if (item["is_asia"] and item["latency"] < 600) or item["latency"] < 300:
                            p["name"] = namer.generate(
                                flag=p.get("name", p.get("server", "")),
                                lat=int(item["latency"]),
                                speed=None,
                                tcp=True,
                                proxy_type=p["type"]
                            )
                            final.append(p)
                            tested.add(k)
                            print(f"   📌 {p['name']} (TCP)")
            else:
                print("⚠️ Clash 启动失败，使用 TCP 筛选...")
                for item in nres[:MAX_FINAL_NODES * 2]:
                    if len(final) >= MAX_FINAL_NODES: break
                    p = item["proxy"]
                    k = f"{p['server']}:{p['port']}"
                    if k in tested: continue
                    if (item["is_asia"] and item["latency"] < 600) or item["latency"] < 300:
                        p["name"] = namer.generate(
                            flag=p.get("name", p.get("server", "")),
                            lat=int(item["latency"]),
                            speed=None,
                            tcp=True,
                            proxy_type=p["type"]
                        )
                        final.append(p)
                        tested.add(k)
        
        final = final[:MAX_FINAL_NODES]
        print(f"\n✅ 最终：{len(final)} 个节点")
        print(f"📊 真实测速：{'✅' if proxy_ok else '❌'}\n")
        
        # 5. 输出配置（确保名称唯一）
        print("📝 生成配置...")
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
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in unique_final], "url": TEST_URL, "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in unique_final]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        with open("proxies.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        
        b64_lines = [format_proxy_to_link(p) for p in unique_final]
        with open("subscription.txt", 'w', encoding='utf-8') as f:
            f.write('\n'.join(b64_lines))
        
        # 统计
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in unique_final[:20]] if unique_final else []
        min_lat = min(lats) if lats else 0
        
        print("\n" + "=" * 60)
        print("📊 统计结果")
        print("=" * 60)
        print(f"• 订阅源：Telegram {len(tg_urls)} | Fork {len(fork_subs)} | 固定 {len(fixed_urls)} | 总 {len(all_urls)}")
        print(f"• 原始节点 {len(nodes)} | TCP {len(nres)} | 最终 {len(unique_final)}")
        print(f"• 亚洲节点 {asia_ct} 个 ({asia_ct * 100 // max(len(unique_final), 1)}%)")
        print(f"• 最低延迟 {min_lat:.1f} ms")
        print(f"• 耗时 {tt:.1f} 秒")
        print("=" * 60 + "\n")
        
        # Telegram推送
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                msg = f"""🚀 <b>节点更新完成 v13.0 Optimized</b>

📊 统计:
• 订阅源：{len(all_urls)} 个
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}
• 亚洲：{asia_ct} 个
• 最低：{min_lat:.1f} ms
• 耗时：{tt:.1f} 秒

📁 YAML: https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml
📄 TXT: https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt

节点命名风格：HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
                print("✅ Telegram通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram推送失败: {e}")
        
        print("🎉 任务完成！节点命名已采用 HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 风格")
        
    finally:
        clash.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
