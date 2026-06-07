#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
from pathlib import Path
# v28.40: 确保当前文件所在目录在 sys.path 中（GitHub Actions 兼容）
_sys_path = str(Path(__file__).parent)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)
# v28.34: 从 parsers 包导入协议解析器
from parsers import (
    parse_vmess, parse_vless, parse_trojan, parse_trojan_go,
    parse_ss, parse_ssr, parse_hysteria, parse_hysteria2,
    parse_tuic, parse_snell, parse_http_proxy, parse_socks,
    parse_anytls, parse_node,
)
from utils import (
    generate_unique_id, _safe_port, is_pure_ip,
    is_cn_proxy_domain, CN_DOMAIN_BLACKLIST_RE,
    REALITY_SAFE_DOMAINS, NON_PROXY_PORTS,
    is_asia, is_china_mainland, mainland_friendly_score,
    get_region, _cc_to_flag, ASIA_REGIONS, NON_FRIENDLY_REGIONS,
    NON_FRIENDLY_PENALTY, PROTOCOL_SCORE,
    WORK_DIR, MAX_RETRIES, HEADERS_POOL,
)
# tcp_ping 已迁移到 core/config.py，从 network.tcp 导入
from sources import (
    discover_github_forks,
    crawl_telegram_channels, get_telegram_pages, crawl_telegram_page, crawl_single_channel,
    fetch, fetch_and_parse, async_fetch_and_parse, async_fetch_nodes,
    async_fetch_url, async_fetch_urls,
    check_subscription_quality, is_valid_url, clean_url,
    is_base64, decode_b64, is_yaml_content, parse_yaml_proxies,
    strip_url, check_url, check_url_fast,
)
# v28.41: Phase3 重构 - ClashManager/NodeNamer/format_proxy_to_link 迁移到 core/ 包
from core.clash import ClashManager
from core.namer import NodeNamer
from core.output import format_proxy_to_link
from core.config import (_NETWORK_BASELINE, check_network_baseline, ensure_clash_dir, create_session, session, tcp_ping)
from core.filter import filter_quality
# v28.42: 设置 stdout 编码为 utf-8，避免 Windows GBK 下 Unicode 输出报错
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# -*- coding: utf-8 -*-
"""
聚合订阅爬虫 v28.39 - 大陆优化版
作者：Anftlity | Version: 28.33
优化：httpx连接池 + 异步HTTP抓取 + sources.yaml配置外置 + Clash分批测速 + 大陆可用性优化 + ProxyNode数据模型
核心原则：三层严格过滤 + 全量优质源 + 零语法错误 + 最佳稳定性 + 大陆高可用
CHANGELOG v28.33:
- 【BUG修复】修复 5 处异常日志（resolve_domain, test_proxy 大陆测试部分）
- 【代码质量】语法检查全部通过，无已知语法错误
- 【生产就绪】代码已提交并推送至 GitHub

CHANGELOG v28.31:
- 【异常日志】修复 13 个 parse_*() 函数的异常日志（添加 as e）
- 【代码质量】消除静默异常，提升调试能力

CHANGELOG v28.27:
- 【ProxyNode迁移】parse_ss()/parse_vmess() 内部使用 ProxyNode 结构化存储
- 【向后兼容】返回 to_dict() 保持 dict 格式，现有代码无需修改
- 【代码质量】统一使用 ProxyNode 数据模型，减少 dict 散乱访问

CHANGELOG v28.25:
- 【数据模型】新增 ProxyNode dataclass（结构化节点存储，逐步替代 dict）
- 【去重改进】新增 dedup_key() 方法（基于协议/服务器/端口/认证信息的 MD5）
- 【兼容层】新增 _proxy_getattr() 辅助函数（兼容 ProxyNode 对象和普通 dict）
- 【版本统一】版本号从 v28.22 更新至 v28.25

CHANGELOG v28.22:
- 【线程安全】DNS缓存/_HISTORY_SCORES 加锁保护，消除并发竞态
- 【DNS修复】resolve_domain 移除全局 setdefaulttimeout，改用超时线程包装
- 【SSR修复】SSR序列化失败不再输出注释行，返回None避免客户端解析错误
- 【老挝修复】get_region移除"la"二字母匹配，改用"laos"词边界正则，防止Los Angeles误判
- 【缓存统一】移除过时_ip_geo_cache引用，统一使用limiter.get_geo()
- 【版本统一】版本号从v28.20更新至v28.22
- 【tcp_workers可配】从硬编码200改为环境变量TCP_WORKERS，上限500
CHANGELOG v28.19:
- 【关键修复】协议握手检测扩展到所有协议(vmess/vless/trojan/hysteria2/tuic/snell)
- 【可用率提升】修复节点通过TCP但协议握手失败导致实际不可用的问题
CHANGELOG v28.18:
- 【优先级调整】Telegram>Fork>固定源，固定源放最后
- 【输出优化】Telegram源优先抓取，固定源作为补充
CHANGELOG v28.17:
- 【SmartRateLimiter】域名级限流策略（ip-api/t.me严格，gstatic/CF宽松）
- 【IP缓存持久化】TTLCache + JSON文件，24h有效期，程序退出自动保存
- 【缓存加载】启动时自动加载历史缓存，减少重复查询
CHANGELOG v28.17:
- 【关键BUG修复】亚洲前置排序后又被sort覆盖，等于白做
- 【配额制节点选择】分亚洲/非亚洲两组排序，按60%配额合并
- 【is_asia增强】新增IP地理位置+SNI+域名TLD三级检测
- 【TCP测试优化】亚洲节点优先进入测试队列
- 【延迟放宽】亚洲TCP补充1500ms，非亚洲800ms
- 【权重提升】ASIA_PRIORITY_BONUS 50→80
- 【Bandit修复】B110/B112全部加日志，B323/B105加nosec
"""

import signal
import sys
from urllib.parse import urlparse, unquote, parse_qs
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from cn_cidr_data import CN_IP_RANGES as _CN_IP_RANGES_RAW  # cn_cidr_data.py 由 gen_cn_cidr.py 自动生成，不可添加自定义函数
import ipaddress
import httpx
import asyncio
import requests
import base64
import hashlib
import time
import json

# v28.45: GeoIP2 本地数据库支持（GitHub Actions 预下载）
import sys
import re
import yaml
import subprocess
import signal
import gzip
import shutil
import ssl
import urllib.request
import urllib.error

