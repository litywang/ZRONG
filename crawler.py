#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clash 节点筛选器 - v5.0 (完整参数解析版)
修复：
  ✅ VLESS Reality 完整参数解析
  ✅ VMess WS/H2/GRPC 完整配置
  ✅ Trojan 完整 TLS 配置
  ✅ 生成 Clash.Meta 完整 YAML 格式
"""

import requests
import base64
import hashlib
import time
import json
import socket
import os
import sys
import re
import yaml
import subprocess
import signal
import gzip
import shutil
from urllib.parse import urlparse, parse_qs, unquote, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ==================== 配置区 ====================
CANDIDATE_URLS = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
TIMEOUT = 10

MAX_FETCH_NODES = 2000
MAX_TCP_TEST_NODES = 400
MAX_PROXY_TEST_NODES = 150
MAX_FINAL_NODES = 100

MAX_LATENCY = 1000
MIN_PROXY_SPEED = 0.03
MAX_PROXY_LATENCY = 2000
TEST_URL = "http://www.gstatic.com/generate_204"

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"

NODE_NAME_STYLE = "fancy"
NODE_NAME_PREFIX = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"

def ensure_clash_dir():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return WORK_DIR

# ==================== 节点重命名 ====================
class NodeNamer:
    FANCY_CHARS = {
        'A': '𝔄', 'B': '𝔅', 'C': '𝔆', 'D': '𝔇', 'E': '𝔈', 'F': '𝔉', 'G': '𝔊', 'H': '𝔋',
        'I': 'ℑ', 'J': '𝔍', 'K': '𝔎', 'L': '𝔏', 'M': '𝔐', 'N': '𝔑', 'O': '𝔒', 'P': '𝔓',
        'Q': '𝔔', 'R': '𝔕', 'S': '𝔖', 'T': '𝔗', 'U': '𝔘', 'V': '𝔙', 'W': '𝔚', 'X': '𝔛',
        'Y': '𝔜', 'Z': '𝔝',
        'a': '𝔞', 'b': '𝔟', 'c': '𝔠', 'd': '𝔡', 'e': '𝔢', 'f': '𝔣', 'g': '𝔤', 'h': '𝔥',
        'i': '𝔦', 'j': '𝔧', 'k': '𝔨', 'l': '𝔩', 'm': '𝔪', 'n': '𝔫', 'o': '𝔬', 'p': '𝔭',
        'q': '𝔮', 'r': '𝔯', 's': '𝔰', 't': '𝔱', 'u': '𝔲', 'v': '𝔳', 'w': '𝔴', 'x': '𝔵',
        'y': '𝔶', 'z': '𝔷',
    }
    REGION_CODES = {"🇭🇰": "HK", "🇹🇼": "TW", "🇯🇵": "JP", "🇸🇬": "SG", "🇰🇷": "KR", "🇹🇭": "TH", "🇻🇳": "VN", "🇺🇸": "US", "🇬🇧": "UK", "🇩🇪": "DE", "🇫🇷": "FR", "🇳🇱": "NL", "🌍": "OT"}
    
    def __init__(self, style="fancy", prefix=NODE_NAME_PREFIX):
        self.style = style
        self.prefix = prefix
        self.counters = {}
    
    def to_fancy(self, text):
        return ''.join(self.FANCY_CHARS.get(c, c) for c in text)
    
    def generate_name(self, flag, latency, speed=None, tcp_only=False):
        code = self.REGION_CODES.get(flag, "OT")
        if code not in self.counters:
            self.counters[code] = 0
        self.counters[code] += 1
        num = self.counters[code]
        prefix = self.to_fancy(self.prefix) if self.style == "fancy" else "Anftlity"
        if speed:
            return f"{code}{num}-{prefix}|⚡{latency}ms|📥{speed:.1f}MB"
        elif tcp_only:
            return f"{code}{num}-{prefix}|⚡{latency}ms(TCP)"
        return f"{code}{num}-{prefix}|⚡{latency}ms"

# ==================== Clash 管理 ====================
class ClashManager:
    def __init__(self):
        self.error_details = []
        self.process = None
        ensure_clash_dir()
    
    def download_clash(self):
        print("📥 下载 Mihomo 内核...")
        if CLASH_PATH.exists():
            return True
        urls = [f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz"]
        for url in urls:
            try:
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                temp_gz = WORK_DIR / "mihomo.gz"
                with open(temp_gz, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                with gzip.open(temp_gz, "rb") as f_in:
                    with open(CLASH_PATH, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.chmod(CLASH_PATH, 0o755)
                temp_gz.unlink()
                if CLASH_PATH.exists():
                    return True
            except:
                continue
        return False
    
    def create_test_config(self, proxies):
        ensure_clash_dir()
        config = {
            "port": CLASH_PORT, "socks-port": CLASH_PORT + 1, "allow-lan": False, "mode": "rule",
            "log-level": "warning", "external-controller": f"0.0.0.0:{CLASH_API_PORT}", "secret": "",
            "ipv6": False, "unified-delay": True, "tcp-concurrent": True,
            "proxies": proxies[:MAX_PROXY_TEST_NODES],
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": [p["name"] for p in proxies[:MAX_PROXY_TEST_NODES]]}],
            "rules": ["MATCH,TEST"]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        return True
    
    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash():
            return False
        print("🚀 启动 Clash 内核...")
        LOG_FILE.touch()
        try:
            with open(LOG_FILE, "w") as log_f:
                self.process = subprocess.Popen(
                    [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())],
                    stdout=log_f, stderr=subprocess.STDOUT, preexec_fn=os.setsid, cwd=str(WORK_DIR.absolute())
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
    
    def test_proxy(self, proxy_name):
        result = {"success": False, "latency": 9999, "speed": 0.0, "error": ""}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST", json={"name": proxy_name}, timeout=5)
            time.sleep(0.3)
            proxies = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            start = time.time()
            resp = requests.get(TEST_URL, proxies=proxies, timeout=10, allow_redirects=False)
            latency = (time.time() - start) * 1000
            if resp.status_code in [200, 204, 301, 302]:
                speed_start = time.time()
                speed_resp = requests.get("https://speed.cloudflare.com/__down?bytes=524288", proxies=proxies, timeout=15)
                speed = len(speed_resp.content) / max(0.5, time.time() - speed_start) / (1024 * 1024)
                result = {"success": True, "latency": round(latency, 1), "speed": round(speed, 2), "error": ""}
            else:
                result["error"] = f"Status: {resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:80]
        return result

# ==================== ⭐ 完整节点解析（修复版） ====================
def parse_vmess_complete(node):
    """完整解析 VMess，保留所有必需参数"""
    try:
        if not node.startswith("vmess://"):
            return None
        payload = node[8:]
        for _ in range(2):
            try:
                missing = len(payload) % 4
                if missing:
                    payload += "=" * (4 - missing)
                decoded = base64.b64decode(payload).decode("utf-8")
                if decoded.startswith("{"):
                    payload = decoded
                    break
                payload = decoded
            except:
                break
        if not payload.startswith("{"):
            return None
        config = json.loads(payload)
        
        # 基础参数
        proxy = {
            "name": f"🌍",
            "type": "vmess",
            "server": config.get("add") or config.get("host", ""),
            "port": int(config.get("port", 443)),
            "uuid": config.get("id", ""),
            "alterId": int(config.get("aid", 0)),
            "cipher": config.get("scy", "auto") or "auto",
            "udp": True,
            "skip-cert-verify": True,
        }
        
        # 网络类型
        network = config.get("net", "tcp").lower()
        if network in ["ws", "h2", "http", "grpc", "quic"]:
            proxy["network"] = network
        
        # TLS 配置
        if config.get("tls") == "tls" or config.get("security") == "tls":
            proxy["tls"] = True
            proxy["sni"] = config.get("sni") or config.get("host") or proxy["server"]
            proxy["skip-cert-verify"] = config.get("allowInsecure", False) or True
            # ALPN
            alpn = config.get("alpn")
            if alpn:
                if isinstance(alpn, str):
                    proxy["alpn"] = [a.strip() for a in alpn.split(",")]
                else:
                    proxy["alpn"] = alpn
        
        # WS 配置（完整）
        if network == "ws":
            ws_opts = {}
            path = config.get("path") or config.get("wsOpts", {}).get("path", "/")
            if path:
                ws_opts["path"] = path
            host = config.get("host") or config.get("wsOpts", {}).get("headers", {}).get("Host", "")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        
        # GRPC 配置
        if network == "grpc":
            grpc_opts = {}
            serviceName = config.get("serviceName") or config.get("grpcOpts", {}).get("serviceName", "")
            if serviceName:
                grpc_opts["grpc-service-name"] = serviceName
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts
        
        # 验证必需字段
        if not proxy["server"] or not proxy["uuid"]:
            return None
        
        return proxy
    except Exception as e:
        return None

def parse_vless_complete(node):
    """完整解析 VLESS，包含 Reality 所有参数"""
    try:
        if not node.startswith("vless://"):
            return None
        parsed = urlparse(node)
        if not parsed.hostname:
            return None
        uuid = parsed.username or ""
        if not uuid:
            return None
        
        params = parse_qs(parsed.query)
        get_param = lambda k: params.get(k, [""])[0]
        remark = unquote(parsed.fragment or "VLESS")
        
        # 基础参数
        proxy = {
            "name": f"🌍",
            "type": "vless",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "uuid": uuid,
            "udp": True,
            "skip-cert-verify": True,
        }
        
        # 安全配置
        security = get_param("security")
        if security == "tls":
            proxy["tls"] = True
            proxy["sni"] = get_param("sni") or proxy["server"]
            # ALPN
            alpn = get_param("alpn")
            if alpn:
                proxy["alpn"] = [a.strip() for a in alpn.split(",")]
            # 指纹
            fp = get_param("fp")
            if fp:
                proxy["client-fingerprint"] = fp
        elif security == "reality":
            proxy["tls"] = True
            proxy["sni"] = get_param("sni") or proxy["server"]
            pbk = get_param("pbk")
            sid = get_param("sid")
            if pbk and sid:
                proxy["reality-opts"] = {"public-key": pbk, "short-id": sid}
            else:
                # 参数缺失，节点不可用
                return None
            fp = get_param("fp")
            if fp:
                proxy["client-fingerprint"] = fp
            else:
                proxy["client-fingerprint"] = "chrome"  # 默认指纹
        
        # Flow (XTLS)
        flow = get_param("flow")
        if flow:
            proxy["flow"] = flow
        
        # 网络配置
        type_param = get_param("type")
        if type_param == "ws":
            proxy["network"] = "ws"
            ws_opts = {}
            path = get_param("path")
            if path:
                ws_opts["path"] = path
            host = get_param("host")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        elif type_param == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = {}
            serviceName = get_param("serviceName")
            if serviceName:
                grpc_opts["grpc-service-name"] = serviceName
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts
        
        return proxy
    except Exception as e:
        return None

def parse_trojan_complete(node):
    """完整解析 Trojan"""
    try:
        if not node.startswith("trojan://"):
            return None
        parsed = urlparse(node)
        if not parsed.hostname:
            return None
        password = parsed.username or unquote(parsed.path.strip("/"))
        if not password:
            return None
        
        params = parse_qs(parsed.query)
        get_param = lambda k: params.get(k, [""])[0]
        
        proxy = {
            "name": f"🌍",
            "type": "trojan",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "password": password,
            "udp": True,
            "skip-cert-verify": True,
            "sni": get_param("sni") or proxy["server"],
        }
        
        # ALPN
        alpn = get_param("alpn")
        if alpn:
            proxy["alpn"] = [a.strip() for a in alpn.split(",")]
        
        # 指纹
        fp = get_param("fp")
        if fp:
            proxy["client-fingerprint"] = fp
        
        # WS 配置
        type_param = get_param("type")
        if type_param == "ws":
            proxy["network"] = "ws"
            ws_opts = {}
            path = get_param("path")
            if path:
                ws_opts["path"] = path
            host = get_param("host")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        
        return proxy
    except Exception as e:
        return None

def get_region_from_name(name):
    name_lower = name.lower()
    if any(k in name_lower for k in ["hk", "hongkong", "港"]): return "🇭🇰", "HK"
    elif any(k in name_lower for k in ["tw", "taiwan", "台"]): return "🇹🇼", "TW"
    elif any(k in name_lower for k in ["jp", "japan", "日"]): return "🇯🇵", "JP"
    elif any(k in name_lower for k in ["sg", "singapore", "新"]): return "🇸🇬", "SG"
    elif any(k in name_lower for k in ["kr", "korea", "韩"]): return "🇰🇷", "KR"
    elif any(k in name_lower for k in ["th", "thailand", "泰"]): return "🇹🇭", "TH"
    elif any(k in name_lower for k in ["vn", "vietnam", "越"]): return "🇻🇳", "VN"
    elif any(k in name_lower for k in ["us", "usa", "美"]): return "🇺🇸", "US"
    elif any(k in name_lower for k in ["uk", "britain", "英"]): return "🇬🇧", "UK"
    elif any(k in name_lower for k in ["de", "german", "德"]): return "🇩🇪", "DE"
    elif any(k in name_lower for k in ["fr", "france", "法"]): return "🇫🇷", "FR"
    elif any(k in name_lower for k in ["nl", "netherlands", "荷"]): return "🇳🇱", "NL"
    return "🌍", "OT"

def parse_node_complete(node):
    """统一节点解析入口"""
    node = node.strip()
    if not node or node.startswith("#"):
        return None
    if node.startswith("vmess://"):
        return parse_vmess_complete(node)
    elif node.startswith("vless://"):
        return parse_vless_complete(node)
    elif node.startswith("trojan://"):
        return parse_trojan_complete(node)
    return None

def is_base64(s):
    try:
        s = s.strip()
        if len(s) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s + "=" * (4 - len(s) % 4), validate=True)
        return True
    except:
        return False

def decode_base64_safe(content):
    try:
        content = content.strip()
        missing = len(content) % 4
        if missing:
            content += "=" * (4 - missing)
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        if "://" in decoded:
            return decoded
        return content
    except:
        return content

def fetch_url(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text.strip()
    except:
        return ""

def tcp_ping(host, port, timeout=2.0):
    if not host:
        return 9999
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        sock.connect((host, port))
        sock.close()
        return round((time.time() - start) * 1000, 1)
    except:
        return 9999

def is_asia_node(proxy):
    text = f"{proxy.get('name', '')} {proxy.get('server', '')}".lower()
    return any(k in text for k in ["hk", "hongkong", "tw", "taiwan", "jp", "japan", "sg", "singapore", "kr", "korea", "asia", "hkt", "th", "vn"])

def check_url_available(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code in (200, 301, 302)
    except:
        return False

# ==================== 主程序 ====================
def main():
    start_time = time.time()
    clash = ClashManager()
    namer = NodeNamer(style=NODE_NAME_STYLE, prefix=NODE_NAME_PREFIX)
    proxy_test_success = False
    
    print("=" * 50)
    print("🚀 Clash 节点筛选器 - v5.0 (完整参数解析)")
    print("=" * 50)
    
    try:
        # 1. 验证订阅源
        print("\n🔍 验证订阅源...")
        valid_urls = [url for url in CANDIDATE_URLS if check_url_available(url)]
        print(f"✅ 找到 {len(valid_urls)} 个可用订阅源\n")
        
        # 2. 抓取节点
        print("📥 抓取节点...")
        all_nodes = {}
        for url in valid_urls:
            content = fetch_url(url)
            if not content:
                continue
            if is_base64(content):
                content = decode_base64_safe(content)
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                proxy = parse_node_complete(line)
                if proxy:
                    unique_key = f"{proxy['server']}:{proxy['port']}:{proxy.get('uuid', proxy.get('password', ''))}"
                    node_hash = hashlib.md5(unique_key.encode()).hexdigest()
                    if node_hash not in all_nodes:
                        all_nodes[node_hash] = proxy
                if len(all_nodes) >= MAX_FETCH_NODES:
                    break
            if len(all_nodes) >= MAX_FETCH_NODES:
                break
        print(f"✅ 解析完成：{len(all_nodes)} 个唯一节点\n")
        
        # 3. TCP 延迟测试
        print("⚡ 第一阶段：TCP 延迟测试...")
        node_list = list(all_nodes.values())[:MAX_TCP_TEST_NODES]
        node_results = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {executor.submit(lambda p: (p, tcp_ping(p["server"], p["port"]), is_asia_node(p)), proxy): proxy for proxy in node_list}
            for i, future in enumerate(as_completed(futures)):
                proxy, latency, is_asia = future.result()
                if latency < MAX_LATENCY:
                    node_results.append({"proxy": proxy, "latency": latency, "is_asia": is_asia})
        node_results.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        print(f"✅ TCP 合格：{len(node_results)} 个（亚洲：{sum(1 for n in node_results if n['is_asia'])}）\n")
        
        # 4. 真实代理测速
        print("🚀 第二阶段：真实代理测速...")
        final_nodes = []
        tested_keys = set()
        
        if len(node_results) > 0:
            test_proxies = [n["proxy"] for n in node_results[:MAX_PROXY_TEST_NODES]]
            if clash.create_test_config(test_proxies) and clash.start():
                proxy_test_success = True
                print("📊 开始测速...\n")
                for i, item in enumerate(node_results[:MAX_PROXY_TEST_NODES]):
                    proxy = item["proxy"]
                    result = clash.test_proxy(proxy["name"])
                    unique_key = f"{proxy['server']}:{proxy['port']}"
                    if result["success"] and result["latency"] < MAX_PROXY_LATENCY:
                        if result["speed"] >= MIN_PROXY_SPEED or result["latency"] < 500:
                            flag, code = get_region_from_name(proxy.get("name", ""))
                            new_name = namer.generate_name(flag, int(result["latency"]), result["speed"], tcp_only=False)
                            proxy["name"] = new_name
                            final_nodes.append(proxy)
                            tested_keys.add(unique_key)
                            print(f"   ✅ {new_name}")
                    if len(final_nodes) >= MAX_FINAL_NODES:
                        break
                clash.stop()
                
                # 保底策略
                if len(final_nodes) < MAX_FINAL_NODES // 2:
                    print(f"\n⚠️ 测速合格不足，使用 TCP 补充...")
                    for item in node_results:
                        if len(final_nodes) >= MAX_FINAL_NODES:
                            break
                        proxy = item["proxy"]
                        unique_key = f"{proxy['server']}:{proxy['port']}"
                        if unique_key in tested_keys:
                            continue
                        if item["is_asia"] and item["latency"] < 500:
                            flag, code = get_region_from_name(proxy.get("name", ""))
                            proxy["name"] = namer.generate_name(flag, int(item["latency"]), tcp_only=True)
                            final_nodes.append(proxy)
                            tested_keys.add(unique_key)
                        elif item["latency"] < 250:
                            flag, code = get_region_from_name(proxy.get("name", ""))
                            proxy["name"] = namer.generate_name(flag, int(item["latency"]), tcp_only=True)
                            final_nodes.append(proxy)
                            tested_keys.add(unique_key)
        
        print(f"\n✅ 最终可用：{len(final_nodes)} 个")
        
        # 5. 输出配置
        print("📝 生成配置文件...")
        for proxy in final_nodes:
            proxy.pop("_latency", None)
            proxy.pop("_speed", None)
        
        clash_config = {
            "proxies": final_nodes,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in final_nodes], "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in final_nodes]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        
        with open("proxies.yaml", "w", encoding="utf-8") as f:
            yaml.dump(clash_config, f, allow_unicode=True, default_flow_style=False)
        
        # 统计
        total_time = time.time() - start_time
        asia_count = sum(1 for p in final_nodes if is_asia_node(p))
        print(f"\n📊 最终：{len(final_nodes)} 个 | 亚洲：{asia_count} 个 | 耗时：{total_time:.1f} 秒\n")
        
        # Telegram 推送
        if BOT_TOKEN and CHAT_ID:
            try:
                msg = f"""🚀 <b>节点更新完成</b>

📊 统计：
• 原始：{len(all_nodes)} | TCP 合格：{len(node_results)} | 最终：{len(final_nodes)}
• 亚洲节点：{asia_count} 个
• 耗时：{total_time:.1f} 秒

📁 订阅：
<code>https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml</code>"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
            except:
                pass
        
        print("🎉 完成！")
        
    finally:
        clash.stop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
