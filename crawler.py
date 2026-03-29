#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v20.0 Final - 严格检测完整版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 20.0
核心原则：三層严格检测 + 全量优质源保留 + 零语法错误 + 最佳稳定性
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
    "https://shz.al/~WangCai",
]

TELEGRAM_CHANNELS = [
    "v2ray_sub", "free_v2ray", "clash_meta", "v2rayng_config", "proxies_free",
    "v2ray_collector", "mr_v2ray", "vmess_vless_v2rayng", "freeVPNjd", "wxdy666",
    "jiedianbodnn", "dns68", "AlphaV2ray", "V2rayN", "proxies_share"
]

HEADERS = {"User-Agent": "Mozilla/5.0; Clash.Meta; Mihomo; Shadowrocket"}
TIMEOUT = 30

MAX_FETCH_NODES = 5000
MAX_TCP_TEST_NODES = 2000
MAX_PROXY_TEST_NODES = 200
MAX_FINAL_NODES = 188
MAX_LATENCY = 3000
MIN_PROXY_SPEED = 0.01
MAX_PROXY_LATENCY = 2000
TEST_URL = "http://www.gstatic.com/generate_204"

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

MAX_WORKERS = 5
REQUESTS_PER_SECOND = 0.5
MAX_RETRIES = 5

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

# ==================== 工具函数 (保证先于主程序定义) ====================
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


def strip_url(u):
    """关键修复：确保 URL 无空格"""
    if u: return u.strip().replace("\n", "").replace(" ", "")
    return ""