# v28.66a: 出口IP缓存（同IP只查一次）
_exit_ip_cache = {}
import urllib.parse
import threading
import random
import logging

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

from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from cachetools import TTLCache
from parsers.proxynode import ProxyNode  # v28.52: ProxyNode 迁移，解除循环导入

# ===== network 包（Phase2 提取）=====
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
# ===== core/history 包（Phase1+Phase2）=====
from core.history import (
    load_node_history, save_node_history,
    load_source_history, save_source_history,
    update_node_history, get_node_history_score,
    update_source_history, dynamic_source_weight,
    record_history, history_stability_score,
    get_node_history, get_source_history, get_history_scores,
    _NODE_HISTORY, _SOURCE_HISTORY,
    _NODE_HISTORY_LOCK, _SOURCE_HISTORY_LOCK,
    _HISTORY_SCORES, _HISTORY_SCORES_LOCK,
)


# v28.34: 从 parsers 包导入协议解析器




# ========== httpx 同步客户端（高性能连接池 + HTTP/2）==========
# ========== httpx 异步客户端（v29 异步抓取）==========
# threading, random, datetime 已在文件顶部导入
# ==================== 配置区 ====================
# v28.3: 可用率修复 — 恢复gstatic.com，改MAX_FINAL_NODES控制TCP补充上限
_yaml_urls, _yaml_chans, _yaml_repos = [], [], []
_cfg_path = Path(__file__).parent / "sources.yaml"
if _cfg_path.exists():
    try:
        with open(_cfg_path, encoding="utf-8") as _f:
            _data = yaml.safe_load(_f) or {}
            _raw_urls = _data.get("candidate_urls", [])
            _yaml_chans = _data.get("telegram_channels", [])
            _yaml_repos = _data.get("github_base_repos", [])
            # v28.23: 支持字典格式 {url: ..., weight: ...} 和纯字符串格式
            _yaml_urls = []
            for item in _raw_urls:
                if isinstance(item, dict):
                    _yaml_urls.append(item.get("url", ""))
                else:
                    _yaml_urls.append(str(item))
            _yaml_urls = [u for u in _yaml_urls if u]
            # github_base_repos 只保留纯字符串格式
            _yaml_repos = [str(r) for r in _yaml_repos if r]
        logging.debug(f"[sources.yaml] loaded {len(_yaml_urls)} urls / {len(_yaml_chans)} tg channels / {len(_yaml_repos)} github repos")
    except FileNotFoundError:
        logging.debug("[sources.yaml] not found, using empty config")
    except yaml.YAMLError as _e:
        logging.debug(f"[sources.yaml] YAML parse error, using empty config: {_e}")
    except PermissionError:
        logging.debug("[sources.yaml] permission denied, using empty config")


# _source_weight 已迁移到 core/history.py（通过 _source_weight 别名兼容）
# _INLINE_CANDIDATE_URLS 已废弃：CANDIDATE_URLS 直接从 sources.yaml 读取
CANDIDATE_URLS = _yaml_urls  # v28.34: 强制从 sources.yaml 读取，不再使用内联回退


TELEGRAM_CHANNELS = _yaml_chans  # v28.34: 强制从 sources.yaml 读取，不再使用内联回退
TIMEOUT = int(os.getenv("TIMEOUT", "12"))  # v28.21: 8→12秒，GitHub Actions 网络波动容忍

MAX_FETCH_NODES = int(os.getenv("MAX_FETCH_NODES", "5000"))     # v25: 扩大候选池（原3000）
MAX_TCP_TEST_NODES = int(os.getenv("MAX_TCP_TEST_NODES", "1200"))  # v25: TCP翻倍（原600，匹配README 10s阈值）
MAX_PROXY_TEST_NODES = int(os.getenv("MAX_PROXY_TEST_NODES", "1000"))  # v28.21: 800→1000，更多节点进入测速
MAX_FINAL_NODES = int(os.getenv("MAX_FINAL_NODES", "200"))       # v28.55: 200，给亚洲节点更多空间
MAX_LATENCY = int(os.getenv("MAX_LATENCY", "5000"))              # v28.8: 放宽到5s（大陆网络环境需要更宽松阈值）
MIN_PROXY_SPEED = float(os.getenv("MIN_PROXY_SPEED", "30"))  # v28.21: 30KB/s保活（原0过松）
MAX_PROXY_LATENCY = int(os.getenv("MAX_PROXY_LATENCY", "5000"))  # v28.8: 放宽到5s（大陆网络环境需要更宽松阈值）
# v28.55: 调整探针地址为国内服务，核心验证大陆可达性
TEST_URL = "https://myip.ipip.net/json"  # 国内IP查询服务，验证节点大陆可达性
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

CLASH_PORT = int(os.getenv("CLASH_PORT", "17890"))  # v28.23: 可配置
CLASH_API_PORT = int(os.getenv("CLASH_API_PORT", "19090"))  # v28.23: 可配置
CLASH_VERSION = os.getenv("CLASH_VERSION", "v1.19.0")  # v28.23: 可配置
NODE_NAME_PREFIX = "Anftlity"

# v28.57: 大陆端点测试改为评分降级（非淘汰），避免误杀真实可用节点；换入更多国内可达URL
# v28.68: 默认关闭大陆出口IP检测（api.ip.sb从GitHub Actions访问慢+堆积，导致超时）
ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
MAINLAND_TEST_URLS = [
    # v28.60: 大陆专属检测：只有从大陆IP访问才返回预期内容
    # 境外访问会被阻断或返回非预期内容，用于真正区分节点是否走大陆出口
    "http://beian.miit.gov.cn",
    # 2. 中国政府采购网（仅大陆可达）
    "http://www.ccgp.gov.cn",
    # 3. 央行征信中心（仅大陆可达）
    "http://www.pbccrc.org.cn",
    # 4. 百度搜索首页（境外访问会被限速或阻断）
    "http://www.baidu.com",
    # 5. 腾讯大陆服务器（境外访问延迟极高，基本不可用）
    "http://www.qq.com",
    # 6. 淘宝大陆服务器（境外访问会被限速）
    "http://www.taobao.com",
    # 7. 国内DNS：114.114.114.114 专属解析（仅大陆可达）
    "http://114.114.114.114/resolve?name=www.baidu.com&type=A",
]
# v28.57: 大陆测试改为评分降级而非直接淘汰，减少误杀
# v28.68: 默认关闭大陆出口IP检测（api.ip.sb从GitHub Actions访问慢+堆积，导致超时）
ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "0") == "1"
MAINLAND_SCORE_THRESHOLD = int(os.getenv("MAINLAND_SCORE_THRESHOLD", "30"))
# v28.58: 大陆可达性测试通过后的额外加分（可配置，默认20分）
MAINLAND_PASS_BONUS = int(os.getenv("MAINLAND_PASS_BONUS", "20"))

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "80"))  # v28.21: 50→80，Actions 可承受
# REQUESTS_PER_SECOND 已迁移至 utils.py
# 订阅源抓取并发（降速防封）
FETCH_WORKERS = int(os.getenv("FETCH_WORKERS", "150"))  # v28.21: 30→150，抓取并发提升

