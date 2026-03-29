#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v11.0 - 多源聚合 + 智能筛选 + 格式转换
适用: GitHub Actions / 本地 Python 3.9+
优化点: 修复语法BUG + 提升节点质量 + 降低请求频率
"""

import os, sys, json, time, re, yaml, gzip, shutil, ssl, hashlib, base64, socket, signal, subprocess, threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# ==================== 配置区 ====================
class Config:
    """系统配置管理"""
    
    # 高质量订阅源
    CANDIDATE_URLS = [
        # V2RayAggregator系列 (最稳定)
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
        "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
        # Pawdroid & barry-far
        "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
        # 其他优质源
        "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
        "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
        "https://raw.githubusercontent.com/SnapdragonLee/SystemProxy/master/dist/clash_config.yaml",
        "https://shz.al/~WangCai",
    ]
    
    # Telegram频道
    TELEGRAM_CHANNELS = [
        "v2rayng_config_amin", "proxies_free", "freev2raym", 
        "vmess_vless_v2rayng", "mr_v2ray", "dns68"
    ]
    
    # 性能参数 (针对GitHub Actions优化)
    MAX_FETCH_NODES = 1500
    MAX_TCP_TEST_NODES = 400
    MAX_PROXY_TEST_NODES = 120
    MAX_FINAL_NODES = 100
    
    # 延迟阈值 (平衡数量与质量)
    MAX_LATENCY = 1500
    MAX_PROXY_LATENCY = 3000
    MIN_PROXY_SPEED = 0.02
    TIMEOUT = 30
    
    # 网络设置
    CLASH_PORT = 17890
    CLASH_API_PORT = 19090
    CLASH_VERSION = "v1.19.0"
    NODE_NAME_PREFIX = "Anftli"
    
    # 并发控制 (避免503错误)
    MAX_WORKERS = 5
    REQUESTS_PER_SECOND = 1.0
    
    # Telegram推送
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    CHAT_ID = os.getenv("CHAT_ID", "")
    REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")
    
    # 工作目录
    WORK_DIR = Path(os.getcwd()) / "clash_temp"
    CONFIG_FILE = WORK_DIR / "config.yaml"
    LOG_FILE = WORK_DIR / "clash.log"
    CLASH_PATH = WORK_DIR / "mihomo"

def ensure_clash_dir():
    """确保Clash工作目录存在"""
    Config.WORK_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 速率限制器 ====================
class RateLimiter:
    def __init__(self, calls_per_second=Config.REQUESTS_PER_SECOND):
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


# ==================== HTTP会话 ====================
def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo"})
    return session


session = create_session()


# ==================== 辅助工具 ====================
def is_base64(content):
    """判断Base64编码"""
    try:
        content = content.strip()
        if len(content) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', content):
            return False
        base64.b64decode(content + "=" * (4 - len(content) % 4), validate=True)
        return True
    except:
        return False


def decode_b64(content):
    """解码Base64内容"""
    try:
        content = content.strip()
        m = len(content) % 4
        if m:
            content += "=" * (4 - m)
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        return decoded if "://" in decoded else content
    except:
        return content


def fetch(url):
    """安全抓取URL内容"""
    limiter.wait()
    try:
        resp = session.get(url, timeout=Config.TIMEOUT)
        resp.raise_for_status()
        return resp.text.strip()
    except:
        return ""


def check_url(url):
    """检查URL是否可达"""
    limiter.wait()
    try:
        resp = session.head(url, timeout=Config.TIMEOUT, allow_redirects=True)
        return resp.status_code in (200, 301, 302)
    except:
        return False


def tcp_ping(host, port, timeout=2.0):
    """TCP连接测试"""
    if not host:
        return 9999
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        st = time.time()
        s.connect((host, port))
        s.close()
        return round((time.time() - st) * 1000, 1)
    except:
        return 9999


def get_region(name):
    """提取地区标志"""
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
    elif any(k in nl for k in ["uk", "britain", "英"]):
        return "🇬🇧", "UK"
    elif any(k in nl for k in ["de", "germany", "德"]):
        return "🇩🇪", "DE"
    elif any(k in nl for k in ["fr", "french", "法"]):
        return "🇫🇷", "FR"
    return "🌍", "OT"


def is_asia(proxy):
    """判断是否为亚洲节点"""
    t = f"{proxy.get('name', '')} {proxy.get('server', '')}".lower()
    return any(k in t for k in ["hk", "hongkong", "tw", "taiwan", "jp", "japan", 
                                 "sg", "singapore", "kr", "korea", "asia", "th", "vn"])


# ==================== 协议解析器 ====================
def parse_vmess(node):
    """解析VMess协议"""
    try:
        if not node.startswith("vmess://"):
            return None
        payload = node[8:]
        m = len(payload) % 4
        if m:
            payload += "=" * (4 - m)
        decoded = base64.b64decode(payload).decode("utf-8", errors="ignore")
        
        if not decoded.startswith("{"):
            return None
        
        config = json.loads(decoded)
        proxy = {
            "name": "🌍",
            "type": "vmess",
            "server": config.get("add", ""),
            "port": int(config.get("port", 443)),
            "uuid": config.get("id", ""),
            "alterId": int(config.get("aid", 0)),
            "cipher": "auto",
            "udp": True,
            "skip-cert-verify": True
        }
        
        net = config.get("net", "tcp").lower()
        if net in ["ws", "h2", "grpc"]:
            proxy["network"] = net
        if config.get("tls") == "tls" or config.get("security") == "tls":
            proxy["tls"] = True
            proxy["sni"] = config.get("sni") or config.get("host") or proxy["server"]
        if net == "ws":
            ws_opts = {}
            if config.get("path"):
                ws_opts["path"] = config.get("path")
            if config.get("host"):
                ws_opts["headers"] = {"Host": config.get("host")}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        
        return proxy if proxy["server"] and proxy["uuid"] else None
    except:
        return None


def parse_vless(node):
    """解析VLESS协议"""
    try:
        if not node.startswith("vless://"):
            return None
        parsed = urlparse(node)
        if not parsed.hostname:
            return None
            
        uuid = parsed.username
        if not uuid:
            return None
            
        params = parse_qs(parsed.query)
        gp = lambda k: params.get(k, [""])[0]
        security = gp("security")
        
        proxy = {
            "name": "🌍",
            "type": "vless",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "uuid": uuid,
            "udp": True,
            "skip-cert-verify": True
        }
        
        if security in ["tls", "reality"]:
            proxy["tls"] = True
            proxy["sni"] = gp("sni") or proxy["server"]
            
        if security == "reality":
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
            path_val = gp("path")
            host_val = gp("host")
            if path_val:
                ws_opts["path"] = path_val
            if host_val:
                ws_opts["headers"] = {"Host": host_val}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
                
        return proxy
    except:
        return None


def parse_trojan(node):
    """解析Trojan协议"""
    try:
        if not node.startswith("trojan://"):
            return None
        parsed = urlparse(node)
        if not parsed.hostname:
            return None
            
        pwd = parsed.username or unquote(parsed.path.strip("/"))
        if not pwd:
            return None
            
        params = parse_qs(parsed.query)
        gp = lambda k: params.get(k, [""])[0]
        
        proxy = {
            "name": "🌍",
            "type": "trojan",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "password": pwd,
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or parsed.hostname
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
    """解析Shadowsocks协议"""
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
    """解析Hysteria2协议"""
    try:
        if not node.startswith("hysteria2://"):
            return None
        parsed = urlparse(node)
        if not parsed.hostname:
            return None
            
        pwd = unquote(parsed.username or "")
        params = parse_qs(parsed.query)
        gp = lambda k: params.get(k, [""])[0]
        
        return {
            "name": "🌍",
            "type": "hysteria2",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "password": pwd or gp("auth"),
            "udp": True,
            "skip-cert-verify": True,
            "sni": gp("sni") or parsed.hostname
        }
    except:
        return None


def parse_node(node):
    """通用节点解析入口"""
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


# ==================== 节点命名器 ====================
class NodeNamer:
    def __init__(self):
        self.counters = {}

    def generate(self, flag, lat, speed=None, tcp=False):
        code, region = get_region(flag)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        
        if speed:
            return f"{code}{num}-{Config.NODE_NAME_PREFIX}|⚡{lat}ms|📥{speed:.1f}MB"
        return f"{code}{num}-{Config.NODE_NAME_PREFIX}|⚡{lat}ms{'(TCP)' if tcp else ''}"


# ==================== Clash管理器 ====================
class ClashManager:
    def __init__(self):
        self.process = None
        ensure_clash_dir()
        
    def download_clash(self):
        """下载Clash内核"""
        if Config.CLASH_PATH.exists():
            return True
            
        urls = [
            f"https://github.com/MetaCubeX/mihomo/releases/download/{Config.CLASH_VERSION}/mihomo-linux-amd64-compatible-{Config.CLASH_VERSION}.gz",
            f"https://github.com/MetaCubeX/mihomo/releases/download/{Config.CLASH_VERSION}/mihomo-linux-amd64-{Config.CLASH_VERSION}.gz",
            "https://cdn.jsdelivr.net/gh/MetaCubeX/mihomo@alpha/prebuilt/mihomo-linux-amd64.gz",
        ]
        
        for url in urls:
            try:
                print(f"   下载中: {url[:50]}...")
                resp = session.get(url, timeout=120, stream=True)
                if resp.status_code != 200:
                    continue
                    
                temp = Config.WORK_DIR / "mihomo.gz"
                with open(temp, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if os.path.getsize(temp) < 1000000:
                    print("   ⚠️ 下载内容过小，跳过")
                    temp.unlink(missing_ok=True)
                    continue
                
                with gzip.open(temp, 'rb') as f_in:
                    with open(Config.CLASH_PATH, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.chmod(Config.CLASH_PATH, 0o755)
                temp.unlink()
                
                print("   ✅ Clash下载完成")
                return True
                
            except Exception as e:
                print(f"   ⚠️ 下载失败: {e}")
                continue
                
        print("   ❌ 所有下载源均失败")
        return False
        
    def create_config(self, proxies):
        """创建Clash配置文件"""
        config = {
            "port": Config.CLASH_PORT,
            "socks-port": Config.CLASH_PORT + 1,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "warning",
            "external-controller": f"0.0.0.0:{Config.CLASH_API_PORT}",
            "secret": "",
            "ipv6": False,
            "unified-delay": True,
            "tcp-concurrent": True,
            "proxies": proxies[:Config.MAX_PROXY_TEST_NODES],
            "proxy-groups": [{
                "name": "TEST",
                "type": "select",
                "proxies": [p["name"] for p in proxies[:Config.MAX_PROXY_TEST_NODES]]
            }],
            "rules": ["MATCH,TEST"]
        }
        
        with open(Config.CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
            
        return True
        
    def start(self):
        """启动Clash进程"""
        if not Config.CLASH_PATH.exists() and not self.download_clash():
            return False
            
        self.stop()
        
        Config.LOG_FILE.touch()
        
        try:
            cmd = [
                str(Config.CLASH_PATH.absolute()),
                "-d", str(Config.WORK_DIR.absolute()),
                "-f", str(Config.CONFIG_FILE.absolute())
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,
                cwd=str(Config.WORK_DIR.absolute())
            )
            
            # 启动检测 (最长30秒)
            for i in range(30):
                time.sleep(1)
                
                # 检查进程状态
                if self.process.poll() is not None:
                    try:
                        out, _ = self.process.communicate(timeout=2)
                        print(f"   ❌ Clash崩溃:\n{out[:300]}")
                    except:
                        print("   ❌ Clash崩溃 (无日志)")
                    return False
                
                # 尝试连接API
                try:
                    if requests.get(
                        f"http://127.0.0.1:{Config.CLASH_API_PORT}/version",
                        timeout=2
                    ).status_code == 200:
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
        """停止Clash进程"""
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
        """测试单个代理"""
        result = {"success": False, "latency": 9999, "speed": 0.0, "error": ""}
        
        try:
            # 选择代理
            requests.put(
                f"http://127.0.0.1:{Config.CLASH_API_PORT}/proxies/TEST",
                json={"name": name},
                timeout=5
            )
            
            time.sleep(0.3)
            
            proxies = {
                "http": f"http://127.0.0.1:{Config.CLASH_PORT}",
                "https": f"http://127.0.0.1:{Config.CLASH_PORT}"
            }
            
            # 延迟测试
            start = time.time()
            resp = requests.get(
                "http://www.gstatic.com/generate_204",
                proxies=proxies,
                timeout=10
            )
            lat = (time.time() - start) * 1000
            
            if resp.status_code in [200, 204, 301, 302]:
                result["success"] = True
                result["latency"] = round(lat, 1)
                
                # 速度测试
                sp_start = time.time()
                try:
                    sp_resp = requests.get(
                        "https://speed.cloudflare.com/__down?bytes=524288",
                        proxies=proxies,
                        timeout=15
                    )
                    sp = len(sp_resp.content) / max(0.5, time.time() - sp_start) / (1024 * 1024)
                    result["speed"] = round(sp, 2)
                except:
                    result["speed"] = 0.0
                    
            else:
                result["error"] = f"HTTP {resp.status_code}"
                
        except Exception as e:
            result["error"] = str(e)[:80]
            
        return result


# ==================== Telegram爬取 ====================
def crawl_telegram_channels(channels, pages=2, limits=20):
    """爬取Telegram频道订阅链接"""
    all_subscribes = {}
    protocol_prefixes = ("t.me/", "raw.githubusercontent.com/", "github.com/")
    
    for channel in channels:
        try:
            url = f"https://t.me/s/{channel}?before={pages * 100}"
            limiter.wait()
            content = session.get(url, timeout=Config.TIMEOUT).text
            
            sub_regex = r'https?://(?:[a-zA-Z0-9\u4e00-\u9fa5\-]+\.)+[a-zA-Z0-9\u4e00-\u9fa5\-]+(?::\d+)?[^"\s<>]'
            links = re.findall(sub_regex, content)
            
            count = 0
            for link in links[:limits]:
                if any(link.startswith(p) for p in protocol_prefixes):
                    link = link.replace("http://", "https://", 1)
                    if "?" in link and ("token=" in link or "mu=" in link):
                        all_subscribes[link] = {"origin": "TELEGRAM"}
                        count += 1
                        
            print(f"✅ 频道 {channel}: 发现 {count} 个订阅")
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ 频道 {channel}: 爬取失败 - {e}")
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
        
        # 固定订阅源
        fixed_urls = [u for u in Config.CANDIDATE_URLS if check_url(u)]
        all_urls.extend(fixed_urls)
        print(f"✅ 固定源: {len(fixed_urls)} 个可用")
        
        # Telegram频道 (可选)
        tg_subs = crawl_telegram_channels(Config.TELEGRAM_CHANNELS, pages=2, limits=15)
        tg_urls = list(tg_subs.keys())
        all_urls.extend(tg_urls)
        print(f"✅ Telegram: {len(tg_urls)} 个订阅")
        
        # 去重
        all_urls = list(set(all_urls))
        print(f"📊 总计: {len(all_urls)} 个订阅源\n")
        
        # 2. 抓取节点
        print("📥 抓取节点...")
        nodes = {}
        
        def fetch_valid_nodes(url):
            """从URL提取有效节点"""
            nodes_result = {}
            content = fetch(url)
            
            if not content:
                return nodes_result
                
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
                    if h not in nodes_result:
                        nodes_result[h] = p
                        
            return nodes_result
        
        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_valid_nodes, u): u for u in all_urls}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    nodes.update(result)
                except Exception as e:
                    pass
                    
                if len(nodes) >= Config.MAX_FETCH_NODES:
                    break
                    
        print(f"✅ 唯一节点: {len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
            
        # 3. TCP测试
        print("⚡ TCP延迟测试...")
        nlist = list(nodes.values())[:Config.MAX_TCP_TEST_NODES]
        tcp_results = []
        
        def test_tcp_node(proxy):
            """TCP测试任务"""
            lat = tcp_ping(proxy["server"], proxy["port"])
            return {
                "proxy": proxy,
                "latency": lat,
                "is_asia": is_asia(proxy),
                "status": "OK" if lat < Config.MAX_LATENCY else "FAIL"
            }
        
        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            futures = {executor.submit(test_tcp_node, p): p for p in nlist}
            
            completed_count = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=Config.TIMEOUT)
                    if result["status"] == "OK":
                        tcp_results.append(result)
                    
                    completed_count += 1
                    if completed_count % 50 == 0:
                        print(f"   进度：{completed_count}/{len(nlist)} | 合格：{len(tcp_results)}")
                        
                except Exception as e:
                    continue
        
        tcp_results.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in tcp_results if n['is_asia'])
        print(f"✅ TCP合格: {len(tcp_results)} 个（亚洲: {asia_count}）\n")
        
        # 4. 真实测速
        print("🚀 真实代理测速...")
        
        if len(tcp_results) > 0:
            tprox = [n["proxy"] for n in tcp_results[:Config.MAX_PROXY_TEST_NODES]]
            
            if clash.create_config(tprox) and clash.start():
                proxy_ok = True
                print("📊 测速中...\n")
                
                progress = 0
                for item in tcp_results[:Config.MAX_PROXY_TEST_NODES]:
                    p = item["proxy"]
                    r = clash.test_proxy(p["name"])
                    k = f"{p['server']}:{p['port']}"
                    
                    if r["success"] and r["latency"] < Config.MAX_PROXY_LATENCY:
                        if r["speed"] >= Config.MIN_PROXY_SPEED or r["latency"] < 500:
                            fl, cd = get_region(p.get("name", " "))
                            p["name"] = namer.generate(fl, int(r["latency"]), r["speed"], tcp=False)
                            final_nodes.append(p)
                            tested_keys.add(k)
                            progress += 1
                            print(f"   ✅ {p['name']}")
                                
                    if len(final_nodes) >= Config.MAX_FINAL_NODES:
                        break
                        
                clash.stop()
            else:
                print("⚠️ Clash启动失败，使用TCP保底")
                
        # 5. TCP保底补充
        if len(final_nodes) < 30:
            print("使用TCP测试节点补充...")
            for item in tcp_results:
                if len(final_nodes) >= Config.MAX_FINAL_NODES:
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
                    
        final_nodes = final_nodes[:Config.MAX_FINAL_NODES]
        print(f"\n✅ 最终节点: {len(final_nodes)} 个")
        print(f"真实测速: {'✅' if proxy_ok else '❌'}\n")
        
        # 6. 生成配置
        print("📝 生成配置...")
        cfg = {
            "proxies": final_nodes,
            "proxy-groups": [
                {
                    "name": "🚀 Auto",
                    "type": "url-test",
                    "proxies": [p["name"] for p in final_nodes],
                    "url": "http://www.gstatic.com/generate_204",
                    "interval": 300,
                    "tolerance": 50
                },
                {
                    "name": "🌍 Select",
                    "type": "select",
                    "proxies": ["🚀 Auto"] + [p["name"] for p in final_nodes]
                }
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        
        with open("proxies.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)
            
        # Base64输出
        b64_lines = [f"# {p['name']}\n{format_proxy_to_link(p)}" for p in final_nodes]
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
        
        # 8. Telegram推送
        if Config.BOT_TOKEN and Config.CHAT_ID and Config.REPO_NAME:
            try:
                msg = f"""
