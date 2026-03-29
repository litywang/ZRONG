#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v11.0 - 最终稳定版
适用: GitHub Actions / 本地 Python 3.9+
修复点: f-string 语法 + Clash启动 + Telegram爬取
"""

import os, sys, json, time, re, yaml, gzip, shutil, ssl, hashlib, base64, socket, signal, subprocess, threading, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse, unquote, parse_qs
import requests

# ==================== 配置区 ====================
CANDIDATE_URLS = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
    "https://shz.al/~WangCai",
]

TELEGRAM_CHANNELS = ["proxies_free", "mr_v2ray", "dns68"]

TIMEOUT = 30
MAX_FETCH_NODES = 1500
MAX_TCP_TEST_NODES = 300
MAX_PROXY_TEST_NODES = 100
MAX_FINAL_NODES = 80
MAX_LATENCY = 1500
MIN_PROXY_SPEED = 0.02
MAX_PROXY_LATENCY = 3000
TEST_URL = "http://www.gstatic.com/generate_204"

MAX_WORKERS = 3
REQUESTS_PER_SECOND = 0.5
MAX_RETRIES = 5

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "Anftli"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"


def ensure_clash_dir():
    WORK_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 速率限制器 ====================
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


# ==================== HTTP 会话 ====================
def create_session():
    session = requests.Session()
    retry = Retry(total=MAX_RETRIES, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo"})
    return session


session = create_session()


# ==================== 辅助工具 ====================
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
        resp = session.get(url, timeout=TIMEOUT)
        return resp.text.strip()
    except:
        return ""


def check_url(u):
    limiter.wait()
    try:
        resp = session.head(u, timeout=TIMEOUT, allow_redirects=True)
        return resp.status_code in (200, 301, 302)
    except:
        return False


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
    elif any(k in nl for k in ["us", "usa", "美"]):
        return "🇺🇸", "US"
    return "🌍", "OT"


def is_asia(p):
    t = f"{p.get('name', '')} {p.get('server', '')}".lower()
    return any(k in t for k in ["hk", "tw", "jp", "sg", "kr", "asia"])


# ==================== 协议解析器 ====================
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
        proxy = {
            "name": "🌍",
            "type": "vmess",
            "server": c.get("add", ""),
            "port": int(c.get("port", 443)),
            "uuid": c.get("id", ""),
            "alterId": int(c.get("aid", 0)),
            "cipher": "auto",
            "udp": True,
            "skip-cert-verify": True
        }
        net = c.get("net", "tcp").lower()
        if net in ["ws", "h2", "grpc"]:
            proxy["network"] = net
        if c.get("tls") == "tls" or c.get("security") == "tls":
            proxy["tls"] = True
            proxy["sni"] = c.get("sni") or c.get("host") or proxy["server"]
        if net == "ws":
            ws_opts = {}
            if c.get("path"):
                ws_opts["path"] = c.get("path")
            if c.get("host"):
                ws_opts["headers"] = {"Host": c.get("host")}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        return proxy if proxy["server"] and proxy["uuid"] else None
    except:
        return None


def parse_vless(node):
    try:
        if not node.startswith("vless://"):
            return None
        p = urlparse(node)
        if not p.hostname:
            return None
        uuid = p.username
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
            ws_opts = {}
            if gp("path"):
                ws_opts["path"] = gp("path")
            if gp("host"):
                ws_opts["headers"] = {"Host": gp("host")}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
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
            "sni": gp("sni") or p.hostname
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
        return {
            "name": "🌍",
            "type": "ss",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": pwd,
            "udp": True
        }
    except:
        return None


def parse_hysteria2(node):
    try:
        if not node.startswith("hysteria2://"):
            return None
        p = urlparse(node)
        if not p.hostname:
            return None
        pwd = unquote(p.username or "")
        params = parse_qs(p.query)
        gp = lambda k: params.get(k, [""])[0]
        return {
            "name": "🌍",
            "type": "hysteria2",
            "server": p.hostname,
            "port": int(p.port or 443),
            "password": pwd or gp("auth"),
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or p.hostname
        }
    except:
        return None


def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"):
        return None
    parsers = {
        "vmess://": parse_vmess,
        "vless://": parse_vless,
        "trojan://": parse_trojan,
        "ss://": parse_ss,
        "hysteria2://": parse_hysteria2
    }
    for prefix, parser in parsers.items():
        if node.startswith(prefix):
            return parser(node)
    return None


# ==================== NodeNamer ====================
class NodeNamer:
    def __init__(self):
        self.counters = {}

    def generate(self, flag, lat, speed=None, tcp=False):
        code, region = get_region(flag)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        if speed:
            return f"{code}{num}-{NODE_NAME_PREFIX}|⚡{lat}ms|📥{speed:.1f}MB"
        return f"{code}{num}-{NODE_NAME_PREFIX}|⚡{lat}ms{'(TCP)' if tcp else ''}"


# ==================== Clash 管理器 ====================
class ClashManager:
    def __init__(self):
        self.process = None
        ensure_clash_dir()

    def download_clash(self):
        if CLASH_PATH.exists():
            return True
        urls = [
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz",
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-{CLASH_VERSION}.gz",
            "https://cdn.jsdelivr.net/gh/MetaCubeX/mihomo@alpha/prebuilt/mihomo-linux-amd64.gz",
        ]
        for url in urls:
            try:
                print(f"   下载中: {url[:50]}...")
                resp = session.get(url, timeout=120, stream=True)
                if resp.status_code != 200:
                    continue
                temp = WORK_DIR / "mihomo.gz"
                with open(temp, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                if os.path.getsize(temp) < 1000000:
                    print("   ⚠️ 下载内容过小，跳过")
                    temp.unlink(missing_ok=True)
                    continue
                with gzip.open(temp, 'rb') as f_in:
                    with open(CLASH_PATH, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.chmod(CLASH_PATH, 0o755)
                temp.unlink()
                print("   ✅ Clash下载完成")
                return True
            except Exception as e:
                print(f"   ⚠️ 下载失败: {e}")
                continue
        print("   ❌ 所有下载源均失败")
        return False

    def create_config(self, proxies):
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
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
        return True

    def start(self):
        if not CLASH_PATH.exists() and not self.download_clash():
            return False
        self.stop()
        LOG_FILE.touch()
        try:
            cmd = [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid, cwd=str(WORK_DIR.absolute()))
            for i in range(30):
                time.sleep(1)
                if self.process.poll() is not None:
                    try:
                        out, _ = self.process.communicate(timeout=2)
                        print(f"   ❌ Clash崩溃:\n{out[:300]}")
                    except:
                        print("   ❌ Clash崩溃 (无日志)")
                    return False
                try:
                    if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                        print("   ✅ Clash API就绪")
                        return True
                except:
                    pass
            print("   ⏱️ Clash启动超时")
            return False
        except Exception as e:
            print(f"   💥 Clash启动异常: {e}")
            return False

    def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
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


# ==================== Telegram 爬取 ====================
def crawl_telegram_channels(channels, pages=2, limits=20):
    all_subscribes = {}
    for channel in channels:
        try:
            limiter.wait()
            url = f"https://t.me/s/{channel}?before={pages * 100}"
            content = session.get(url, timeout=TIMEOUT).text
            sub_regex = r'https?://(?:[a-zA-Z0-9\u4e00-\u9fa5\-]+\.)+[a-zA-Z0-9\u4e00-\u9fa5\-]+(?::\d+)?[^"\s<>]'
            links = re.findall(sub_regex, content)
            protocol_prefixes = ("raw.githubusercontent.com/", "github.com/")
            count = 0
            for link in links[:limits]:
                link = link.replace("http://", "https://", 1)
                if any(link.startswith(p) for p in protocol_prefixes):
                    if "?" in link:
                        all_subscribes[link] = {"origin": "TELEGRAM"}
                        count += 1
            print(f"✅ 频道 {channel}: 发现 {count} 个订阅")
            time.sleep(1)
        except Exception as e:
            print(f"❌ 频道 {channel}: {e}")
            continue
    return all_subscribes


# ==================== 主程序 ====================
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    final_nodes = []
    tested_keys = set()
    proxy_ok = False

    print("=" * 50)
    print("🚀 聚合订阅爬虫 v11.0 (最终稳定版)")
    print("=" * 50)

    try:
        # 1. 收集订阅源
        print("\n🔗 收集订阅源...")
        all_urls = []
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=2, limits=15)
        tg_urls = list(tg_subs.keys())
        all_urls.extend(tg_urls)
        print(f"✅ Telegram: {len(tg_urls)} 个订阅")

        fixed_urls = [u for u in CANDIDATE_URLS if check_url(u)]
        all_urls.extend(fixed_urls)
        print(f"✅ 固定源: {len(fixed_urls)} 个可用\n")

        all_urls = list(set(all_urls))
        print(f"📊 总计: {len(all_urls)} 个订阅源\n")

        # 2. 抓取节点
        print("📥 抓取节点...")
        nodes = {}

        def fetch_valid_nodes(url):
            result = {}
            content = fetch(url)
            if not content:
                return result
            if is_base64(content):
                content = decode_b64(content)
            valid_prefixes = ("vmess://", "vless://", "trojan://", "ss://", "hysteria2://")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if not any(line.startswith(p) for p in valid_prefixes):
                    continue
                p = parse_node(line)
                if p and p.get("server") and p.get("port"):
                    key = f"{p['server']}:{p['port']}"
                    h = hashlib.md5(key.encode()).hexdigest()
                    if h not in result:
                        result[h] = p
            return result

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_valid_nodes, u): u for u in all_urls}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    nodes.update(result)
                except:
                    pass
                if len(nodes) >= MAX_FETCH_NODES:
                    break

        print(f"✅ 唯一节点: {len(nodes)} 个\n")
        if not nodes:
            print("❌ 无有效节点!")
            return

        # 3. TCP 测试 (已修复 lambda 语法)
        print("⚡ TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        tcp_results = []

        def test_tcp_node(proxy):
            """独立任务函数"""
            lat = tcp_ping(proxy["server"], proxy["port"])
            return {"proxy": proxy, "latency": lat, "is_asia": is_asia(proxy), "status": "OK" if lat < MAX_LATENCY else "FAIL"}

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(test_tcp_node, p): p for p in nlist}
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=TIMEOUT + 10)
                    if result["status"] == "OK":
                        tcp_results.append(result)
                    completed += 1
                    if completed % 50 == 0:
                        print(f"   进度：{completed}/{len(nlist)} | 合格：{len(tcp_results)}")
                except:
                    continue

        tcp_results.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in tcp_results if n["is_asia"])
        print(f"✅ TCP 合格: {len(tcp_results)} 个（亚洲：{asia_count}）\n")

        # 4. 真实测速 + TCP 保底
        print("🚀 真实代理测速...")

        if len(tcp_results) > 0:
            tprox = [n["proxy"] for n in tcp_results[:MAX_PROXY_TEST_NODES]]
            if clash.create_config(tprox) and clash.start():
                proxy_ok = True
                print("📊 测速中...\n")
                progress = 0
                for item in tcp_results[:MAX_PROXY_TEST_NODES]:
                    p = item["proxy"]
                    r = clash.test_proxy(p["name"])
                    k = f"{p['server']}:{p['port']}"
                    if r["success"] and r["latency"] < MAX_PROXY_LATENCY:
                        if r["speed"] >= MIN_PROXY_SPEED or r["latency"] < 500:
                            fl, cd = get_region(p.get("name", " "))
                            p["name"] = namer.generate(fl, int(r["latency"]), r["speed"], tcp=False)
                            final_nodes.append(p)
                            tested_keys.add(k)
                            progress += 1
                            print(f"   ✅ {p['name']}")
                    if len(final_nodes) >= MAX_FINAL_NODES:
                        break
                clash.stop()
            else:
                print("⚠️ Clash 启动失败，使用 TCP 保底")

        # 5. TCP 补充
        if len(final_nodes) < 30:
            print("使用 TCP 测试节点补充...")
            for item in tcp_results:
                if len(final_nodes) >= MAX_FINAL_NODES:
                    break
                p = item["proxy"]
                k = f"{p['server']}:{p['port']}"
                if k in tested_keys:
                    continue
                if item["is_asia"] and item["latency"] < 600:
                    fl, cd = get_region(p.get("name", " "))
                    p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                    final_nodes.append(p)
                    tested_keys.add(k)
                    print(f"   📌 {p['name']} (TCP)")
                elif item["latency"] < 300:
                    fl, cd = get_region(p.get("name", " "))
                    p["name"] = namer.generate(fl, int(item["latency"]), tcp=True)
                    final_nodes.append(p)
                    tested_keys.add(k)

        final_nodes = final_nodes[:MAX_FINAL_NODES]
        print(f"\n✅ 最终节点: {len(final_nodes)} 个")
        print(f"真实测速: {'✅' if proxy_ok else '❌'}\n")

        # 6. 生成配置
        print("📝 生成配置...")
        cfg = {
            "proxies": final_nodes,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in final_nodes], "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in final_nodes]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        with open("proxies.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

        # Base64 输出 (修复 f-string 语法)
        b64_lines = []
        for p in final_nodes:
            link = format_proxy_to_link(p)
            b64_lines.append(f"# {p['name']}\n{link}")
        with open("subscription.txt", 'w', encoding='utf-8') as f:
            f.write('\n'.join(b64_lines))

        # 7. 统计报告
        tt = time.time() - st
        asia_ct = sum(1 for p in final_nodes if is_asia(p))
        lats = [tcp_ping(p["server"], p["port"]) for p in final_nodes[:20]] if final_nodes else []
        min_lat = min(lats) if lats else 0

        print("\n" + "=" * 50)
        print("📊 统计结果")
        print("=" * 50)
        print(f"• 订阅源: {len(all_urls)} 个 | 固定: {len(fixed_urls)} | Telegram: {len(tg_urls)}")
        print(f"• 原始: {len(nodes)} 个 | TCP: {len(tcp_results)} 个 | 最终: {len(final_nodes)} 个")
        print(f"• 亚洲节点: {asia_ct} 个 ({asia_ct * 100 // max(len(final_nodes), 1)}%)")
        print(f"• 最低延迟: {min_lat:.1f} ms")
        print(f"• 总耗时: {tt:.1f} 秒")
        print("=" * 50 + "\n")

        # 8. Telegram 推送
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                msg = f"""
🚀 <b>节点更新完成</b>