# [SPEED] GitHub Fork 发现限制（最大耗时来源）
MAX_FORK_REPOS = int(os.getenv("MAX_FORK_REPOS", "60"))  # v25: 提升fork发现量（原30）
MAX_FORK_URLS = 1500  # Fork URL总数上限

# ===== GitHub 多镜像池（v25: 扩展至8个，按速度排序，2026-04实测）=====
SUB_MIRRORS = [
    "https://gh.llkk.cc/",           # ~700ms  最快
    "https://ghproxy.net/",           # ~900ms  v25新增
    "https://gh-proxy.com/",          # ~1500ms
    "https://mirror.ghproxy.com/",    # ~1800ms v25新增
    "https://raw.iqiq.io/",           # ~2100ms
    "https://gh.api.99988866.xyz/",   # ~3000ms v25新增
    "https://ghps.cc/",               # ~3500ms v25新增
    "https://ghfast.top/",            # ~4000ms v25新增
]

# ===== CN IP 段过滤（精确 CIDR，来自 APNIC 官方数据，4219条）=====
# 由 cn_cidr_data.py 提供，替代原来的 /8 粒度（33条），大幅降低误杀率
CN_IP_RANGES = _CN_IP_RANGES_RAW

# ===== 端口质量评分 ======
HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}

# v28.14: 提高亚洲优先级权重
ASIA_PRIORITY_BONUS = int(os.getenv("ASIA_PRIORITY_BONUS", "40"))  # v28.49: 提高亚洲优先级（35→40）
TARGET_ASIA_RATIO = float(os.getenv("TARGET_ASIA_RATIO", "0.60"))  # v28.55: 提高亚洲目标比例（55%→60%）
ASIA_TCP_RELAX = 1800    # v28.55: 亚洲TCP补充延迟放宽到1800ms，让更多亚洲节点通过
ASIA_MIN_COUNT = int(os.getenv("ASIA_MIN_COUNT", "60"))  # v28.55: 提高亚洲保底数量（50→60）

# ===== 并发配置 ======
MAX_CONCURRENT_FETCH = 3
MAX_CONCURRENT_TCP = 60

# ===== DNS 缓存 ======
# v28.68: 历史记录模块已迁移到 core/history.py
from core.history import (
    load_node_history, load_source_history,
    save_source_history, save_node_history,
    update_source_history, dynamic_source_weight, source_weight,
    update_node_history, get_node_history_score,
    get_node_history, get_source_history, get_history_scores,
    NODE_HISTORY_FILE, SOURCE_HISTORY_FILE,
    _NODE_HISTORY, _SOURCE_HISTORY, _NODE_HISTORY_LOCK, _SOURCE_HISTORY_LOCK,
    _HISTORY_SCORES, _HISTORY_SCORES_LOCK,
)
# 兼容旧名
_load_node_history = load_node_history
_load_source_history = load_source_history
_save_node_history = save_node_history
_save_source_history = save_source_history
_update_source_history = update_source_history
_dynamic_source_weight = dynamic_source_weight
_source_weight = source_weight
_update_node_history = update_node_history
_get_node_history_score = get_node_history_score
_HISTORY_COMPAT_IMPORTED = True  # 标记：历史模块已从 core.history 导入





# _NETWORK_BASELINE 已迁移到 core/config.py

# ===== GitHub 直推配置 ======
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
GIST_ID = os.getenv("GIST_ID", "dc87627768298a4f6af8281cad97dfa3")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

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

GITHUB_BASE_REPOS = _yaml_repos  # v28.34: 强制从 sources.yaml 读取，不再使用内联定义


# ========== DNS 缓存（带TTL）==========# v28.8: 删除重复调用，已在文件开头调用
# requests.packages.urllib3.disable_warnings()


# ========== CN 过滤工具 ==========
# 已从 utils.py 导入 is_pure_ip / is_cn_proxy_domain，此处不再重复定义
_init_cn_lookup()











# ========== 网络基准检测 ==========



# ========== TLS 握手检测 ==========



# ========== HTTP HEAD 检测 ==========



# ========== 丢包率检测 ==========



# ========== 二次 TCP 验证 ==========

# BUGFIX v28.20: IPv6 兼容的 socket 创建
# ========== v28.6: 协议握手验证（TCP 层粗筛核心）==========





# ========== 内部 TCP Ping（兼容旧名 tcp_ping）==========




# BUGFIX v28.39: 添加 tcp_ping 别名（兼容主流程调用）






# v28.45: GeoIP2 本地数据库读取器（延迟初始化）
# BUGFIX v28.39: 添加 _ip_geo_batch（主流程依赖）








# [STAR] 节点解析器（保持不变）
# v28.34: 协议解析器已迁移到 parsers/ 包
# 请从 parsers 包导入:
# from parsers import (parse_vmess, parse_vless, parse_trojan, parse_trojan_go,
#     parse_ss, parse_ssr, parse_hysteria, parse_hysteria2,
#     parse_tuic, parse_snell, parse_http_proxy, parse_socks,
#     parse_anytls, parse_node)





# [STAR] Clash 管理（保持不变）


# [STAR] 节点命名（优化版：无后缀）


# [STAR] 协议链接转换（扩展版）


# [STAR] 主程序（集成 Fork 发现）