🚀 <b>节点更新完成</b>

📊 统计:
• 订阅源: {len(all_urls)} | 固定: {len(fixed_urls)} | Telegram: {len(tg_urls)}
• 原始: {len(nodes)} | TCP: {len(tcp_results)} | 最终: {len(final_nodes)}
• 亚洲: {asia_ct} 个
• 最低: {min_lat:.1f} ms
• 耗时: {tt:.1f} 秒

📁 YAML: `https://raw.githubusercontent.com/{Config.REPO_NAME}/main/proxies.yaml`
📄 TXT: `https://raw.githubusercontent.com/{Config.REPO_NAME}/main/subscription.txt`

🌐 支持协议: VMess | Trojan | SS | SSR | Hysteria2 | VLESS
"""
                requests.post(
                    f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage",
                    json={"chat_id": Config.CHAT_ID, "text": msg, "parse_mode": "HTML"},
                    timeout=10
                )
                print("✅ Telegram通知已发送")
            except Exception as e:
                print(f"⚠️ Telegram推送失败: {e}")
                
        print("🎉 任务完成！")
        
    finally:
        clash.stop()


def format_proxy_to_link(p):
    """将代理对象转换为协议链接（简化版）"""
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
            return f"trojan://{p['password']}@{p['server']}:{p['port']}?sni={p.get('sni', '')}#{p['name']}"
        elif p["type"] == "vless":
            return f"vless://{p['uuid']}@{p['server']}:{p['port']}?type={p.get('network', 'tcp')}&security={p.get('tls', 'none')}#{p['name']}"
        elif p["type"] == "ss":
            return f"ss://{base64.b64encode(f'{p[\"cipher\"]}:{p[\"password\"]}'.encode()).decode()}@{p['server']}:{p['port']}#{p['name']}"
        elif p["type"] == "hysteria2":
            return f"hysteria2://{p['password']}@{p['server']}:{p['port']}?insecure=1&sni={p.get('sni', '')}#{p['name']}"
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
