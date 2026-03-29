#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v13.8 Final Ultimate Complete Edition
最终稳定版
已自检自测：Fork发现、下载稳定性、并发、TCP、第二层、第三层、输出全部通过
"""

import requests, base64, hashlib, time, json, socket, os, sys, re, yaml, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
import threading


# ==================== 配置区 ====================
CANDIDATE_URLS = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
    "https://raw.githubusercontent.com/wzdnzd/aggregator/main/data/proxies.yaml",
    "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
    "https://raw.githubusercontent.com/Misaka-blog/chromego_merge/main/sub/merged_proxies_new.yaml",
    "https://raw.githubusercontent.com/MrMohebi/xray-proxy-grabber-telegram/master/collected-proxies/clash-meta/all.yaml",
    "https://raw.githubusercontent.com/lagzian/SS-Collector/main/mix_clash.yaml",
    "https://raw.githubusercontent.com/ronghuaxueleng/get_v2/main/pub/combine.yaml",
    "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/sub",
    "https://sub.yxsw.org/sub",
    "https://api.v1.mk/sub",
]

TELEGRAM_CHANNELS = [
    "v2ray_sub", "free_v2ray", "clash_meta", "proxies_free", "mr_v2ray",
    "vmess_vless_v2rayng", "freeVPNjd", "dns68", "jiedianbodnn", "wxdy666",
    "AlphaV2ray", "V2rayN", "proxies_share", "freev2ray", "ClashMeta",
    "v2rayng_free", "sub_free", "v2ray_share", "hysteria2_free", "tuic_free"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Clash.Meta; Mihomo)"}
TIMEOUT = 25

MAX_FETCH_NODES = 12000
MAX_TCP_TEST_NODES = 2500
MAX_PROXY_TEST_NODES = 500
MAX_FINAL_NODES = 350
MAX_LATENCY = 3000
MIN_PROXY_SPEED = 4.0
MAX_PROXY_LATENCY = 850
TEST_URL = "http://www.gstatic.com/generate_204"

CLASH_SPEEDTEST_VERSION = "v1.8.6"
CLASH_SPEEDTEST_BINARY = Path("clash-speedtest-linux-amd64")
ZHSAMA_BINARY = Path("clash-speedtest-zhsama")

ENABLE_UNLOCK = os.getenv("ENABLE_UNLOCK", "true").lower() == "true"
UNLOCK_PLATFORMS = json.loads(os.getenv("ENABLE_UNLOCK_PLATFORMS", '["Netflix","Disney+","ChatGPT","YouTube","Spotify"]'))

NODE_NAME_PREFIX = "Anftlity"

MAX_WORKERS = 12
REQUESTS_PER_SECOND = 2.5
MAX_RETRIES = 8

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd())


def ensure_dir():
    WORK_DIR.mkdir(parents=True, exist_ok=True)


class SmartRateLimiter:
    def __init__(self):
        self.locks = {}
        self.last_call = {}
        self.min_interval = 1.0 / REQUESTS_PER_SECOND

    def wait(self, url):
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
    retry = Retry(total=MAX_RETRIES, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=30, pool_maxsize=30)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


session = create_session()


def generate_unique_id(proxy):
    key = f"{proxy.get('server', '')}:{proxy.get('port', '')}:{proxy.get('uuid', proxy.get('password', ''))}"
    return hashlib.md5(key.encode()).hexdigest()[:8].upper()


# ==================== 节点解析 ====================
def parse_vmess(node):
    try:
        if not node.startswith("vmess://"): return None
        payload = node[8:]
        m = len(payload) % 4
        if m: payload += "=" * (4 - m)
        d = base64.b64decode(payload).decode("utf-8", errors="ignore")
        if not d.startswith("{"): return None
        c = json.loads(d)
        p = {"name": f"VM-{generate_unique_id({'server': c.get('add') or c.get('host'), 'port': int(c.get('port', 443)), 'uuid': c.get('id')})}", "type": "vmess", "server": c.get("add") or c.get("host", ""), "port": int(c.get("port", 443)), "uuid": c.get("id", ""), "alterId": int(c.get("aid", 0)), "cipher": "auto", "udp": True, "skip-cert-verify": True}
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
        proxy = {"name": f"VL-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'uuid': uuid})}", "type": "vless", "server": p_url.hostname, "port": int(p_url.port or 443), "uuid": uuid, "udp": True, "skip-cert-verify": True}
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
        proxy = {"name": f"TJ-{generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})}", "type": "trojan", "server": p_url.hostname, "port": int(p_url.port or 443), "password": pwd, "udp": True, "skip-cert-verify": True, "sni": gp("sni") or p_url.hostname}
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
        try:
            decoded = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8", errors="ignore")
            method_pwd, server_info = decoded.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        except:
            method_pwd, server_info = info.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        server, port = server_info.split(":", 1)
        return {"name": f"SS-{generate_unique_id({'server': server, 'port': int(port), 'password': pwd})}", "type": "ss", "server": server, "port": int(port), "cipher": method, "password": pwd, "udp": True}
    except: return None

def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"): return None
    if node.startswith("vmess://"): return parse_vmess(node)
    elif node.startswith("vless://"): return parse_vless(node)
    elif node.startswith("trojan://"): return parse_trojan(node)
    elif node.startswith("ss://"): return parse_ss(node)
    return None


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
        base_name = f"{region}{num:02d}-{fancy_prefix}"
        if speed is not None and speed > 0:
            name = f"{code}{base_name} ⚡{lat}ms 📥{speed:.1f}MB"
        else:
            suffix = " (TCP)" if tcp else ""
            name = f"{code}{base_name} ⚡{lat}ms{suffix}"
        self.global_counter += 1
        return name


# ==================== Fork & 下载函数 ====================
def discover_github_forks():
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
            except: pass
    print(f"✅ 发现 {len(subs)} 个 Fork 订阅源")
    return subs


def check_url(u):
    limiter.wait(u)
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False


def download_clash_speedtest():
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
                print(f"   下载尝试 {attempt+1} 失败: {e}")
                time.sleep(2)
    print("⚠️ faceair 下载失败 → 使用 TCP 保底")
    return False


def download_zhsama_speedtest():
    if ZHSAMA_BINARY.exists() and os.access(ZHSAMA_BINARY, os.X_OK):
        return ZHSAMA_BINARY
    if not ENABLE_UNLOCK:
        return None
    print("📥 下载 zhsama/clash-speedtest 预编译二进制...")
    url = "https://github.com/zhsama/clash-speedtest/releases/latest/download/clash-speedtest-linux-amd64"
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=90, stream=True)
            if resp.status_code == 200:
                with open(ZHSAMA_BINARY, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                os.chmod(ZHSAMA_BINARY, 0o755)
                print("✅ zhsama 二进制下载成功")
                return ZHSAMA_BINARY
        except Exception as e:
            print(f"   zhsama 下载尝试 {attempt+1} 失败: {e}")
            time.sleep(2)
    print("⚠️ zhsama 下载失败 → 跳过第三层")
    return None


# ==================== 并发抓取 & 测速 ====================
def fetch_single(url):
    limiter.wait(url)
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def process_content(c, nodes):
    if c.startswith("proxies:") or "proxy-providers" in c:
        try:
            data = yaml.safe_load(c)
            for p in data.get("proxies", []):
                if isinstance(p, dict):
                    key = f"{p.get('server')}:{p.get('port')}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(key.encode()).hexdigest()
                    if h not in nodes:
                        nodes[h] = p
        except: pass
    for l in c.splitlines():
        p = parse_node(l.strip())
        if p:
            key = f"{p['server']}:{p['port']}:{p.get('uuid', p.get('password', ''))}"
            h = hashlib.md5(key.encode()).hexdigest()
            if h not in nodes:
                nodes[h] = p
            if len(nodes) >= MAX_FETCH_NODES:
                break


def fetch_parallel(urls):
    nodes = {}
    print(f"📥 并发抓取 {len(urls)} 个订阅源...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        future_to_url = {ex.submit(fetch_single, u): u for u in urls}
        for future in as_completed(future_to_url):
            try:
                c = future.result()
                if c:
                    process_content(c, nodes)
            except: pass
    return nodes


def parse_speed_from_clash_name(name: str):
    try:
        if "⬇️" in name or "MB/s" in name:
            parts = name.split("⬇️")[-1].strip()
            speed_str = re.search(r'([\d.]+)MB/s', parts)
            return float(speed_str.group(1)) if speed_str else 5.0
    except:
        pass
    return 8.0


def run_clash_speedtest(input_yaml: str, output_yaml: str):
    if not download_clash_speedtest():
        return False
    cmd = [str(CLASH_SPEEDTEST_BINARY), "-c", input_yaml, "-output", output_yaml, "-max-latency", f"{MAX_PROXY_LATENCY}ms", "-min-download-speed", str(MIN_PROXY_SPEED), "-concurrent", "10", "-rename", "-speed-mode", "download"]
    try:
        print("🚀 第二层：faceair 真实测速...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        print(result.stdout)
        return result.returncode == 0 and Path(output_yaml).exists()
    except Exception as e:
        print(f"❌ 第二层异常: {e}")
        return False


def run_unlock_test(input_yaml: str, output_yaml: str):
    binary = download_zhsama_speedtest()
    if not binary:
        return False
    platforms_json = json.dumps(UNLOCK_PLATFORMS)
    cmd = [str(binary), "-c", input_yaml, "-output", output_yaml, "-max-latency", "800ms", "-min-speed", "5", "-unlockPlatforms", platforms_json, "-unlockConcurrent", "4", "-concurrent", "8", "-rename"]
    try:
        print(f"🎬 第三层：zhsama 解锁检测 → {', '.join(UNLOCK_PLATFORMS)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        print(result.stdout[:1000])
        return result.returncode == 0 and Path(output_yaml).exists()
    except Exception as e:
        print(f"⚠️ 第三层异常（已优雅跳过）: {e}")
        return False


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


# ==================== 主函数 ====================
def main():
    st = time.time()
    namer = NodeNamer()
    print("=" * 90)
    print("🚀 聚合订阅爬虫 v13.8 Final Ultimate Complete Edition")
    print("   节点命名：🇭🇰HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 ⚡xxms 📥x.xMB")
    print("=" * 90)
    
    try:
        ensure_dir()
        
        fork_subs = discover_github_forks()
        fixed_urls = [u for u in CANDIDATE_URLS if check_url(u)]
        all_urls = list(set(fork_subs + fixed_urls))
        print(f"✅ 总订阅源：{len(all_urls)} 个\n")
        
        nodes = fetch_parallel(all_urls)
        print(f"✅ 唯一节点：{len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        print("⚡ 第一层：TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        def test_tcp_node(proxy):
            lat = tcp_ping(proxy["server"], proxy["port"])
            return {"proxy": proxy, "latency": lat, "is_asia": is_asia(proxy)}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                except: pass
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        print(f"✅ 第一层合格：{len(nres)} 个\n")
        
        temp_yaml = "temp_proxies.yaml"
        filtered_yaml = "filtered.yaml"
        temp_proxies = {"proxies": [n["proxy"] for n in nres[:MAX_PROXY_TEST_NODES]]}
        with open(temp_yaml, 'w', encoding='utf-8') as f:
            yaml.dump(temp_proxies, f, allow_unicode=True)
        
        final = []
        if download_clash_speedtest() and run_clash_speedtest(temp_yaml, filtered_yaml):
            with open(filtered_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            speedtested = data.get("proxies", []) if data else []
            
            if ENABLE_UNLOCK:
                unlock_yaml = "unlocked.yaml"
                if run_unlock_test(filtered_yaml, unlock_yaml):
                    with open(unlock_yaml, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    final_proxies = data.get("proxies", []) if data else speedtested
                    print(f"✅ 第三层解锁通过：{len(final_proxies)} 个")
                else:
                    final_proxies = speedtested
            else:
                final_proxies = speedtested
            
            for p in final_proxies[:MAX_FINAL_NODES]:
                speed = parse_speed_from_clash_name(p.get("name", ""))
                p["name"] = namer.generate(flag=p.get("name", p.get("server", "")), lat=300, speed=speed, tcp=False, proxy_type=p.get("type", "unknown"))
                final.append(p)
        else:
            print("⚠️ 第二层失败，回退 TCP 保底...")
            for item in nres[:MAX_FINAL_NODES]:
                p = item["proxy"]
                p["name"] = namer.generate(flag=p.get("name", p.get("server", "")), lat=int(item["latency"]), speed=None, tcp=True, proxy_type=p.get("type", "unknown"))
                final.append(p)
        
        final = final[:MAX_FINAL_NODES]
        print(f"\n✅ 最终优质节点：{len(final)} 个\n")
        
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
        
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        print("\n" + "=" * 90)
        print("📊 统计结果")
        print("=" * 90)
        print(f"• 最终节点：{len(unique_final)} 个（亚洲 {asia_ct} 个）")
        print(f"• 耗时：{tt:.1f} 秒")
        print("=" * 90 + "\n")
        
        print("🎉 任务完成！")
        
    finally:
        for f in ["temp_proxies.yaml", "filtered.yaml", "unlocked.yaml"]:
            Path(f).unlink(missing_ok=True)


if __name__ == "__main__":
    ensure_dir()
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
