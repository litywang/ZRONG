#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZRONG 订阅聚合工具 - 入口文件
作者：Anftlity | Version: 28.99
重构 Phase A: 常量下沉至 config/constants.py，消除全局变量膨胀
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

# v28.42: 重定向 stdout 为 utf-8（解决 Windows GBK 与 Unicode 输出冲突）
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# v28.55: 配置日志级别，默认 INFO，可通过环境变量 LOG_LEVEL 覆盖
_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# ==================== 全局常量（来自 config/constants.py）====================
# v28.99: 所有常量统一从 config.constants 导入
import config.constants as _cfg
from config import constants as _const

# 从 constants 导入所有常量，使 crawler.py 保持向后兼容
from config.constants import (
    TIMEOUT, MAX_WORKERS, FETCH_WORKERS, MAX_CONCURRENT_FETCH, MAX_CONCURRENT_TCP,
    HEADERS_POOL, CANDIDATE_URLS, TELEGRAM_CHANNELS, GITHUB_BASE_REPOS,
    MAX_FETCH_NODES, MAX_TCP_TEST_NODES, MAX_PROXY_TEST_NODES, MAX_FINAL_NODES,
    MAX_LATENCY, MIN_PROXY_SPEED, MAX_PROXY_LATENCY, ASIA_TCP_RELAX,
    TEST_URL, MAINLAND_TEST_URLS, MAINLAND_SCORE_THRESHOLD, MAINLAND_PASS_BONUS,
    ASIA_PRIORITY_BONUS, TARGET_ASIA_RATIO, ASIA_MIN_COUNT,
    GITHUB_TOKEN, GIST_ID, MAX_FORK_REPOS, MAX_FORK_URLS,
    BOT_TOKEN, CHAT_ID, REPO_NAME,
    SUB_MIRRORS, NODE_NAME_PREFIX,
    HIGH_PORT_BONUS_THRESHOLD, COMMON_PORT_PENALTY,
    USER_AGENT_POOL,
)

# v28.99: 从 sources.yaml 加载配置到 constants 全局变量
_yaml_cfg = Path(__file__).parent / "sources.yaml"
if _yaml_cfg.exists():
    try:
        with open(_yaml_cfg, encoding="utf-8") as _f:
            _data = yaml.safe_load(_f) or {}
            _const.CANDIDATE_URLS = [
                (u.get("url") if isinstance(u, dict) else str(u))
                for u in (_data.get("candidate_urls") or [])
                if (u.get("url") if isinstance(u, dict) else str(u))
            ]
            _const.TELEGRAM_CHANNELS = [
                str(c) for c in (_data.get("telegram_channels") or [])
            ]
            _const.GITHUB_BASE_REPOS = [
                str(r) for r in (_data.get("github_base_repos") or [])
            ]
        logging.debug(
            f"[sources.yaml] loaded {len(_const.CANDIDATE_URLS)} urls / "
            f"{len(_const.TELEGRAM_CHANNELS)} tg channels / "
            f"{len(_const.GITHUB_BASE_REPOS)} github repos"
        )
    except Exception as _e:
        logging.debug(f"[sources.yaml] load failed, using empty config: {_e}")

# ==================== 协议解析 ====================
from parsers import (
    parse_vmess, parse_vless, parse_trojan, parse_trojan_go,
    parse_ss, parse_ssr, parse_hysteria, parse_hysteria2,
    parse_tuic, parse_snell, parse_http_proxy, parse_socks,
    parse_anytls, parse_node,
)
from parsers.proxynode import ProxyNode

# ==================== 工具函数 ====================
from utils import (
    _safe_port, is_pure_ip,
    get_region, ASIA_REGIONS, NON_FRIENDLY_REGIONS,
    NON_FRIENDLY_PENALTY,
    WORK_DIR, MAX_RETRIES, HEADERS_POOL as _UA_HEADERS,
    REQUESTS_PER_SECOND,
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
    strip_url,
)

# ==================== CN IP 数据 ====================
from network.cn_cidr_data import CN_IP_RANGES as _CN_IP_RANGES_RAW
CN_IP_RANGES = _CN_IP_RANGES_RAW

# ==================== 兼容性别名（向后兼容，避免旧代码断裂）====================
# v28.99: 删除旧的 _alias = real_function 批量赋值
# 仅保留 crawler.py 作为命名空间入口，所有常量均已通过 import 语句导入

# ==================== 入口 ====================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n[WARN] 用户中断执行")
        sys.exit(1)
    except (OSError, ValueError, TypeError) as e:
        logging.error(f"\n[FAIL] 运行异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
