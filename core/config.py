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
CLASH_VERSION = os.getenv("CLASH_VERSION", "v1.19.0")  # v28.23: 可配置
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
# v30.0 Phase 6b: 替换为实际下载测速URL
# 理由：cp.cloudflare.com/captive.apple.com 是CDN captive portal，
# 任何请求（含直接DNS解析不走代理）都会返回HTTP 204 → false positive
# 新URL：需代理路由+下载内容，speed>0才能通过
TEST_URLS = [
    # 主池：真实下载测速（需代理隧道 + 下载非零内容）
    "https://speed.cloudflare.com/__down?bytes=102400",   # 100KB下载测速
    "http://speedtest.tele2.net/1024KB.zip",             # 1MB下载测速
    "https://proof.utt.utt",                             # 法国速度测试
]
# 备用池：小文件+短超时（快速识别可用节点）
TEST_URLS_BACKUP = [
    "https://speed.hetzner.de/1MB.bin",                  # 1MB下载
    "https://download.hetzner.de/512KB.bin",             # 512KB下载
]

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
