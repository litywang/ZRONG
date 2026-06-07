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

from core.main_flow import main