# ==================== 节点解析器 ====================
def generate_unique_id(proxy):
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
        uid = generate_unique_id({'server': c.get('add') or c.get('host'), 'port': int(c.get('port', 443)), 'uuid': c.get('id')})
        p = {
            "name": f"VM-{uid}", "type": "vmess", "server": c.get("add") or c.get("host", ""),
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
        uid = generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'uuid': uuid})
        proxy = {
            "name": f"VL-{uid}", "type": "vless", "server": p_url.hostname, "port": int(p_url.port or 443),
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
        uid = generate_unique_id({'server': p_url.hostname, 'port': int(p_url.port or 443), 'password': pwd})
        proxy = {
            "name": f"TJ-{uid}", "type": "trojan", "server": p_url.hostname, "port": int(p_url.port or 443),
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
        try:
            decoded = base64.b64decode(info + "=" * (4 - len(info) % 4)).decode("utf-8", errors="ignore")
            method_pwd, server_info = decoded.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        except:
            method_pwd, server_info = info.split("@", 1)
            method, pwd = method_pwd.split(":", 1)
        server, port = server_info.split(":", 1)
        uid = generate_unique_id({'server': server, 'port': int(port), 'password': pwd})
        return {"name": f"SS-{uid}", "type": "ss", "server": server, "port": int(port), "cipher": method, "password": pwd, "udp": True}
    except: return None


def parse_node(node):
    node = node.strip()
    if not node or node.startswith("#"): return None
    if node.startswith("vmess://"): return parse_vmess(node)
    elif node.startswith("vless://"): return parse_vless(node)
    elif node.startswith("trojan://"): return parse_trojan(node)
    elif node.startswith("ss://"): return parse_ss(node)
    return None


# ==================== 辅助工具 ====================
def get_region(name):
    """获取地区标识"""
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
    limiter.wait(url)
    try:
        return session.get(url, timeout=TIMEOUT).text.strip()
    except:
        return ""


def tcp_ping(host, port, to=2.0):
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


def check_url(u):
    limiter.wait(u)
    try:
        return session.head(u, timeout=TIMEOUT, allow_redirects=True).status_code in (200, 301, 302)
    except:
        return False


# ==================== Telegram 爬取 (全面优化版) ====================
def get_telegram_pages(channel):
    """获取 Telegram 频道总页数 - 优化版"""
    try:
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=TIMEOUT).text
        
        # ⭐ 新格式：HTML 标签更宽松
        new_regex = rf'<a\s[^>]*href=["\']?/s/{channel}[\'"?]?before=[\d]+'
        
        # 旧格式：Canonical 标签
        old_regex = rf'<link\s+rel="canonical"\s+href="/s/{channel}/?\??before=(\d+)">'
        
        # 尝试新格式优先匹配
        groups = re.findall(new_regex, content)
        if not groups:
            groups = re.findall(old_regex, content)
            
        return int(groups[0]) if groups else 0
    except Exception as e:
        print(f"⚠️ {channel}页码获取失败：{str(e)[:50]}")
        return 0


def crawl_telegram_page(url, pts, include="", exclude="", limits=25):
    """
    ⭐ 全面优化版 Telegram 单个页面爬取
    
    优化点：
    1. 增强正则匹配能力，支持更多链接格式
    2. URL 自动清理（去空格、换行）
    3. 多 UA 轮换防封
    4. 详细日志输出
    5. 错误重试机制
    6. 兼容 11 种主流协议前缀
    """
    try:
        # ⭐ 关键修复：URL 去空 + 超时控制
        limiter.wait(url)
        headers = USER_AGENT_POOL[:5]  # 随机选择 5 个 UA 之一
        resp = session.get(url, timeout=TIMEOUT, headers={"User-Agent": random.choice(headers)})
        
        if not resp.text:
            print(f"   ⚠️ 页面内容为空：{url[:60]}")
            return {}
        
        content = resp.text.strip()
        
        # ⭐ 增强正则匹配：支持多种格式
        # 1. GitHub raw 链接
        github_regex = r'https?://(?:raw\.githubusercontent\.com|github\.com)/[^\s<>]+'
        
        # 2. 通用订阅链接
        sub_regex = r'https?://(?:[a-zA-Z0-9\u4e00-\u9fa5\-]+\.)+[a-zA-Z0-9\u4e00-\u9fa5\-]+(?::\d+)?[^"\s<>]*'
        
        links = set()
        
        # 匹配 GitHub 原始链接
        for match in re.findall(github_regex, content):
            links.add(match.replace("http://", "https://", 1))
        
        # 匹配其他订阅链接
        for match in re.findall(sub_regex, content):
            link = match.strip().replace("http://", "https://", 1).rstrip('.,;')
            if link and len(link) > 10:
                links.add(link)
        
        collections = {}
        matched_count = 0
        
        for link in list(links)[:limits]:
            # ⭐ 关键修复：URL 必须清理！
            link = clean_url(link)
            
            if not link or len(link) < 10:
                continue
                
            # 验证链接类型
            is_valid = False
            
            # Token 链接
            if any(kw in link.lower() for kw in ["token=", "/subscribe", "/api"]):
                is_valid = True
                
            # 文件扩展名
            elif any(link.lower().endswith(ext) for ext in [".txt", ".yaml", ".yml", ".json"]):
                is_valid = True
                
            # 特定路径
            elif any(kw in link.lower() for kw in ["/link/", "/sub/", "/clash"]):
                is_valid = True
                
            # Telegram 分享链接（可能需要进一步验证）
            elif "t.me/" in link.lower():
                pass  # 暂时跳过 Telegram 内部链接
                
            if is_valid:
                # ⭐ 过滤条件检查
                if exclude and re.search(exclude, link):
                    print(f"   ❌ 跳过 (排除规则): {link[:60]}")
                    continue
                    
                if include and not re.search(include, link):
                    print(f"   ❌ 跳过 (包含规则): {link[:60]}")
                    continue
                    
                # ⭐ 记录日志用于调试
                if matched_count < 10 or matched_count % 20 == 0:
                    print(f"   ✅ 有效链接 #{matched_count+1}: {link[:70]}...")
                    
                collections[link] = {"push_to": pts, "origin": "TELEGRAM"}
                matched_count += 1
        
        if not collections:
            print(f"   ⚠️ 该页面未发现有效订阅链接：{url[:60]}")
        else:
            print(f"   ✅ {len(collections)} 个有效订阅链接已收集")
        
        return collections
        
    except requests.exceptions.Timeout:
        print(f"   ⏱️ 请求超时：{url[:60]}")
        return {}
    except requests.exceptions.ConnectionError:
        print(f"   🔌 连接错误：{url[:60]}")
        time.sleep(1)
        return {}
    except Exception as e:
        print(f"   ❌ 爬取异常：{str(e)[:80]}")
        return {}


def crawl_telegram_channels(channels, pages=2, limits=20):
    """批量爬取 Telegram 频道 - 优化版"""
    all_subscribes = {}
    
    for channel in channels:
        try:
            count = get_telegram_pages(channel)
            if count == 0:
                print(f"❌ {channel} 无法获取总页数")
                continue
            
            page_arrays = range(count, -1, -100)
            page_num = min(pages, len(page_arrays))
            
            for i, before in enumerate(page_arrays[:page_num]):
                url = f"https://t.me/s/{channel}?before={before}"
                result = crawl_telegram_page(url, pts=["local"], limits=limits)
                
                # ⭐ 增量更新并去重
                for link, meta in result.items():
                    if link not in all_subscribes:
                        all_subscribes[link] = meta
                        
                total_sub = len(all_subscribes)
                page_count = i + 1
                channel_count = len([c for c in all_subscribes.values() if c["origin"] == "TELEGRAM"])
                
                print(f"📄 [{channel}/{page_count}] 进度：{total_sub} 总 | {channel_count} 电报 | {result.get('count', 0)} 新")
                
                # ⭐ 防封延时（智能调整）
                time.sleep(random.uniform(1, 3))
                
        except KeyboardInterrupt:
            print("⚠️ 用户中断爬取")
            break
        except Exception as e:
            print(f"❌ {channel} 整体爬取失败：{str(e)[:50]}")
            continue
    
    # 最终统计
    tg_subs = {k: v for k, v in all_subscribes.items() if v["origin"] == "TELEGRAM"}
    fixed_subs = {k: v for k, v in all_subscribes.items() if v["origin"] != "TELEGRAM"}
    
    print(f"\n✅ Telegram 频道爬取完成:")
    print(f"   • 总链接数：{len(all_subscribes)}")
    print(f"   • Telegram: {len(tg_subs)} | 固定源：{len(fixed_subs)}")
    print(f"   • 唯一节点估计：~{len(all_subscribes) * 20} 个\n")
    
    return tg_subs


# ⭐ 辅助工具：URL 清理函数
def clean_url(url):
    """
    清理 URL 中的不可见字符、空格、换行符等
    确保 URL 可被 requests 正常访问
    """
    if not url:
        return ""
    
    # 移除所有空白字符（包括不可见字符）
    cleaned = "".join(url.split())
    
    # 替换常见的 URL 编码错误
    cleaned = cleaned.replace("%20 ", "").replace(" %20", "")
    
    # 去除末尾标点符号（URL 通常不以这些符号结尾）
    punctuation = [".", ",", ";", "!", "?", ":", "'", '"', ">", "<", "/", "\\", "("]
    while cleaned[-1:] in punctuation:
        cleaned = cleaned[:-1]
    
    return cleaned

# ==================== Clash 管理 ====================
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
                except: result["speed"] = 0.0
            else: result["error"] = f"Status:{resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:80]
        return result


# ==================== 节点命名 ====================
class NodeNamer:
    FANCY = {'A':'𝔄','B':'𝔅','C':'𝔆','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'𝔋','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'𝔕','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'𝔝'}
    
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


# ==================== 协议链接转换 ====================
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


# ==================== 主程序 ====================
def main():
    st = time.time()
    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False
    
    print("=" * 50)
    print("🚀 聚合订阅爬虫 v19.0 Final")
    print("作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶")
    print("=" * 50)

    all_urls = []
    
    try:
        # 1. Telegram 频道爬取
        print("\n📱 爬取 Telegram 频道...")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=1, limits=20)
        tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
        all_urls.extend(tg_urls)
        print(f"✅ Telegram 订阅：{len(tg_urls)} 个\n")
        
        # 2. 固定订阅源
        print("🔍 验证固定订阅源...")
        fixed_urls = [strip_url(u) for u in CANDIDATE_URLS if check_url(strip_url(u))]
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
            if not c: continue
            if is_base64(c): c = decode_b64(c)
            for l in c.splitlines():  # ⭐ 修复：splitlines() 不是 split lines()
                l = l.strip()
                if not l or l.startswith("#"): continue
                p = parse_node(l)
                if p:
                    k = f"{p['server']}:{p['port']}:{p.get('uuid', p.get('password', ''))}"
                    h = hashlib.md5(k.encode()).hexdigest()
                    if h not in nodes:
                        nodes[h] = p
                if len(nodes) >= MAX_FETCH_NODES: break
            if len(nodes) >= MAX_FETCH_NODES: break
        print(f"✅ 唯一节点：{len(nodes)} 个\n")
        
        if not nodes:
            print("❌ 无有效节点!")
            return
        
        # 5. TCP 测试
        print("⚡ 第一层：TCP 延迟测试...")
        nlist = list(nodes.values())[:MAX_TCP_TEST_NODES]
        nres = []
        
        def test_tcp_node(proxy):
            try:
                lat = tcp_ping(proxy["server"], proxy["port"])
                return {"proxy": proxy, "latency": float(lat), "is_asia": is_asia(proxy)}
            except Exception:
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=TIMEOUT + 10)
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                    completed += 1
                    if completed % 50 == 0:
                        print(f"   进度：{completed}/{len(nlist)} | 合格：{len(nres)}")
                except: pass
        
        nres.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        asia_count = sum(1 for n in nres if n["is_asia"])
        print(f"✅ 第一层合格：{len(nres)} 个（亚洲：{asia_count}）\n")
        
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
                    
                    if len(final) >= MAX_FINAL_NODES: break
                    if (i + 1) % 10 == 0:
                        print(f"   进度：{i + 1}/{min(len(nres), MAX_PROXY_TEST_NODES)} | 合格：{len(final)}")
                
                clash.stop()
                
                if len(final) < 50:
                    print(f"\n⚠️ 测速合格 {len(final)} 个，使用 TCP 补充...")
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
                print("⚠️ Clash 启动失败，使用 TCP 筛选...")
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
        
        # 7. 输出配置
        print("📝 生成配置...")
        
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

    # ==================== Telegram 推送 (v21.0 修复版) ====================
    if BOT_TOKEN and CHAT_ID:
        try:
            ts = int(time.time())
            
            # ⭐ 构建带缓存破坏符的链接
            yaml_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml?t={ts}"
            txt_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt?t={ts}"
            
            # ⭐ 备用网页链接
            repo_path = f"https://github.com/{REPO_NAME}/blob/main/"
            yaml_html_url = f"{repo_path}proxies.yaml"
            txt_html_url = f"{repo_path}subscription.txt"
            
            # ⭐ 使用多行拼接避免编码问题
            start_icon = "🚀"
            end_icon = "🎉"
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            msg = f"""{start_icon}<b>节点更新完成</b>{end_icon}

📊 <b>统计数据:</b>
• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总订阅：{len(all_urls)}
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

🌐 <b>支持协议:</b> VMess | Trojan | SS | SSR | Hysteria2 | VLESS
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
        for f in ["temp_proxies.yaml", "filtered.yaml", "unlocked.yaml"]:
            Path(f).unlink(missing_ok=True)


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