def main():
    st = time.time()

    # v28.53: 初始化 sources 配置访问层（必须在其他 sources 函数调用前）
    import sources.config
    sources.config.init_config()

    # v28.53: 加载节点历史记录
    _load_node_history()
    # v28.54: 加载源历史记录
    _load_source_history()

    # 注册信号处理（优化：自动保存数据）

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    logging.debug("[OK] 信号处理已注册（自动保存数据）")

    # v28.22: CN CIDR 数据有效期校验（gen_cn_cidr.py 每次运行会重新生成 cn_cidr_data.py，所以不能在那里加函数）
    try:
        _cidr_file = Path(__file__).parent / "cn_cidr_data.py"
        if _cidr_file.exists():
            _cidr_age_days = (time.time() - _cidr_file.stat().st_mtime) / 86400
            if _cidr_age_days > 30:
                logging.warning("[WARN] CN_CIDR 数据已过期 (%.0f 天)，建议运行 gen_cn_cidr.py 更新", _cidr_age_days)
    except (OSError, ValueError):
        logging.debug("Exception occurred", exc_info=True)
        # 校验失败不影响主流程

    clash = ClashManager()
    namer = NodeNamer()
    proxy_ok = False

    # v29: 异步抓取模式（可选启用）
    USE_ASYNC_FETCH = os.getenv("USE_ASYNC_FETCH", "0") == "1"

    logging.info("=" * 50)
    logging.info("[START] 聚合订阅爬虫 v28.39 - 大陆优化版")
    logging.info("作者：Anftlity | Version: 28.33")
    logging.info(f"异步抓取: {'[OK] 启用' if USE_ASYNC_FETCH else '[FAIL] 禁用（同步模式）'}")
    logging.info("=" * 50)

    all_urls = []

    try:
        # 1. Telegram 频道爬取（最高优先级）
        logging.info("[TG] 爬取 Telegram 频道（优先）...")
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=1, limits=20)
        tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
        logging.debug(f"[OK] Telegram 订阅：{len(tg_urls)} 个\n")

        # 2. Telegram 订阅 URL 加入队列（最高优先级）
        all_urls.extend(tg_urls)
        logging.debug(f"[OK] Telegram 订阅已加入队列：{len(tg_urls)} 个\n")

        # 3. GitHub Fork 发现（中等优先级）
        logging.info("[SEARCH] GitHub Fork 发现...")
        fork_subs = discover_github_forks()
        all_urls.extend(fork_subs)
        logging.info(f"[OK] Fork 来源：{len(fork_subs)} 个")

        # 4. 固定订阅源（最低优先级，放最后）
        logging.info("[LOAD] 加载固定订阅源（补充）...")
        fixed_urls = [strip_url(u) for u in CANDIDATE_URLS if strip_url(u)]
        all_urls.extend(fixed_urls)
        logging.info(f"[OK] 固定订阅源：{len(fixed_urls)} 个（跳过验证）")

        # 5. 去重
        all_urls = list(set(all_urls))
        logging.info(f"[STAT] 总订阅源：{len(all_urls)} 个")

        # v28.54: 按动态权重排序订阅源（高权重源优先抓取）
        url_weights = {u: _dynamic_source_weight(u) for u in all_urls}
        all_urls.sort(key=lambda u: -url_weights[u])
        logging.info(f"[STAT] 源权重排序完成（最高权重: {url_weights[all_urls[0]]:.1f}")

        # 6. 抓取节点（按all_urls顺序，Telegram已在前面）
        logging.info("[LOAD] 抓取节点...")
        nodes = {}
        yaml_count = 0
        txt_count = 0
        # v28.54: 追踪每个 URL 的抓取结果用于更新源历史
        url_results = {}  # url -> (success, node_count, asia_count)

        if USE_ASYNC_FETCH:
            # v29 异步抓取路径
            logging.info("[WEB] 使用异步抓取模式...")
            nodes, yaml_count, txt_count, url_results = asyncio.run(
                async_fetch_nodes(all_urls, MAX_FETCH_NODES)
            )
        else:
            # v28.x 同步抓取路径（保留）
            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
                futures = {ex.submit(fetch_and_parse, u): u for u in all_urls}
                completed = 0
                for future in as_completed(futures):
                    url = futures[future]
                    completed += 1
                    local_nodes, is_yaml = future.result()
                    node_count = len(local_nodes)
                    asia_count = sum(1 for p in local_nodes.values() if is_asia(p))
                    url_results[url] = (node_count > 0, node_count, asia_count)
                    for h, p in local_nodes.items():
                        if h not in nodes:
                            # v28.54: 使用动态权重覆盖静态权重
                            p["_src_weight"] = _dynamic_source_weight(url)
                            nodes[h] = p
                    # BUGFIX: 仅在有节点时才计入 yaml/txt 统计
                    if local_nodes:
                        if is_yaml:
                            yaml_count += 1
                        else:
                            txt_count += 1
                    if completed % 50 == 0:
                        logging.debug(f"   进度: {completed}/{len(all_urls)} | 节点: {len(nodes)}")
                    if len(nodes) >= MAX_FETCH_NODES:
                        break

        # v28.54: 更新所有源的历史记录
        for url, (success, node_count, asia_count) in url_results.items():
            _update_source_history(url, success, node_count, asia_count)

        logging.debug(f"[OK] 唯一节点：{len(nodes)} 个 (YAML源: {yaml_count}, TXT源: {txt_count})\n")

        if not nodes:
            logging.warning("[FAIL] 无有效节点!")
            return

        # 5.5 节点质量过滤（借鉴 wzdnzd/aggregator）
        logging.info("[SEARCH] 节点质量过滤...")
        before_filter = len(nodes)
        nodes = {h: p for h, p in nodes.items() if filter_quality(p)}
        after_filter = len(nodes)
        logging.info(f"[OK] 质量过滤：{before_filter} → {after_filter} 个（排除 {before_filter - after_filter} 个低质量节点)")

        if not nodes:
            logging.warning("[FAIL] 过滤后无有效节点!")
            return

        # v28.58: 同服务器跨协议优选去重
        # 同一服务器同一端口有多个协议节点时，只保留大陆友好度评分最高的那个
        # 避免同一 IP:Port 的多个协议节点占用宝贵的测试额度
        before_dedup_server = len(nodes)
        srvport_best = {}
        for h, p in nodes.items():
            srv = p.get("server", "").lower()
            port = str(p.get("port", 0))
            # 提取纯服务器地址（去掉端口）
            if srv.startswith("[") and "]" in srv:
                host = srv.split("]")[0][1:]
            elif ":" in srv and is_pure_ip(srv.split(":")[0]):
                host = srv.rsplit(":", 1)[0]
            else:
                host = srv.split(":")[0] if ":" in srv else srv
            key = f"{host}:{port}"
            mf = mainland_friendly_score(p)
            if key not in srvport_best or mf > srvport_best[key][1]:
                srvport_best[key] = (h, mf)
        # 只保留每个 server:port 评分最高的节点
        nodes = {h: nodes[h] for h, _ in srvport_best.values()}
        after_dedup_server = len(nodes)
        if before_dedup_server > after_dedup_server:
            logging.info(f"[OK] 同服务器跨协议去重：{before_dedup_server} → {after_dedup_server} 个（保留每IP:Port最优协议）")

        # 5.6 预查询 IP 地理位置（批量，用于节点区域识别）
        logging.info("[GEO] 预查询 IP 地理位置...")
        all_servers = set()
        for p in nodes.values():
            srv = p.get("server", "")
            # BUGFIX v28.20: IPv6 安全提取 host
            if srv.startswith("[") and "]" in srv:
                host = srv.split("]")[0][1:]
            elif is_pure_ip(srv) and ":" in srv:
                host = srv  # 纯 IPv6（如 fe80::1）整体就是 host
            elif ":" in srv:
                host = srv.split(":")[0]
            else:
                host = srv
            if is_pure_ip(host):
                all_servers.add(host)
        _ip_geo_batch(list(all_servers)[:500])  # 最多查 500 个

        # 6. TCP 测试（提高并发）
        logging.info("[SPEED] 第一层：TCP 延迟测试...")
        # v28.49: TCP测试队列优化——亚洲节点优先测试，提高亚洲测试比例
        all_nodes_list = list(nodes.values())
        asia_nodes_list = [n for n in all_nodes_list if is_asia(n)]
        non_asia_nodes_list = [n for n in all_nodes_list if not is_asia(n)]
        # v28.49: 亚洲节点优先，分配80%测试额度给亚洲（原为70%）
        asia_tcp_ratio = 0.80
        asia_quota = min(len(asia_nodes_list), int(MAX_TCP_TEST_NODES * asia_tcp_ratio))
        non_asia_quota = min(len(non_asia_nodes_list), MAX_TCP_TEST_NODES - asia_quota)
        # v28.49: 亚洲节点保底——至少测试120个亚洲节点（如果存在）
        asia_min_test = min(120, len(asia_nodes_list))
        if asia_quota < asia_min_test:
            asia_quota = asia_min_test
            non_asia_quota = min(len(non_asia_nodes_list), MAX_TCP_TEST_NODES - asia_quota)

        # v28.58: 亚洲节点按大陆友好度评分排序，高分节点优先进入TCP测试队列
        # 这样确保有限的TCP测试额度优先分配给更可能大陆友好的节点
        try:
            asia_nodes_list.sort(key=lambda n: mainland_friendly_score(n), reverse=True)
        except (ValueError, KeyError, TypeError):
            logging.debug("Asia nodes sort by mf_score failed, using original order")

        nlist = asia_nodes_list[:asia_quota] + non_asia_nodes_list[:non_asia_quota]
        logging.info(f"   [STAT] TCP测试队列：{len(asia_nodes_list[:asia_quota])} 亚洲"
              f" + {len(non_asia_nodes_list[:non_asia_quota])} 非亚洲 = {len(nlist)} 总计")
        nres = []



        # 提高并发数用于 TCP 测试（大幅提高）
        tcp_workers = min(int(os.getenv("TCP_WORKERS", "200")), 500)  # v28.22: 可配置，上限500
        with ThreadPoolExecutor(max_workers=tcp_workers) as ex:
            futures = {ex.submit(test_tcp_node, p): p for p in nlist}
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=2)  # 缩短超时
                    if result["latency"] < MAX_LATENCY:
                        nres.append(result)
                        # v28.53: TCP测试通过，更新历史记录
                        _update_node_history(result["proxy"], success=True)
                    else:
                        # v28.53: TCP测试失败，更新历史记录
                        _update_node_history(result["proxy"], success=False)
                    completed += 1
                    if completed % 50 == 0:
                        logging.debug(f"   进度：{completed}/{len(nlist)} | 合格：{len(nres)}")
                except (OSError, ValueError, TypeError):
                    logging.debug("Proxy test error for node")

        # v28.8: 利用 IP 地理位置优化排序（增强大陆友好性）



        # v28.49: 增强排序逻辑，大幅优先亚洲节点
        nres.sort(key=lambda x: (
            -_geo_score(x),  # IP 地理位置加权（亚洲加分，非友好区域扣分）
            -x["is_asia"],
            -(1 if is_reality_friendly(x["proxy"]) else 0),  # Reality节点优先
            -PROTOCOL_SCORE.get(x["proxy"].get("type", ""), 0) / 10.0,  # 协议评分加权
            x["latency"]
        ))
        # v28.49: 如果亚洲节点不足75%，调整排序策略强制提升（原为70%）
        asia_count = sum(1 for n in nres if n["is_asia"])
        if asia_count > 0 and asia_count < len(nres) * 0.75:
            # 重新排序：亚洲节点全部置顶，非亚洲按延迟排序
            asia_nodes = [n for n in nres if n["is_asia"]]
            non_asia_nodes = [n for n in nres if not n["is_asia"]]
            nres = asia_nodes + non_asia_nodes
            logging.info("   强制亚洲置顶：{} 亚洲 + {} 非亚洲".format(len(asia_nodes), len(non_asia_nodes)))
        # v28.14: 重新计算亚洲数量（排序后可能已调整）
        asia_count = sum(1 for n in nres if n["is_asia"])
        tcp_asia_pct = round(asia_count * 100 / max(len(nres), 1), 1)
        logging.debug(f"[OK] 第一层合格：{len(nres)} 个（亚洲：{asia_count}，占比：{tcp_asia_pct}%）\n")

        # 7. 真实测速 + TCP 保底（保留）
        logging.info("[START] 真实代理测速（分批）...")
        final = []
        tested = set()
        proxy_ok = False
        nres_untested = nres[:MAX_TCP_TEST_NODES]
        batch_size = MAX_PROXY_TEST_NODES
        batch_id = 0

        if len(nres) > 0:
            batch_enough = False  # BUGFIX: 标志位，用于内层 break 跳出后通知外层 while
            while len(final) < MAX_FINAL_NODES and nres_untested and not batch_enough:
                batch_id += 1
                batch_items = []
                for item in nres_untested:
                    if len(batch_items) >= batch_size:
                        break
                    k = f"{item['proxy']['server']}:{item['proxy']['port']}"
                    if k not in tested:
                        batch_items.append(item)
                if not batch_items:
                    break

                tprox = [item["proxy"] for item in batch_items]
                logging.info(f"[PACKAGE] 第{batch_id}批：{len(tprox)} 个节点...")

                if not clash.create_config(tprox) or not clash.start():
                    logging.warning("   [FAIL] Clash 启动失败，跳过本批")
                    clash.stop()
                    break

                proxy_ok = True



                try:
                    with ThreadPoolExecutor(max_workers=40) as tex:  # v28.7: 20→40 并发（Clash API 异步，不需要保守）
                        test_futures = {tex.submit(test_one, item, clash, namer): item for item in batch_items}
                        done_count = 0
                        for future in as_completed(test_futures):
                            try:
                                item, p, r = future.result(timeout=8)
                                done_count += 1
                                k = f"{p['server']}:{p['port']}"
                                # v28.49: 亚洲节点真实测速延迟放宽（2.0→2.5倍）
                                if r["success"] and (
                                    r["latency"] < MAX_PROXY_LATENCY
                                    or (is_asia(p) and r["latency"] < MAX_PROXY_LATENCY * 2.5)
                                ):
                                    srv = p.get("server", "")
                                    sni_val = p.get("sni", "") or p.get("servername", "")
                                    ws_opts = p.get("ws-opts", {})
                                    ws_host = (
                                        ws_opts.get("headers", {}).get("Host", "")
                                        if isinstance(ws_opts, dict) else ""
                                    )
                                    if ws_host:
                                        sni_val = ws_host
                                    fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                                    p["name"] = namer.generate(
                                        fl, int(r["latency"]), r["speed"], tcp=False,
                                        server=srv, sni=sni_val,
                                        mainland_pass=r.get("mainland_pass", False)
                                    )
                                    # v28.57: 附加真实大陆可达性测试结果，供 final_sort_key 使用
                                    p["_mainland_pass"] = r.get("mainland_pass", False)
                                    # v28.68: 移除硬筛大陆不可达节点的逻辑
                                    #         ENABLE_MAINLAND_TEST 默认关闭，TCP Ping+协议握手+Clash测速
                                    #         已能有效判断节点可用性，无需额外大陆出口IP检测
                                    final.append(p)
                                    tested.add(k)  # v28.12: restore
                                    # v28.53: 真实测速通过，更新历史记录
                                    _update_node_history(p, success=True)
                                    logging.info(f"   [OK] {p['name']}")
                                else:
                                    # v28.53: 真实测速失败，更新历史记录
                                    _update_node_history(p, success=False)
                                if len(final) >= MAX_FINAL_NODES:
                                    batch_enough = True  # BUGFIX: 通知外层 while 退出
                                    break
                                if done_count % 20 == 0:
                                    logging.info(f"   进度：{done_count}/{len(batch_items)} | 合格：{len(final)}")
                            except (OSError, ValueError, TypeError):
                                logging.debug("Batch proxy test error")
                    logging.debug(f"\n   第{batch_id}批完成：累计合格 {len(final)} 个\n")
                except (OSError, subprocess.SubprocessError, ValueError) as e:
                    logging.debug(f"   [FAIL] Clash 崩溃: {e}")
                    clash.stop()
                    break

            # TCP 补充
            if len(final) < MAX_FINAL_NODES:
                logging.warning(f"\n[WARN] 测速合格 {len(final)} 个/{MAX_FINAL_NODES} 目标，使用 TCP 补充...")
                for item in nres:
                    if len(final) >= MAX_FINAL_NODES:
                        break
                    p = item["proxy"]
                    k = f"{p['server']}:{p['port']}"
                    if k in tested:
                        continue
                    # v28.47: 亚洲TCP补充延迟进一步放宽
                    if item["is_asia"] and item["latency"] < ASIA_TCP_RELAX * 1.5:
                        tested.add(k)  # BUGFIX: 标记避免重复检测
                        srv = p.get("server", "")
                        sni_val = p.get("sni", "") or p.get("servername", "")
                        ws_opts = p.get("ws-opts", {})
                        ws_host = (
                            ws_opts.get("headers", {}).get("Host", "")
                            if isinstance(ws_opts, dict) else ""
                        )
                        if ws_host:
                            sni_val = ws_host
                        fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                        p["name"] = namer.generate(
                            fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val,
                            mainland_pass=False
                        ) + "[TCP]"
                        p['_mainland_pass'] = False  # v28.59: TCP节点标记大陆不可达
                        final.append(p)
                        logging.info(f"   [TCP] {p['name']}")
                    elif item["latency"] < 800:
                        # v28.16: 非亚洲TCP补充延迟提高（500→800）
                        tested.add(k)  # BUGFIX: 标记避免重复检测
                        srv = p.get("server", "")
                        sni_val = p.get("sni", "") or p.get("servername", "")
                        ws_opts = p.get("ws-opts", {})
                        ws_host = (
                            ws_opts.get("headers", {}).get("Host", "")
                            if isinstance(ws_opts, dict) else ""
                        )
                        if ws_host:
                            sni_val = ws_host
                        fl, cd = get_region(p.get("name", ""), server=srv, sni=sni_val)
                        p["name"] = namer.generate(
                            fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val,
                            mainland_pass=False
                        ) + "[TCP]"
                        p['_mainland_pass'] = False  # v28.59: TCP节点标记大陆不可达
                        final.append(p)
                        logging.info(f"   [TCP] {p['name']}")
                    else:
                        tested.add(k)

        final = final[:MAX_FINAL_NODES]

        # v28.57: 最终排序整合真实大陆可达性测试结果


        # v28.49: 配额制节点选择——提高亚洲比例
        # 分组排序后再按配额合并，柔性配额：保底+上限
        asia_final = sorted(
            [p for p in final if is_asia(p)],
            key=final_sort_key
        )
        non_asia_final = sorted(
            [p for p in final if not is_asia(p)],
            key=final_sort_key
        )

        target_asia = int(MAX_FINAL_NODES * TARGET_ASIA_RATIO)  # 柔性目标
        max_asia = int(MAX_FINAL_NODES * 0.75)  # v28.49: 上限75%
        min_asia = min(ASIA_MIN_COUNT, MAX_FINAL_NODES)  # 保底数量
        target_non_asia = MAX_FINAL_NODES - target_asia

        # 柔性配额：保底 ≤ 实际 ≤ 上限
        if len(asia_final) < min_asia:
            # 亚洲极少，全部保留，非亚洲补足
            actual_asia = len(asia_final)
            actual_non_asia = min(len(non_asia_final), MAX_FINAL_NODES - actual_asia)
            final = asia_final + non_asia_final[:actual_non_asia]
            logging.debug(f"   [WARN] 亚洲节点不足保底{min_asia}个，全部保留{actual_asia}个"
                  f" + 非亚洲{actual_non_asia}个")
        elif len(asia_final) <= target_asia:
            # 亚洲在保底~目标之间，全部保留高质量亚洲
            actual_non_asia = min(len(non_asia_final), MAX_FINAL_NODES - len(asia_final))
            final = asia_final + non_asia_final[:actual_non_asia]
            logging.debug(f"   [OK] 亚洲{len(asia_final)}个(柔性区间) + 非亚洲{actual_non_asia}个")
        elif len(asia_final) <= max_asia:
            # 亚洲在目标~上限之间，按目标配额
            final = asia_final[:target_asia] + non_asia_final[:target_non_asia]
            logging.debug(f"   [OK] 亚洲配额{target_asia}个 + 非亚洲配额{target_non_asia}个")
        else:
            # 亚洲过多，截到上限，非亚洲用剩余
            actual_non_asia = min(len(non_asia_final), MAX_FINAL_NODES - max_asia)
            final = asia_final[:max_asia] + non_asia_final[:actual_non_asia]
            logging.debug(f"   [OK] 亚洲截断{max_asia}个(上限) + 非亚洲{actual_non_asia}个")

        logging.debug(f"\n[OK] 最终：{len(final)} 个")
        logging.debug(f"[STAT] 真实测速：{'[OK]' if proxy_ok else '[FAIL]'}\n")

        # 8. 输出配置（保留）
        logging.debug("[NOTE] 生成配置...\n")
        final_names = {}
        unique_final = []
        for p in final:
            original_name = p["name"]
            count = final_names.get(original_name, 0)
            if count > 0:
                p["name"] = f"{original_name}-{count}"
            final_names[original_name] = count + 1
            unique_final.append(p)

        # BUGFIX v28.24: 输出前清洗内部字段，防止 _src_weight 等字段写入 YAML
        CLASH_FIELDS = {
            'name','type','server','port','udp','tfo','mptcp',
            'skip-cert-verify','sni','servername','tls','alpn','ca','cert','key',
            'client-fingerprint','obfs','obfs-password',
            'network','ws-opts','grpc-opts','h2-opts','http-opts',
            'reality-opts','flow','pinned-sha256','dialer-proxy',
            'cipher','password','plugin','plugin-opts',
            'uuid','alterId','aid',
            'protocol','protocol-param','obfs','obfs-param',
            'auth-str','up','down',
            'congestion-controller',
        }
        cleaned_final = []
        for p in unique_final:
            cleaned = {k: v for k, v in p.items() if not k.startswith('_') and k in CLASH_FIELDS}
            cleaned_final.append(cleaned)

        # v28.54: 输出源权重统计
        if _SOURCE_HISTORY:
            logging.debug("\n[STAT] 源权重统计（Top 10）:")
            sorted_sources = sorted(
                _SOURCE_HISTORY.items(),
                key=lambda x: _dynamic_source_weight(x[0]),
                reverse=True
            )[:10]
            for url, rec in sorted_sources:
                w = _dynamic_source_weight(url)
                success_rate = rec["success_count"] / max(rec["success_count"] + rec["fail_count"], 1)
                logging.debug(f"   • 权重{w:.1f} | 成功率{success_rate:.0%} | {url[:60]}...")

        # v28.52: 大陆路由规则（CN_DIRECT=1 启用）
        _cn_direct = os.getenv("CN_DIRECT", "1") == "1"
        _rules = []
        if _cn_direct:
            # 中国大陆域名后缀直连
            _cn_domains = [
                "cn", "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
                "taobao.com", "tmall.com", "jd.com", "baidu.com", "bilibili.com",
                "qq.com", "weibo.com", "alipay.com", "alicdn.com", "aliyun.com",
                "weixin.qq.com", "163.com", "126.com", "sina.com.cn", "sohu.com",
                "youku.com", "douyin.com", "xiaohongshu.com", "zhihu.com",
                "cnblogs.com", "csdn.net", "jianshu.com", "oschina.net",
                "gitee.com", "coding.net", "tencent.com", "tencentcloud.com",
                "alibaba.com", "alibaba-inc.com", "antgroup.com", "ele.me",
                "meituan.com", "dianping.com", "58.com", "ganji.com",
                "autohome.com.cn", "xcar.com.cn", "pcauto.com.cn",
                "ithome.com", "sspai.com", "geekpark.net", "36kr.com",
                "chinaunicom.com", "10010.com", "189.cn", "10086.cn",
                "bankcomm.com", "icbc.com.cn", "ccb.com", "boc.cn",
                "aliyuncs.com", "qcloud.com", "qiniu.com", "upaiyun.com",
            ]
            for _domain in _cn_domains:
                _rules.append(f"DOMAIN-SUFFIX,{_domain},DIRECT")
            # GeoIP 中国大陆直连
            _rules.append("GEOIP,CN,DIRECT")
            # 局域网直连
            _rules.append("IP-CIDR,127.0.0.0/8,DIRECT")
            _rules.append("IP-CIDR,172.16.0.0/12,DIRECT")
            _rules.append("IP-CIDR,192.168.0.0/16,DIRECT")
            _rules.append("IP-CIDR,10.0.0.0/8,DIRECT")
            _rules.append("IP-CIDR,100.64.0.0/10,DIRECT")
            _rules.append("IP-CIDR,169.254.0.0/16,DIRECT")
            _rules.append("IP-CIDR,224.0.0.0/4,DIRECT")
            _rules.append("IP-CIDR,240.0.0.0/4,DIRECT")
            _rules.append("IP-CIDR,255.255.255.255/32,DIRECT")
            # 常见国内DNS直连
            _rules.append("DOMAIN-SUFFIX,dns.alidns.com,DIRECT")
            _rules.append("DOMAIN-SUFFIX,doh.pub,DIRECT")
            _rules.append("DOMAIN-SUFFIX,dns.pub,DIRECT")
        # 兜底：其余走代理
        _rules.append("MATCH,[GEO] Select")

        cfg = {"proxies": cleaned_final,
               "proxy-groups": [{"name": "[START] Auto",
                                 "type": "url-test",
                                 "proxies": [p["name"] for p in cleaned_final],
                                 "url": TEST_URL,
                                 "interval": 300,
                                 "tolerance": 50},
                                {"name": "[GEO] Select",
                                 "type": "select",
                                 "proxies": ["[START] Auto"] + [p["name"] for p in cleaned_final]}],
               "rules": _rules}
        with open("proxies.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, Dumper=yaml.SafeDumper)

        # BUGFIX: 标准订阅格式 = 整块 base64 编码（大部分客户端要求此格式）
        plain_lines = '\n'.join(link for p in unique_final if (link := format_proxy_to_link(p)) is not None)  # v28.22: 过滤None
        b64_content = base64.b64encode(plain_lines.encode('utf-8')).decode('utf-8')
        with open("subscription.txt", "w", encoding="utf-8") as f:
            f.write(b64_content)

        # 统计
        tt = time.time() - st
        asia_ct = sum(1 for p in unique_final if is_asia(p))
        # v28.39: 从节点名称提取延迟用于统计
        min_lat = 9999
        for p in unique_final[:20]:
            m = re.search(r"(\d+)", p.get("name", ""))
            if m:
                lat = int(m.group(1))
                if 0 < lat < min_lat:
                    min_lat = lat
        if min_lat == 9999:
            min_lat = 0

        logging.debug("\n" + "=" * 180)
        logging.debug("[STAT] 统计结果")
        logging.debug("=" * 180)
        logging.debug(f"• Fork 来源：{len(fork_subs)}")
        logging.debug(f"• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总：{len(all_urls)}")
        logging.debug(f"• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：{len(unique_final)}")
        # v28.13: 修复亚洲占比计算（避免除零，使用更精确的计算）
        asia_pct = round(asia_ct * 100 / max(len(unique_final), 1), 1)
        logging.debug(f"• 亚洲：{asia_ct} 个 ({asia_pct}%)")
        logging.debug(f"• 最低延迟：{min_lat:.1f} ms")
        logging.debug(f"• 耗时：{tt:.1f} 秒")
        logging.debug("=" * 180 + "\n")

        # 9. Telegram 推送（保留）
        if BOT_TOKEN and CHAT_ID and REPO_NAME:
            try:
                ts = int(time.time())
                yaml_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/proxies.yaml?t={ts}"
                txt_raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/subscription.txt?t={ts}"
                repo_path = f"https://github.com/{REPO_NAME}/blob/main/"
                yaml_html_url = f"{repo_path}proxies.yaml"
                txt_html_url = f"{repo_path}subscription.txt"

                start_icon = "[START]"
                end_icon = "[CELEBRATE]"
                update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                msg = f"""{start_icon}<b>节点更新完成</b>{end_icon}

[STAT] <b>统计数据:</b>
• Telegram: {len(tg_urls)} | 固定：{len(fixed_urls)} | 总订阅：{len(all_urls)}
• Fork 来源：{len(fork_subs)}
• 原始：{len(nodes)} | TCP: {len(nres)} | 最终：<code>{len(unique_final)}</code> 个
• 亚洲：{asia_ct} 个 ({asia_pct}%)
• 最低延迟：{min_lat:.1f} ms
• 平均耗时：{tt:.1f} 秒
━━━━━━━━━━━━━━━━━━━━━━━

[SAVE] <b>直链下载:</b>
YAML: <code>{yaml_raw_url}</code>
TXT: <code>{txt_raw_url}</code>

[WEB] <b>网页查看:</b>
YAML: <a href="{yaml_html_url}">{yaml_html_url}</a>
TXT: <a href="{txt_html_url}">{txt_html_url}</a>

━━━━━━━━━━━━━━━━━━━━━━━

[WEB] <b>支持协议:</b> VMess | VLESS | Trojan | SS | Hysteria2 | Hysteria | TUIC | WireGuard
[PERSON]‍[PC] <b>作者:</b> Anftlity

<b>更新时间:</b> {update_time}"""
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                    timeout=10
                )
                logging.debug("[OK] Telegram通知已发送")
            except (requests.RequestException, OSError, ValueError) as e:
                logging.debug(f"[WARN] Telegram推送失败：{e}")
        logging.debug("[CELEBRATE] 任务完成！")

    except (OSError, ValueError, TypeError, KeyboardInterrupt) as e:
        logging.debug(f"\n[FAIL] 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        clash.stop()
        # v28.55: 程序退出时关闭异步HTTP客户端
        try:
            sync_close_async_http_client()
            logging.debug("[OK] 异步HTTP客户端已关闭")
        except (OSError, RuntimeError, asyncio.TimeoutError):
            logging.debug("关闭异步HTTP客户端失败", exc_info=True)
        # ISSUE-3-05: 关闭 requests session，避免资源泄漏
        try:
            session.close()
            logging.debug("[OK] Requests session 已关闭")
        except (OSError, ValueError):
            logging.debug("Exception occurred", exc_info=True)
        # v28.17: 程序退出时保存IP地理缓存
        try:
            limiter.save_geo_cache()
        except (OSError, ValueError):
            logging.debug("Exception occurred", exc_info=True)
        # v28.53: 程序退出时保存节点历史记录
        try:
            _save_node_history()
        except (OSError, ValueError):
            logging.debug("Exception occurred", exc_info=True)
        # v28.54: 程序退出时保存源历史记录
        try:
            _save_source_history()
        except (OSError, ValueError):
            logging.debug("Exception occurred", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.debug("\n[WARN] 用户中断执行")
        sys.exit(1)
    except (OSError, ValueError, TypeError) as e:
        logging.debug(f"\n[FAIL] 程序异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
