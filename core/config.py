# core/config.py - 配置与工具函数
# v28.42 Phase4 重构
# v28.69: 补全 CLASH_* 常量（从 crawler.py 迁移）

import logging
import random
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from network.tcp import _tcp_ping, tcp_ping
from utils import WORK_DIR, MAX_RETRIES, HEADERS_POOL

# ===== Clash 配置常量（v28.69 从 crawler.py 迁移）=====
CLASH_PORT = int(os.getenv("CLASH_PORT", "17890"))  # v28.23: 可配置
CLASH_API_PORT = int(os.getenv("CLASH_API_PORT", "19090"))  # v28.23: 可配置
CLASH_VERSION = os.getenv("CLASH_VERSION", "v1.18.7")  # v30.5: 更新为最新稳定版
CLASH_PATH = WORK_DIR / "mihomo"
CONFIG_FILE = WORK_DIR / "config.yaml"
LOG_FILE = WORK_DIR / "clash.log"

# ===== 网络基准（check_network_baseline 依赖）=====
_NETWORK_BASELINE = {"latency": 9999, "verified": False}

def check_network_baseline():
    """检测网络基准延迟"""
    for target, port in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
        lat = _tcp_ping(target, port, timeout=2.0)
        if lat < 9999:
            _NETWORK_BASELINE["latency"] = min(_NETWORK_BASELINE["latency"], lat)
            _NETWORK_BASELINE["verified"] = True
    return _NETWORK_BASELINE["latency"]



def ensure_clash_dir():
    """安全创建目录"""
    if WORK_DIR.exists() and not WORK_DIR.is_dir():
        try:
            WORK_DIR.unlink()
        except (OSError, PermissionError):
            logging.debug("Failed to unlink %s", WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

def create_session():
    session = requests.Session()
    retry = Retry(total=MAX_RETRIES, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(random.choice(HEADERS_POOL))
    return session

session = create_session()

# ===== 测速 URL（v29.04 从 crawler.py 迁移）=====
# v29.04: 简化测速URL，只保留全球可达的HTTP 204检测
# 原则：HTTP优于HTTPS（避免TLS问题），204优于200（避免body校验）
# 全球可达：Cloudflare + Apple + Microsoft（HTTP 204/无内容）
# v30.0 Phase 6f: 多层级测速URL池
# 之前false positive的根源是/proxies/TEST而非/proxies/GLOBAL（代理选择器bug），非URL本身
# 第一层：HTTP 204（最快，无body，全球CDN），第二层：HTTP纯文本（避免TLS开销）
# v30.3: 测速URL——204页面（轻量、全球CDN可达、适合EC delay API）
TEST_URLS = [
    "https://www.gstatic.com/generate_204",
    "https://cp.cloudflare.com/generate_204",
    "https://www.google.com/generate_204",
]
TEST_URLS_BACKUP = [
    "https://connectivitycheck.gstatic.com/generate_204",
    "https://www.apple.com/library/test/success.html",
]

# v30.3: 本地dialer-proxy上游代理（让节点流量走本地已有代理出去）
DIALER_PROXY_SERVER = os.getenv("DIALER_PROXY_SERVER", "127.0.0.1")
DIALER_PROXY_PORT = int(os.getenv("DIALER_PROXY_PORT", "3066"))  # SOCKS5端口
USE_DIALER_PROXY = os.getenv("USE_DIALER_PROXY", "1") == "1"
if USE_DIALER_PROXY:
    import socket
    _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _s.settimeout(2)
    if _s.connect_ex((DIALER_PROXY_SERVER, DIALER_PROXY_PORT)) != 0:
        logging.warning(f"[CONFIG] dialer-proxy {DIALER_PROXY_SERVER}:{DIALER_PROXY_PORT} 不可达，自动禁用")
        USE_DIALER_PROXY = False
    _s.close()

# v30.5: Karing 集成（直接用已运行的Karing Clash API测速，无需启动独立mihomo）
KARING_API_URL = os.getenv("KARING_API_URL", "http://127.0.0.1:3057")
KARING_API_SECRET = os.getenv("KARING_API_SECRET", "6e987380b2efa20a")
USE_KARING = os.getenv("USE_KARING", "0") == "1"

# HTTP代理（用于采集阶段，让TG/GitHub请求走代理）
HTTP_PROXY = os.getenv("HTTP_PROXY", "http://127.0.0.1:3067")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "http://127.0.0.1:3067")

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
