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

# ===== 测速 URL（v28.69 从 crawler.py 迁移）=====
# 测速URL优先国内服务，未通过国内测速的节点直接淘汰
# v28.57: 超时5s→8s，亚洲出口节点响应慢，5s太严苛；添加http/https混合降低TLS握手负担
TEST_URLS = [
    "http://myip.ipip.net/json",
    "https://myip.ipip.net/json",
    "http://ip.3322.org",
    "https://www.baidu.com",
    "https://www.qq.com",
    "https://www.taobao.com",
    "http://cp.cloudflare.com/generate_204",
    "http://captive.apple.com/generation_204",
]
# 原国际测速地址降级为备用（仅国内地址全部失败时启用）
# v28.57: 备用池移除了google（含TLS握手延迟），保留gstatic作为最终兜底
TEST_URLS_BACKUP = [
    "https://www.gstatic.com/generate_204",
    "http://www.msftconnecttest.com/connecttest.txt",
]

ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
