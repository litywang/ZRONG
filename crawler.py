#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 - 大陆优化版
作者：Anftlity | Version: 28.72
优化：httpx连接池 + 异步HTTP抓取 + sources.yaml配置外置 + Clash分批测速 + 大陆可用性优化 + ProxyNode数据模型
核心原则：三层严格过滤 + 全量优质源 + 零语法错误 + 最佳稳定性 + 大陆高可用
"""

import os
import sys
import signal
import json
import time
import re
import yaml
import subprocess
import gzip
import shutil
import ssl
import threading
import random
import logging
import ipaddress
import httpx
import asyncio
import requests
import base64
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor, as_completed

# v28.40: 确保当前文件所在目录在 sys.path 中（GitHub Actions 兼容）
_sys_path = str(Path(__file__).parent)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

# v28.42: 设置 stdout 编码为 utf-8，避免 Windows GBK 下 Unicode 输出报错
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# v28.55: 配置日志级别（默认INFO，可通过环境变量LOG_LEVEL调整）
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# 抑制第三方库冗余日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# ==================== 协议解析器 ====================
from parsers import (
    parse_vmess, parse_vless, parse_trojan, parse_trojan_go,
    parse_ss, parse_ssr, parse_hysteria, parse_hysteria2,
    parse_tuic, parse_snell, parse_http_proxy, parse_socks,
    parse_anytls, parse_node,
)
from parsers.proxynode import ProxyNode  # v28.52: ProxyNode 数据模型

# ==================== 工具函数 ====================
from utils import (
    _safe_port, is_pure_ip,
    get_region, ASIA_REGIONS, NON_FRIENDLY_REGIONS,
    NON_FRIENDLY_PENALTY,
    WORK_DIR, MAX_RETRIES, HEADERS_POOL,
)

# ==================== 核心模块 ====================
from core.validator import (
    generate_unique_id, is_cn_proxy_domain,
    CN_DOMAIN_BLACKLIST_RE, REALITY_SAFE_DOMAINS, NON_PROXY_PORTS,
    is_asia, is_china_mainland,
)
from core.scorer import (
    mainland_friendly_score, _cc_to_flag, PROTOCOL_SCORE,
)
from core.main_flow import main
from core.clash import ClashManager
from core.namer import NodeNamer
from core.output import format_proxy_to_link
from core.filter import filter_quality

from core.config import (
    _NETWORK_BASELINE, check_network_baseline, ensure_clash_dir,
    create_session, session, tcp_ping,
    CLASH_PORT, CLASH_API_PORT, CLASH_VERSION, CLASH_PATH,
    CONFIG_FILE, LOG_FILE, TEST_URLS, TEST_URLS_BACKUP, ENABLE_MAINLAND_TEST,
)

# ==================== 网络模块 ====================
from network.client import (
    get_http_client, get_async_http_client,
    close_async_http_client, sync_close_async_http_client,
    retry_on_exception,
)
from network.dns import resolve_domain, _DNS_CACHE, _DNS_CACHE_LOCK, DNS_CACHE_TTL
from network.tcp import (
    check_node_reachability, tcp_verify, _tcp_ping, tcp_ping,
    packet_loss_check, _create_socket,
)
from network.tls import is_reality_friendly, tls_handshake_ok, http_head_check, _proto_handshake_ok
from network.geo import (
    is_cn_proxy_ip, _init_cn_lookup,
    SmartRateLimiter, limiter,
    _get_geoip2_reader, _geoip2_lookup, _ip_geo_batch,
)

# ==================== 历史记录模块 ====================
from core.history import (
    load_node_history, save_node_history,
    load_source_history, save_source_history,
    update_node_history, get_node_history_score,
    update_source_history, dynamic_source_weight, source_weight,
    record_history, history_stability_score,
    get_node_history, get_source_history, get_history_scores,
    NODE_HISTORY_FILE, SOURCE_HISTORY_FILE,
    _NODE_HISTORY, _SOURCE_HISTORY,
    _NODE_HISTORY_LOCK, _SOURCE_HISTORY_LOCK,
    _HISTORY_SCORES, _HISTORY_SCORES_LOCK,
)

# ==================== 数据源模块 ====================
from sources import (
    discover_github_forks,
    crawl_telegram_channels, get_telegram_pages, crawl_telegram_page, crawl_single_channel,
    fetch, fetch_and_parse, async_fetch_and_parse, async_fetch_nodes,
    async_fetch_url, async_fetch_urls,
    check_subscription_quality, is_valid_url, clean_url,
    is_base64, decode_b64, is_yaml_content, parse_yaml_proxies,
    strip_url, check_url, check_url_fast,
)

# ==================== CN IP 段数据 ====================
from cn_cidr_data import CN_IP_RANGES as _CN_IP_RANGES_RAW  # 由 gen_cn_cidr.py 自动生成，不可添加自定义函数
CN_IP_RANGES = _CN_IP_RANGES_RAW

# ==================== 配置区 ====================
# v28.34: 从 sources.yaml 读取配置（不再使用内联定义）
_yaml_urls, _yaml_chans, _yaml_repos = [], [], []
_cfg_path = Path(__file__).parent / "sources.yaml"
if _cfg_path.exists():
    try:
        with open(_cfg_path, encoding="utf-8") as _f:
            _data = yaml.safe_load(_f) or {}
            _raw_urls = _data.get("candidate_urls", [])
            _yaml_chans = _data.get("telegram_channels", [])
            _yaml_repos = _data.get("github_base_repos", [])
            
            _yaml_urls = []
            for item in _raw_urls:
                if isinstance(item, dict):
                    _yaml_urls.append(item.get("url", ""))
                else:
                    _yaml_urls.append(str(item))
            _yaml_urls = [u for u in _yaml_urls if u]
            
            _yaml_repos = [str(r) for r in _yaml_repos if r]
        
        logging.debug(f"[sources.yaml] loaded {len(_yaml_urls)} urls / {len(_yaml_chans)} tg channels / {len(_yaml_repos)} github repos")
    except Exception as _e:
        logging.debug(f"[sources.yaml] load failed, using empty config: {_e}")

CANDIDATE_URLS = _yaml_urls
TELEGRAM_CHANNELS = _yaml_chans
GITHUB_BASE_REPOS = _yaml_repos

# ==================== 运行参数 ====================
TIMEOUT = int(os.getenv("TIMEOUT", "12"))
MAX_FETCH_NODES = int(os.getenv("MAX_FETCH_NODES", "5000"))
MAX_TCP_TEST_NODES = int(os.getenv("MAX_TCP_TEST_NODES", "1200"))
MAX_PROXY_TEST_NODES = int(os.getenv("MAX_PROXY_TEST_NODES", "1000"))
MAX_FINAL_NODES = int(os.getenv("MAX_FINAL_NODES", "200"))
MAX_LATENCY = int(os.getenv("MAX_LATENCY", "5000"))
MIN_PROXY_SPEED = float(os.getenv("MIN_PROXY_SPEED", "30"))
MAX_PROXY_LATENCY = int(os.getenv("MAX_PROXY_LATENCY", "5000"))

TEST_URL = "https://myip.ipip.net/json"

MAINLAND_TEST_URLS = [
    "http://beian.miit.gov.cn",
    "http://www.ccgp.gov.cn",
    "http://www.pbccrc.org.cn",
    "http://www.baidu.com",
    "http://www.qq.com",
    "http://www.taobao.com",
    "http://114.114.114.114/resolve?name=www.baidu.com&type=A",
]

MAINLAND_SCORE_THRESHOLD = int(os.getenv("MAINLAND_SCORE_THRESHOLD", "30"))
MAINLAND_PASS_BONUS = int(os.getenv("MAINLAND_PASS_BONUS", "20"))

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "80"))
FETCH_WORKERS = int(os.getenv("FETCH_WORKERS", "150"))

MAX_FORK_REPOS = int(os.getenv("MAX_FORK_REPOS", "60"))
MAX_FORK_URLS = 1500

SUB_MIRRORS = [
    "https://gh.llkk.cc/",
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://raw.iqiq.io/",
    "https://gh.api.99988866.xyz/",
    "https://ghps.cc/",
    "https://ghfast.top/",
]

HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}

ASIA_PRIORITY_BONUS = int(os.getenv("ASIA_PRIORITY_BONUS", "40"))
TARGET_ASIA_RATIO = float(os.getenv("TARGET_ASIA_RATIO", "0.60"))
ASIA_TCP_RELAX = 1800
ASIA_MIN_COUNT = int(os.getenv("ASIA_MIN_COUNT", "60"))

MAX_CONCURRENT_FETCH = 3
MAX_CONCURRENT_TCP = 60

NODE_NAME_PREFIX = "Anftlity"

# ==================== GitHub 配置 ====================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "dc87627768298a4f6af8281cad97dfa3")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 11; Mobile; rv:84.0) Gecko/84.0 Firefox/84.0",
]

# ==================== 兼容旧名 ====================
_load_node_history = load_node_history
_load_source_history = load_source_history
_save_node_history = save_node_history
_save_source_history = save_source_history
_update_source_history = update_source_history
_dynamic_source_weight = dynamic_source_weight
_source_weight = source_weight
_update_node_history = update_node_history
_get_node_history_score = get_node_history_score


# ==================== 主程序入口 ====================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n[WARN] 用户中断执行")
        sys.exit(1)
    except (OSError, ValueError, TypeError) as e:
        logging.error(f"\n[FAIL] 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

