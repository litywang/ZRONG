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
TEST_URLS = [
    # 主池：全球可达的HTTP 204检测（优先HTTP，避免TLS问题）
    "http://cp.cloudflare.com/generate_204",
    "http://captive.apple.com/generation_204",
    "http://www.msftconnecttest.com/connecttest.txt",
    # HTTPS补充（如果HTTP失败，尝试HTTPS）
    "https://cp.cloudflare.com/generate_204",
    "https://captive.apple.com/generation_204",
    "https://www.gstatic.com/generate_204",
]
# 备用池：其他全球可用地址
TEST_URLS_BACKUP = [
    "http://www.msftconnecttest.com/connecttest.txt",
    "https://www.microsoft.com",
]

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