📊 统计:
• 订阅源: {len(all_urls)} | 固定: {len(fixed_urls)} | Telegram: {len(tg_urls)}
• 原始: {len(nodes)} | TCP: {len(tcp_results)} | 最终: {len(final_nodes)}
• 亚洲: {asia_ct} 个
• 最低: {min_lat:.1f} ms
• 耗时: {tt:.1f} 秒

📁 YAML: `https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml`
📄 TXT: `https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt`
"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
                print("✅ Telegram通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram推送失败: {e}")

        print("🎉 任务完成！")

    finally:
        clash.stop()


def format_proxy_to_link(p):
    """转换为协议链接 - 已修复 f-string 语法错误"""
    try:
        if p["type"] == "vmess":
            data = {
                "v": "2",
                "ps": p["name"],
                "add": p["server"],
                "port": p["port"],
                "id": p["uuid"],
                "aid": p.get("alterId", 0),
                "net": p.get("network", "tcp"),
                "type": "none",
                "host": p.get("sni", ""),
                "path": p.get("ws-opts", {}).get("path", ""),
                "tls": "tls" if p.get("tls") else ""
            }
            return "vmess://" + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()
        elif p["type"] == "trojan":
            # 修复：避免 f-string 嵌套转义
            pwd_enc = urllib.parse.quote(p['password'], safe='')
            sni = p.get('sni', p['server'])
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?sni={sni}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "vless":
            return f"vless://{p['uuid']}@{p['server']}:{p['port']}?type={p.get('network', 'tcp')}&security={p.get('tls', 'none')}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "ss":
            # 修复：提前计算 SS 编码部分，避免 f-string 内嵌套
            cipher = p['cipher']
            password = p['password']
            auth_str = f"{cipher}:{password}"
            auth_enc = base64.b64encode(auth_str.encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{urllib.parse.quote(p['name'], safe='')}"
        elif p["type"] == "hysteria2":
            pwd_enc = urllib.parse.quote(p['password'], safe='')
            sni = p.get('sni', p['server'])
            return f"hysteria2://{pwd_enc}@{p['server']}:{p['port']}?insecure=1&sni={sni}#{urllib.parse.quote(p['name'], safe='')}"
        else:
            return f"# {p['name']}"
    except:
        return f"# {p['name']}"


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
