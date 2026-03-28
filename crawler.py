#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clash 节点筛选器 - GitHub Actions v2.3 (修复目录创建问题)
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
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ==================== 配置区 ====================
CANDIDATE_URLS = [
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/V2RAY_RAW.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
TIMEOUT = 10

MAX_FETCH_NODES = 1000
MAX_TCP_TEST_NODES = 200
MAX_PROXY_TEST_NODES = 60
MAX_FINAL_NODES = 40

MAX_LATENCY = 500
MIN_PROXY_SPEED = 0.15
MAX_PROXY_LATENCY = 800
TEST_URL = "https://www.google.com/generate_204"

CLASH_PORT = 17890
CLASH_API_PORT = 19090
CLASH_VERSION = "v1.19.0"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")
GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

# ==================== 路径定义 ====================
WORK_DIR = Path(os.getcwd()) / "clash_temp"
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"

def ensure_clash_dir():
    """确保 clash_temp 目录存在"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return WORK_DIR

# ==================== Clash 管理 ====================
class ClashManager:
    def __init__(self):
        self.error_details = []
        self.process = None
        ensure_clash_dir()  # ✅ 初始化时创建目录
    
    def download_clash(self) -> bool:
        print("📥 下载 Mihomo 内核...")
        
        if CLASH_PATH.exists():
            print(f"✅ 内核已存在：{CLASH_PATH}")
            return True
        
        urls = [
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz",
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/mihomo-linux-amd64-{CLASH_VERSION}.gz",
        ]
        
        for i, download_url in enumerate(urls, 1):
            try:
                print(f"   尝试源 {i}/2...")
                
                temp_gz = WORK_DIR / "mihomo.gz"
                resp = requests.get(download_url, timeout=120, stream=True)
                resp.raise_for_status()
                
                with open(temp_gz, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"   下载完成：{temp_gz.stat().st_size} 字节")
                
                with gzip.open(temp_gz, "rb") as f_in:
                    with open(CLASH_PATH, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.chmod(CLASH_PATH, 0o755)
                temp_gz.unlink()
                
                if CLASH_PATH.exists():
                    result = subprocess.run([str(CLASH_PATH), "-v"], capture_output=True, timeout=5, cwd=str(WORK_DIR))
                    if result.returncode == 0:
                        version = result.stdout.decode().strip()[:60]
                        print(f"✅ 内核下载成功：{version}")
                        return True
                    else:
                        self.error_details.append(f"内核验证失败：{result.stderr.decode()[:200]}")
                else:
                    self.error_details.append("内核文件不存在")
                    
            except Exception as e:
                self.error_details.append(f"下载源 {i} 失败：{e}")
                print(f"   ❌ 源 {i} 失败：{e}")
                continue
        
        return False
    
    def create_test_config(self, proxies: list) -> bool:
        ensure_clash_dir()  # ✅ 关键修复！
        
        seen_names = {}
        unique_proxies = []
        for p in proxies[:MAX_PROXY_TEST_NODES]:
            name = p["name"]
            if name in seen_names:
                seen_names[name] += 1
                name = f"{name}_{seen_names[name]}"
            else:
                seen_names[name] = 1
            p_copy = p.copy()
            p_copy["name"] = name
            unique_proxies.append(p_copy)
        
        config = {
            "port": CLASH_PORT,
            "socks-port": CLASH_PORT + 1,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "info",
            "external-controller": f"0.0.0.0:{CLASH_API_PORT}",
            "secret": "",
            "ipv6": False,
            "unified-delay": True,
            "tcp-concurrent": True,
            "proxies": unique_proxies,
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": [p["name"] for p in unique_proxies]}],
            "rules": ["MATCH,TEST"]
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        print(f"✅ 测试配置已生成 ({len(unique_proxies)} 个节点)")
        return True
    
    def start(self) -> bool:
        ensure_clash_dir()
        
        if not CLASH_PATH.exists():
            if not self.download_clash():
                self.error_details.append("Clash 内核下载失败")
                return False
        
        print("🚀 启动 Clash 内核...")
        
        LOG_FILE.touch()
        
        try:
            with open(LOG_FILE, "w") as log_f:
                self.process = subprocess.Popen(
                    [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid,
                    cwd=str(WORK_DIR.absolute())
                )
            
            print("   等待 API 就绪...")
            for i in range(25):
                time.sleep(1)
                
                if self.process.poll() is not None:
                    try:
                        with open(LOG_FILE, "r") as f:
                            logs = f.read()
                    except:
                        logs = "无法读取日志"
                    self.error_details.append(f"Clash 进程异常退出（第{i+1}秒）")
                    self.error_details.append(f"日志：{logs[-500:]}")
                    print(f"❌ Clash 进程异常退出")
                    return False
                
                try:
                    resp = requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2)
                    if resp.status_code == 200:
                        version = resp.json().get("version", "unknown")
                        print(f"✅ Clash 启动成功 (v{version})")
                        return True
                except:
                    if i % 5 == 4:
                        print(f"   等待中... ({i+1}/25 秒)")
            
            self.error_details.append("API 就绪超时")
            return False
            
        except Exception as e:
            self.error_details.append(f"启动异常：{e}")
            return False
    
    def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except:
                pass
    
    def test_proxy(self, proxy_name: str) -> dict:
        result = {"success": False, "latency": 9999, "speed": 0.0, "error": ""}
        try:
            api_url = f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST"
            put_resp = requests.put(api_url, json={"name": proxy_name}, timeout=5)
            if put_resp.status_code != 204:
                result["error"] = f"切换：{put_resp.status_code}"
                return result
            
            time.sleep(0.2)
            proxies = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            
            start = time.time()
            resp = requests.get(TEST_URL, proxies=proxies, timeout=10, allow_redirects=False)
            latency = (time.time() - start) * 1000
            
            if resp.status_code in [200, 204, 301, 302]:
                speed_start = time.time()
                speed_resp = requests.get("https://speed.cloudflare.com/__down?bytes=524288", proxies=proxies, timeout=15)
                speed_elapsed = time.time() - speed_start
                speed = len(speed_resp.content) / max(0.5, speed_elapsed) / (1024 * 1024)
                
                result["success"] = True
                result["latency"] = round(latency, 1)
                result["speed"] = round(speed, 2)
            else:
                result["error"] = f"Status: {resp.status_code}"
        except Exception as e:
            result["error"] = str(e)[:80]
        return result
    
    def get_error_report(self) -> str:
        return "\n".join(self.error_details) if self.error_details else "无详细错误信息"

# ==================== 节点解析函数（与之前相同） ====================
def is_base64(s: str) -> bool:
    try:
        s = s.strip()
        if len(s) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s + "=" * (4 - len(s) % 4), validate=True)
        return True
    except:
        return False

def decode_base64_safe(content: str) -> str:
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

def fetch_url(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text.strip()
    except:
        return ""

def parse_vmess(node: str) -> dict | None:
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
        proxy = {
            "name": config.get("ps", config.get("remarks", "VMess"))[:20],
            "type": "vmess",
            "server": config.get("add", config.get("host", "")),
            "port": int(config.get("port", 443)),
            "uuid": config.get("id", ""),
            "alterId": int(config.get("aid", 0)),
            "cipher": "auto",
            "udp": True,
            "skip-cert-verify": True,
        }
        network = config.get("net", "tcp").lower()
        if network in ["ws", "h2", "grpc"]:
            proxy["network"] = network
        if config.get("tls") == "tls" or config.get("security") == "tls":
            proxy["tls"] = True
            proxy["sni"] = config.get("sni", config.get("host", proxy["server"]))
        if network == "ws":
            ws_opts = {}
            if config.get("path"):
                ws_opts["path"] = config.get("path")
            if config.get("host"):
                ws_opts["headers"] = {"Host": config.get("host")}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        if not proxy["server"] or not proxy["uuid"]:
            return None
        region = get_region_from_name(config.get("ps", ""))
        proxy["name"] = f"{region}{proxy['name']}-{proxy['server'][-5:]}"
        return proxy
    except:
        return None

def parse_vless(node: str) -> dict | None:
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
        remark = unquote(parsed.fragment or "VLESS")[:20]
        proxy = {
            "name": remark,
            "type": "vless",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "uuid": uuid,
            "udp": True,
            "skip-cert-verify": True,
        }
        security = get_param("security")
        if security in ["tls", "reality"]:
            proxy["tls"] = True
            if security == "reality":
                proxy["reality-opts"] = {"public-key": get_param("pbk") or "", "short-id": get_param("sid") or ""}
            proxy["sni"] = get_param("sni") or proxy["server"]
        if get_param("fp"):
            proxy["client-fingerprint"] = get_param("fp")
        if get_param("flow"):
            proxy["flow"] = get_param("flow")
        if get_param("type") == "ws":
            ws_opts = {}
            if get_param("path"):
                ws_opts["path"] = get_param("path")
            if get_param("host"):
                ws_opts["headers"] = {"Host": get_param("host")}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        region = get_region_from_name(remark)
        proxy["name"] = f"{region}{proxy['name']}-{proxy['server'][-5:]}"
        return proxy
    except:
        return None

def parse_trojan(node: str) -> dict | None:
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
        remark = unquote(parsed.fragment or "Trojan")[:20]
        proxy = {
            "name": remark,
            "type": "trojan",
            "server": parsed.hostname,
            "port": int(parsed.port or 443),
            "password": password,
            "udp": True,
            "skip-cert-verify": True,
            "sni": get_param("sni") or proxy["server"],
        }
        region = get_region_from_name(remark)
        proxy["name"] = f"{region}{proxy['name']}-{proxy['server'][-5:]}"
        return proxy
    except:
        return None

def get_region_from_name(name: str) -> str:
    name_lower = name.lower()
    if any(k in name_lower for k in ["hk", "hongkong", "港"]):
        return "🇭🇰"
    elif any(k in name_lower for k in ["tw", "taiwan", "台"]):
        return "🇹🇼"
    elif any(k in name_lower for k in ["jp", "japan", "日"]):
        return "🇯🇵"
    elif any(k in name_lower for k in ["sg", "singapore", "新"]):
        return "🇸🇬"
    elif any(k in name_lower for k in ["kr", "korea", "韩"]):
        return "🇰🇷"
    elif any(k in name_lower for k in ["us", "usa", "美"]):
        return "🇺🇸"
    elif any(k in name_lower for k in ["uk", "britain", "英"]):
        return "🇬🇧"
    return "🌍"

def parse_node(node: str) -> dict | None:
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

def tcp_ping(host: str, port: int, timeout: float = 2.0) -> float:
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

def is_asia_node(proxy: dict) -> bool:
    text = f"{proxy.get('name', '')} {proxy.get('server', '')}".lower()
    keywords = ["hk", "hongkong", "tw", "taiwan", "jp", "japan", "sg", "singapore", "kr", "korea", "asia", "hkt"]
    return any(k in text for k in keywords)

def check_url_available(url: str) -> bool:
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code in (200, 301, 302)
    except:
        return False

# ==================== 主程序 ====================
def main():
    start_time = time.time()
    clash = ClashManager()
    proxy_test_success = False
    
    print("=" * 50)
    print("🚀 Clash 节点筛选器 - GitHub Actions v2.3")
    print("=" * 50)
    print(f"📁 工作目录：{os.getcwd()}")
    print(f"🔧 GITHUB_ACTIONS: {GITHUB_ACTIONS}")
    print(f"📂 clash_temp: {WORK_DIR.absolute()}")
    print("=" * 50)
    
    try:
        print("\n🔍 验证订阅源...")
        valid_urls = []
        for url in CANDIDATE_URLS:
            if check_url_available(url):
                valid_urls.append(url)
                print(f"✅ {url[:50]}...")
            time.sleep(0.2)
        
        if not valid_urls:
            print("❌ 无可用订阅源")
            sys.exit(1)
        print(f"✅ 找到 {len(valid_urls)} 个可用订阅源\n")
        
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
                proxy = parse_node(line)
                if proxy:
                    unique_key = f"{proxy['server']}:{proxy['port']}:{proxy.get('uuid', proxy.get('password', ''))}"
                    node_hash = hashlib.md5(unique_key.encode()).hexdigest()
                    if node_hash not in all_nodes:
                        all_nodes[node_hash] = proxy
                if len(all_nodes) >= MAX_FETCH_NODES:
                    break
            if len(all_nodes) >= MAX_FETCH_NODES:
                break
            time.sleep(0.2)
        print(f"✅ 解析完成：{len(all_nodes)} 个唯一节点\n")
        
        print("⚡ 第一阶段：TCP 延迟测试...")
        node_list = list(all_nodes.values())[:MAX_TCP_TEST_NODES]
        node_results = []
        
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = {}
            for proxy in node_list:
                future = executor.submit(lambda p: (p, tcp_ping(p["server"], p["port"]), is_asia_node(p)), proxy)
                futures[future] = proxy
            
            for i, future in enumerate(as_completed(futures)):
                proxy, latency, is_asia = future.result()
                if latency < MAX_LATENCY:
                    node_results.append({"proxy": proxy, "latency": latency, "is_asia": is_asia})
                if (i + 1) % 50 == 0:
                    print(f"   已测试 {i + 1}/{len(node_list)} 个节点")
        
        node_results.sort(key=lambda x: (-x["is_asia"], x["latency"]))
        print(f"✅ TCP 合格：{len(node_results)} 个（亚洲：{sum(1 for n in node_results if n['is_asia'])}）\n")
        
        print("🚀 第二阶段：真实代理测速...")
        final_nodes = []
        
        if len(node_results) > 0:
            test_proxies = [n["proxy"] for n in node_results[:MAX_PROXY_TEST_NODES]]
            if clash.create_test_config(test_proxies):
                if clash.start():
                    proxy_test_success = True
                    print("📊 开始测速...\n")
                    for i, item in enumerate(node_results[:MAX_PROXY_TEST_NODES]):
                        if len(final_nodes) >= MAX_FINAL_NODES:
                            break
                        proxy = item["proxy"]
                        result = clash.test_proxy(proxy["name"])
                        
                        if result["success"] and result["latency"] < MAX_PROXY_LATENCY:
                            if result["speed"] >= MIN_PROXY_SPEED or result["latency"] < 300:
                                proxy["name"] = f"{proxy['name']}|⚡{result['latency']:.0f}ms|📥{result['speed']:.1f}MB"
                                final_nodes.append(proxy)
                                print(f"   ✅ {proxy['name']}")
                        if (i + 1) % 10 == 0:
                            print(f"   进度：{i + 1}/{min(len(node_results), MAX_PROXY_TEST_NODES)} | 合格：{len(final_nodes)}")
                    clash.stop()
                else:
                    print("⚠️ Clash 启动失败，使用 TCP 优化筛选")
                    for item in node_results[:MAX_FINAL_NODES * 2]:
                        if len(final_nodes) >= MAX_FINAL_NODES:
                            break
                        proxy = item["proxy"]
                        latency = item["latency"]
                        if item["is_asia"] and latency < 200:
                            proxy["name"] = f"{proxy['name']}|⚡{latency:.0f}ms"
                            final_nodes.append(proxy)
                        elif latency < 100:
                            proxy["name"] = f"{proxy['name']}|⚡{latency:.0f}ms"
                            final_nodes.append(proxy)
        else:
            print("⚠️ 无合格节点")
        
        print(f"\n✅ 最终可用：{len(final_nodes)} 个")
        print(f"📊 真实测速：{'✅ 已执行' if proxy_test_success else '❌ 未执行（TCP 降级筛选）'}\n")
        
        print("📝 生成配置文件...")
        for proxy in final_nodes:
            proxy.pop("_latency", None)
            proxy.pop("_speed", None)
        
        clash_config = {
            "proxies": final_nodes,
            "proxy-groups": [
                {"name": "🚀 Auto", "type": "url-test", "proxies": [p["name"] for p in final_nodes], "url": "https://www.google.com/generate_204", "interval": 300, "tolerance": 50},
                {"name": "🌍 Select", "type": "select", "proxies": ["🚀 Auto"] + [p["name"] for p in final_nodes]}
            ],
            "rules": ["MATCH,🌍 Select"]
        }
        
        with open("proxies.yaml", "w", encoding="utf-8") as f:
            yaml.dump(clash_config, f, allow_unicode=True, default_flow_style=False)
        
        nodes_info = [f"# {p['name']}" for p in final_nodes]
        base64_sub = base64.b64encode("\n".join(nodes_info).encode()).decode()
        with open("subscription_base64.txt", "w", encoding="utf-8") as f:
            f.write(base64_sub)
        
        error_report_file = Path("clash_error_report.txt")
        with open(error_report_file, "w", encoding="utf-8") as f:
            f.write(f"运行时间：{time.time() - start_time:.1f} 秒\n")
            f.write(f"真实测速：{'✅ 已执行' if proxy_test_success else '❌ 未执行'}\n\n")
            f.write("错误详情:\n")
            f.write(clash.get_error_report())
        
        total_time = time.time() - start_time
        asia_count = sum(1 for p in final_nodes if is_asia_node(p))
        latency_list = [tcp_ping(p["server"], p["port"]) for p in final_nodes[:20]] if final_nodes else []
        min_lat = min(latency_list) if latency_list else 0
        avg_lat = sum(latency_list) / len(latency_list) if latency_list else 0
        
        print(f"""
{'=' * 50}
📊 统计信息
{'=' * 50}
• 原始节点：{len(all_nodes)} 个
• TCP 合格：{len(node_results)} 个
• 最终可用：{len(final_nodes)} 个
• 亚洲节点：{asia_count} 个 ({asia_count*100//max(len(final_nodes),1)}%)
• 最低延迟：{min_lat:.1f} ms
• 平均延迟：{avg_lat:.1f} ms
• 真实测速：{'✅ 已执行' if proxy_test_success else '❌ 未执行'}
• 总耗时：{total_time:.1f} 秒
{'=' * 50}
        """)
        
        if clash.error_details:
            print("\n⚠️ 错误报告:")
            for err in clash.error_details[:5]:
                print(f"   • {err[:100]}")
        
        if BOT_TOKEN and CHAT_ID:
            try:
                msg = f"""🚀 <b>节点更新完成</b>

📊 统计：
• 原始：{len(all_nodes)} | TCP 合格：{len(node_results)} | 最终：{len(final_nodes)}
• 亚洲节点：{asia_count} 个
• 最低延迟：{min_lat:.1f} ms
• 真实测速：{'✅' if proxy_test_success else '❌'}
• 耗时：{total_time:.1f} 秒

📁 订阅：
<code>https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml</code>"""
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
                print("✅ Telegram 推送成功")
            except Exception as e:
                print(f"❌ Telegram 失败：{e}")
        
        print("\n🎉 完成！")
        
    finally:
        clash.stop()
        print("⚠️ clash_temp 目录已保留，供 artifact 上传")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
