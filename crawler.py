#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
)
# tcp_ping 在 crawler.py 内部定义（_tcp_ping 的别名），不从 utils 导入
from sources import (
    discover_github_forks,
    crawl_telegram_channels, get_telegram_pages, crawl_telegram_page, crawl_single_channel,
    fetch, fetch_and_parse, async_fetch_and_parse, async_fetch_nodes,
    async_fetch_url, async_fetch_urls,
    check_subscription_quality, is_valid_url, clean_url,
    is_base64, decode_b64, is_yaml_content, parse_yaml_proxies,
    strip_url, check_url, check_url_fast,
)
# v28.39: 工具函数已迁移到 utils.py，请从 utils 导入
# v28.41: 设置 stdout 编码为 utf-8，避免 Windows GBK 下 Unicode 输出报错
import sys, io
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
try:
    import geoip2.database
    _GEOIP2_AVAILABLE = True
except ImportError:
    _GEOIP2_AVAILABLE = False
import socket
import os
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


def retry_on_exception(max_retries=2, backoff=1.0, jitter=0.5,
                      retry_on=(Exception,), return_on_fail=None):
    """通用重试装饰器。

    Args:
        max_retries: 最大重试次数（不含首次调用）
        backoff: 退避基数（秒），实际等待 = backoff * attempt + random jitter
        jitter: 随机抖动上限（秒）
        retry_on: 仅捕获这些异常类型进行重试
        return_on_fail: 全部重试失败后的返回值（默认 None）
    """
    import functools
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_retries:
                        wait = backoff * (attempt + 1) + random.uniform(0, jitter)
                        logging.debug(f"[retry] {func.__name__} attempt {attempt+1}/{max_retries} failed: {e}, waiting {wait:.1f}s")
                        time.sleep(wait)
            if last_exc is not None:
                logging.debug(f"[retry] {func.__name__} exhausted {max_retries} retries")
            return return_on_fail
        return wrapper
    return decorator


# ========== httpx 同步客户端（高性能连接池 + HTTP/2）==========
_http_client = None
_http_client_lock = threading.Lock()  # v28.8: 添加线程锁保护


def get_http_client():
    global _http_client
    if _http_client is None:
        with _http_client_lock:  # v28.8: 线程安全保护
            if _http_client is None:  # 双重检查锁定
                _http_client = httpx.Client(
                    timeout=httpx.Timeout(15.0, connect=8.0),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
                    follow_redirects=True,
                    verify=False  # nosec: B501 - Intentional for proxy testing with self-signed certs
                )
    return _http_client


# ========== httpx 异步客户端（v29 异步抓取）==========
_async_http_client = None
_async_http_client_lock = threading.Lock()  # v28.8: 添加线程锁保护


def get_async_http_client():
    global _async_http_client  # v28.13: must declare since function assigns to it
    if _async_http_client is None:
        with _async_http_client_lock:  # v28.8: 线程安全保护
            if _async_http_client is None:  # 双重检查锁定
                _async_http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(15.0, connect=8.0),
                    limits=httpx.Limits(
                        max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "200")),
                        max_keepalive_connections=int(os.getenv("HTTP_KEEPALIVE", "50")),
                        keepalive_expiry=30.0
                    ),
                    follow_redirects=True,
                    verify=False,  # nosec: B501
                    http2=True
                )
    return _async_http_client


async def close_async_http_client():
    """v28.52: 关闭全局异步HTTP客户端，修复RESOURCE_LEAK"""
    global _async_http_client
    if _async_http_client is not None:
        try:
            await _async_http_client.aclose()
            logging.debug("异步HTTP客户端已关闭")
        except (OSError, RuntimeError, asyncio.TimeoutError) as e:
            logging.warning(f"关闭异步HTTP客户端失败: {e}", exc_info=True)
        finally:
            _async_http_client = None


def sync_close_async_http_client():
    """v28.55: 同步包装器，用于非异步上下文关闭异步客户端"""
    if _async_http_client is not None:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                asyncio.create_task(close_async_http_client())
            else:
                loop.run_until_complete(close_async_http_client())
        except (OSError, RuntimeError, asyncio.TimeoutError):
            logging.debug("同步关闭异步客户端失败")


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


def _source_weight(url: str) -> int:
    """v28.23: 根据URL特征推断源权重（1-10），国内友好源得分更高。
    高权重源中解析出的节点在最终排序中获得额外加分。
    """
    u = url.lower()
    # 国内友好源（历史数据表明亚洲节点占比高）
    domestic_keywords = [
        "ermaozi", "peasoft", "aiboboxx", "mfuu", "freefq", "kxswa",
        "llywhn", "adiwzx", "changfengoss", "mymysub", "yeahwu",
        "mksshare", "bulianglin", "yiiss", "free18", "shaoyouvip",
        "yonggekkk", "vxiaodong", "wxloststar",
    ]
    for kw in domestic_keywords:
        if kw in u:
            return 8
    # 大聚合源（量大但亚洲占比一般）
    aggregator_keywords = ["mahdibland", "epodonios", "barry-far"]
    for kw in aggregator_keywords:
        if kw in u:
            return 5
    # 协议专项源（vless/hysteria2 对大陆更友好）
    if "vless" in u or "hysteria2" in u:
        return 7
    if "trojan" in u:
        return 6
    # 默认权重
    return 3

_INLINE_CANDIDATE_URLS = [
    # ============ 内联回退列表（sources.yaml 不存在时使用） ============
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/kxswa/v2rayfree/main/v2ray",
    "https://raw.githubusercontent.com/llywhn/v2ray-subscribe/main/v2ray.txt",

    # ============ 国际稳定源 ============
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vmess.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/trojan.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/ss.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/Eternity.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/trojan.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/trojan.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SS.json",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/VMESS.json",
    "https://raw.githubusercontent.com/baaif/Subconverter/master/sub/sub.ini",
    "https://shz.al/~WangCai",
    # ============ 额外高质量源 ============
    "https://raw.githubusercontent.com/fishball-2048/Subconverter/main/Sub/subconverter_subscribe.ini",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/SagerNet/sing-box/develop/Configs/proxies.json",
    "https://raw.githubusercontent.com/XTLS/Xray-core/master/examples/config.json",
    # v28.0: api.mrx.one 假token 已移除（由 sources.yaml 管理）
    # ============ 国内额外优质源 ============
    "https://raw.githubusercontent.com/adiwzx/freenode/main/v2ray.txt",
    "https://raw.githubusercontent.com/xingsin/test/main/list",
    "https://raw.githubusercontent.com/vxiaodong/zgq/main/sub",
    "https://raw.githubusercontent.com/changfengoss/pro/main/sub",
    "https://raw.githubusercontent.com/mymysub/V2raySubscribe/main/v2ray",
    "https://raw.githubusercontent.com/wxloststar/v2ray_sub/master/v2ray.txt",
    "https://raw.githubusercontent.com/aiboboxx/clashfree/main/clash",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yaml",
    "https://raw.githubusercontent.com/yonggekkk/yonggekkk.github.io/master/v2raylink.txt",
    "https://raw.githubusercontent.com/ONGKB/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/yeahwu/v2ray-wuzhi/main/v2ray",
    "https://raw.githubusercontent.com/v2ray-free/v2ray-free/master/v2ray",
    "https://raw.githubusercontent.com/ssrsub/ssr/master/v2ray",
    # ============ 国际额外源 ============
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/Splitted-By-Protocol/ss.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/ss.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/sub_merge.txt",
    # ============ v25新增国内友好源 ============
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mksshare/mksshare.github.io/main/sub",
    "https://raw.githubusercontent.com/yiiss/ProxyScrape/main/sub",
    "https://raw.githubusercontent.com/bulianglin/demo/main/sub",
    "https://raw.githubusercontent.com/chengaikun/V2RayNode/main/list",
    "https://raw.githubusercontent.com/xream/awesome-vpn/main/sub",
    "https://raw.githubusercontent.com/FreeFlyingMan/v2rayfree/main/v2ray",
    "https://raw.githubusercontent.com/NastyaFan/mihomo-clash/main/proxy",
    # ============ v25: 2026-04-20 最新大陆优质源（12个高频维护） ============
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml",
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt",
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/all.yaml",
    "https://raw.githubusercontent.com/shaoyouvip/free/refs/heads/main/base64.txt",
    "https://raw.githubusercontent.com/a2470982985/getNode/main/clash.yaml",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://nodesfree.github.io/clashnode/clash.yaml",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hysteria2.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/tuic.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/vless.txt",
]
CANDIDATE_URLS = _yaml_urls  # v28.34: 强制从 sources.yaml 读取，不再使用内联回退


TELEGRAM_CHANNELS = _yaml_chans  # v28.34: 强制从 sources.yaml 读取，不再使用内联回退

HEADERS_POOL = [{
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}, {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}, {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X)"
    " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
}]
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
TEST_URLS = [
    "https://myip.ipip.net/json",
    "https://www.baidu.com",
    "https://www.taobao.com",
    "https://www.qq.com",
    "https://ip.3322.org",
]
# 原国际测速地址降级为备用（仅国内地址全部失败时启用）
TEST_URLS_BACKUP = [
    "https://www.gstatic.com/generate_204",
    "https://www.google.com",
]

CLASH_PORT = int(os.getenv("CLASH_PORT", "17890"))  # v28.23: 可配置
CLASH_API_PORT = int(os.getenv("CLASH_API_PORT", "19090"))  # v28.23: 可配置
CLASH_VERSION = os.getenv("CLASH_VERSION", "v1.19.0")  # v28.23: 可配置
NODE_NAME_PREFIX = "Anftlity"

# v28.23: 大陆端点测试（通过代理访问大陆CDN，验证实际可用性）
ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "1") == "1"
MAINLAND_TEST_URLS = [
    "http://myip.ipip.net/json",
    "http://cp.cloudflare.com/generate_204",
    "http://captive.apple.com/generation_204",
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.msftconnecttest.com/connecttest.txt",
    "http://www.qualcomm.com/generate_204",
]
# v28.55: 大陆测试改为强制项，未通过则直接淘汰节点
ENABLE_MAINLAND_TEST = os.getenv("ENABLE_MAINLAND_TEST", "1") == "1"  # 默认强制开启
MAINLAND_SCORE_THRESHOLD = int(os.getenv("MAINLAND_SCORE_THRESHOLD", "30"))

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "80"))  # v28.21: 50→80，Actions 可承受
REQUESTS_PER_SECOND = 6.0     # v25: 提速（原3.0，Actions美国机房可承受）
MAX_RETRIES = int(os.getenv("CLASH_TEST_RETRY", "2"))  # v28.21: 1→2，重试容错

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
_DNS_CACHE = {}
_DNS_CACHE_LOCK = threading.Lock()  # v28.22: 线程安全锁
DNS_CACHE_TTL = 300

# ===== 历史稳定性记录 ======
_HISTORY_SCORES = {}
_HISTORY_SCORES_LOCK = threading.Lock()  # v28.22: 线程安全锁

# v28.53: 节点历史可用性追踪（node_history.json）
NODE_HISTORY_FILE = Path("node_history.json")
_NODE_HISTORY = {}
_NODE_HISTORY_LOCK = threading.Lock()

# v28.54: 智能源权重系统（source_history.json）
SOURCE_HISTORY_FILE = Path("source_history.json")
_SOURCE_HISTORY = {}
_SOURCE_HISTORY_LOCK = threading.Lock()


def _load_node_history():
    """加载节点历史记录。"""
    global _NODE_HISTORY
    if NODE_HISTORY_FILE.exists():
        try:
            with open(NODE_HISTORY_FILE, "r", encoding="utf-8") as f:
                _NODE_HISTORY = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            _NODE_HISTORY = {}
    else:
        _NODE_HISTORY = {}


def _load_source_history():
    """加载源历史记录。"""
    global _SOURCE_HISTORY
    if SOURCE_HISTORY_FILE.exists():
        try:
            with open(SOURCE_HISTORY_FILE, "r", encoding="utf-8") as f:
                _SOURCE_HISTORY = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            _SOURCE_HISTORY = {}
    else:
        _SOURCE_HISTORY = {}


def _save_source_history():
    """保存源历史记录。"""
    try:
        with open(SOURCE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_SOURCE_HISTORY, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        logging.debug("Save source history failed", exc_info=True)


def _save_node_history():
    """保存节点历史记录。"""
    try:
        with open(NODE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_NODE_HISTORY, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        logging.debug("Save node history failed", exc_info=True)


def _update_source_history(url: str, success: bool, node_count: int = 0, asia_count: int = 0):
    """更新单个源的历史记录。
    
    Args:
        url: 订阅源 URL
        success: 本次抓取是否成功
        node_count: 本次抓取的节点数
        asia_count: 本次抓取的亚洲节点数
    """
    now = datetime.now().isoformat()
    with _SOURCE_HISTORY_LOCK:
        if url not in _SOURCE_HISTORY:
            _SOURCE_HISTORY[url] = {
                "first_seen": now,
                "last_seen": now,
                "success_count": 0,
                "fail_count": 0,
                "total_nodes": 0,
                "total_asia_nodes": 0,
                "fetch_count": 0,
                "history": [],  # 最近10次记录
            }
        rec = _SOURCE_HISTORY[url]
        rec["last_seen"] = now
        rec["fetch_count"] += 1
        if success:
            rec["success_count"] += 1
        else:
            rec["fail_count"] += 1
        if node_count > 0:
            rec["total_nodes"] += node_count
            rec["total_asia_nodes"] += asia_count
            # 保留最近10次记录
            rec["history"].append({
                "time": now,
                "nodes": node_count,
                "asia_nodes": asia_count,
            })
            if len(rec["history"]) > 10:
                rec["history"] = rec["history"][-10:]


def _dynamic_source_weight(url: str) -> float:
    """计算动态源权重（1-20分）。
    
    融合静态规则 + 历史表现动态计算：
    - 静态规则：URL 关键词硬编码（1-10分）
    - 动态因子：成功率、亚洲比例、新鲜度、趋势
    
    公式：static * (0.4 + success_rate * 1.2) * (0.8 + asia_rate * 0.4) * recency * trend
    """
    # 1. 静态基础分（1-10）
    static = float(_source_weight(url))
    
    with _SOURCE_HISTORY_LOCK:
        rec = _SOURCE_HISTORY.get(url)
        if not rec:
            # 无历史数据：返回静态分 * 中性因子（1.0）
            return round(static * 1.0, 1)
        
        # 2. 成功率因子（0.4 - 1.6）
        total_fetches = rec["success_count"] + rec["fail_count"]
        success_rate = rec["success_count"] / total_fetches if total_fetches > 0 else 0.5
        success_factor = 0.4 + success_rate * 1.2
        
        # 3. 亚洲比例因子（0.8 - 1.2）
        total_nodes = rec["total_nodes"]
        asia_rate = rec["total_asia_nodes"] / total_nodes if total_nodes > 0 else 0.3
        asia_factor = 0.8 + asia_rate * 0.4
        
        # 4. 新鲜度因子（0.4 - 1.3）
        last_seen = datetime.fromisoformat(rec["last_seen"])
        days_since = (datetime.now() - last_seen).total_seconds() / 86400
        if days_since < 1:
            recency = 1.3
        elif days_since < 7:
            recency = 1.0
        elif days_since < 30:
            recency = 0.7
        else:
            recency = 0.4
        
        # 5. 趋势因子（0.7 - 1.9）
        history = rec.get("history", [])
        if len(history) >= 3:
            recent = sum(h["nodes"] for h in history[-3:]) / 3.0
            older = sum(h["nodes"] for h in history[:-3]) / max(len(history) - 3, 1)
            if older > 0:
                trend = 0.7 + min(recent / older, 1.2) * 1.0
            else:
                trend = 1.0
        else:
            trend = 1.0
        
        # 综合计算
        weight = static * success_factor * asia_factor * recency * trend
        # 限制在 1-20 范围
        weight = max(1.0, min(20.0, weight))
        return round(weight, 1)


def _update_node_history(proxy: dict, success: bool):
    """更新单个节点的历史记录。
    
    Args:
        proxy: 节点配置字典
        success: 本次测试是否成功
    """
    # 节点指纹作为唯一键
    uid = proxy.get("uuid", "")
    pwd = proxy.get("password", "")
    auth = uid or pwd or ""
    host = proxy.get("sni", "") or proxy.get("servername", "") or proxy.get("server", "")
    path = ""
    ws_opts = proxy.get("ws-opts", {})
    if isinstance(ws_opts, dict):
        path = ws_opts.get("path", "")
    key = hashlib.md5(
        f"{proxy.get('type', '')}|{proxy.get('server', '')}|{proxy.get('port', 0)}|{auth}|{path}|{host}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    
    now = datetime.now().isoformat()
    with _NODE_HISTORY_LOCK:
        if key not in _NODE_HISTORY:
            _NODE_HISTORY[key] = {
                "first_seen": now,
                "last_seen": now,
                "success_count": 0,
                "fail_count": 0,
                "availability": 0.0,
            }
        rec = _NODE_HISTORY[key]
        rec["last_seen"] = now
        if success:
            rec["success_count"] += 1
        else:
            rec["fail_count"] += 1
        total = rec["success_count"] + rec["fail_count"]
        rec["availability"] = round(rec["success_count"] / total, 3) if total > 0 else 0.0


def _get_node_history_score(proxy: dict) -> float:
    """获取节点历史可用性评分（0-20分）。
    
    高可用性节点获得额外加分，新节点中性评分。
    """
    uid = proxy.get("uuid", "")
    pwd = proxy.get("password", "")
    auth = uid or pwd or ""
    host = proxy.get("sni", "") or proxy.get("servername", "") or proxy.get("server", "")
    path = ""
    ws_opts = proxy.get("ws-opts", {})
    if isinstance(ws_opts, dict):
        path = ws_opts.get("path", "")
    key = hashlib.md5(
        f"{proxy.get('type', '')}|{proxy.get('server', '')}|{proxy.get('port', 0)}|{auth}|{path}|{host}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    
    with _NODE_HISTORY_LOCK:
        rec = _NODE_HISTORY.get(key)
        if not rec:
            return 10.0  # 新节点：中性评分
        avail = rec["availability"]
        total = rec["success_count"] + rec["fail_count"]
        # 可用性评分：根据历史可用率加权
        # 样本量越大，评分越可信
        confidence = min(total / 10.0, 1.0)  # 10次以上达到最大置信度
        score = avail * 20.0 * confidence + 10.0 * (1 - confidence)
        return round(score, 1)

# ===== 网络基准 ======
_NETWORK_BASELINE = {"latency": 9999, "verified": False}

# ===== GitHub 直推配置 ======
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN"))
GIST_ID = os.getenv("GIST_ID", "dc87627768298a4f6af8281cad97dfa3")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

WORK_DIR = Path(os.getcwd()) / "clash_temp"
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

def resolve_domain(domain, timeout=3):
    if not domain or not isinstance(domain, str):
        return None
    now = time.time()
    with _DNS_CACHE_LOCK:  # v28.22: 线程安全读缓存
        if domain in _DNS_CACHE:
            ip, ts = _DNS_CACHE[domain]
            if now - ts < DNS_CACHE_TTL:
                return ip
    # v28.22: 用 socket.create_connection 替代 setdefaulttimeout
    # 原实现临时修改全局 default timeout，多线程下互相干扰
    try:
        # 使用 getaddrinfo 而非 gethostbyname，支持超时控制
        # socket.getaddrinfo 没有独立超时参数，改用线程+超时包装
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exc:
            future = exc.submit(socket.gethostbyname, domain)
            try:
                ip = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                ip = None
        with _DNS_CACHE_LOCK:  # v28.22: 线程安全写缓存
            _DNS_CACHE[domain] = (ip, now)
        return ip
    except (socket.gaierror, socket.timeout, OSError):
        with _DNS_CACHE_LOCK:  # v28.22: 线程安全写缓存
            _DNS_CACHE[domain] = (None, now)
        return None

# ========== CN 过滤工具 ==========
# 已从 utils.py 导入 is_pure_ip / is_cn_proxy_domain，此处不再重复定义
_CN_IP_SET = set()  # /8 前缀 → 快速排除非CN
_CN_IP_NETS = []    # 精确CIDR列表


def _init_cn_lookup():
    """初始化CN IP查找表"""
    # v28.15: 修改模块级变量
    for net in CN_IP_RANGES:
        _CN_IP_NETS.append(net)
        # 记录/8前缀用于快速排除
        _CN_IP_SET.add(net.network_address.packed[:1])


_init_cn_lookup()


def is_cn_proxy_ip(ip_str):
    """精确CN IP判断（4219条CIDR，先/8快排再精确匹配）"""
    if not ip_str:
        return None
    try:
        ip = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        logging.debug("Exception occurred", exc_info=True)
        return None
    # 快速排除：如果/8前缀不在CN集合中，肯定不是CN
    if isinstance(ip, ipaddress.IPv4Address):
        first_octet = ip.packed[:1]
        if first_octet not in _CN_IP_SET:
            return False
    # 精确匹配
    for cidr in _CN_IP_NETS:
        if ip in cidr:
            return True
    return False


def check_node_reachability(server, timeout=3.0):
    """v28.19: 放宽检测，解析到CN IP不直接排除（可能是CDN/中转节点）"""
    if not server:
        return False, "空server"
    if is_pure_ip(server):
        return True, "纯IP"
    if is_cn_proxy_domain(server):
        return False, "CN域名"
    # v28.19: 移除CN IP硬排除，改为仅记录日志
    # 很多代理使用CDN/中转，解析到CN IP不代表不可用
    resolved_ip = resolve_domain(server, timeout=timeout)
    if resolved_ip and is_cn_proxy_ip(resolved_ip):
        logging.debug("Node %s resolves to CN IP %s, keeping for test", server, resolved_ip)
    return True, "通过"


def is_reality_friendly(p):
    t = p.get("type", "")
    if t == "vless" and p.get("reality-opts"):
        return True
    name = p.get("name", "").lower()
    return any(k in name for k in ["reality", "real-", "vlss", "lima", "fly", "ssrsub"])


def record_history(server_ip, port, latency):
    key = (server_ip, port)
    with _HISTORY_SCORES_LOCK:  # v28.22: 线程安全
        if key not in _HISTORY_SCORES:
            _HISTORY_SCORES[key] = []
        _HISTORY_SCORES[key].append(latency)
        if len(_HISTORY_SCORES[key]) > 10:
            _HISTORY_SCORES[key] = _HISTORY_SCORES[key][-10:]


def history_stability_score(server_ip, port):
    key = (server_ip, port)
    with _HISTORY_SCORES_LOCK:  # v28.22: 线程安全读
        if key not in _HISTORY_SCORES or not _HISTORY_SCORES[key]:
            return 0
        scores = list(_HISTORY_SCORES[key])  # 快照，避免持锁计算
    n = len(scores)
    success_rate = sum(1 for s in scores if s < 9999) / n
    avg = sum(scores) / n
    variance = sum((s - avg) ** 2 for s in scores) / n
    std = variance ** 0.5
    return max(0, int(success_rate * 500 - min(std * 2, 200)))

# ========== 网络基准检测 ==========


def check_network_baseline():
    """检测网络基准延迟"""
    for target, port in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
        lat = _tcp_ping(target, port, timeout=2.0)
        if lat < 9999:
            _NETWORK_BASELINE["latency"] = min(_NETWORK_BASELINE["latency"], lat)
            _NETWORK_BASELINE["verified"] = True
    return _NETWORK_BASELINE["latency"]

# ========== TLS 握手检测 ==========


def tls_handshake_ok(host, port, timeout=5.0):
    if not host:
        return True, "ok"
    sock = None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            with ctx.wrap_socket(sock, server_hostname=host):
                pass
            return True, "ok"
        except ssl.SSLError as e:
            err = str(e)
            if 'HANDSHAKE_FAILURE' in err or 'SSLV3' in err:
                return False, "handshake_fail"
            return True, "ok"
    except (socket.timeout, OSError, ConnectionRefusedError):
        logging.debug("Exception occurred", exc_info=True)
        return True, "ok"
    finally:
        if sock:
            try:
                sock.close()
            except (OSError, socket.error):
                logging.debug("Exception occurred", exc_info=True)
                pass

# ========== HTTP HEAD 检测 ==========


def http_head_check(host, port, timeout=3.0):
    if not host:
        return False
    try:
        import http.client
        if port in (443, 8443, 8080):
            try:
                conn = http.client.HTTPSConnection(
                    host, port, timeout=timeout,
                    context=ssl._create_unverified_context()  # nosec B323
                )
                conn.request("HEAD", "/", headers={"User-Agent": "curl/7.83.1"})
                resp = conn.getresponse()
                conn.close()
                return resp.status < 500
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("HTTPS probe failed for %s:%s", host, port)
        if port in (80, 8080, 8888):
            try:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)
                conn.request("HEAD", "/", headers={"User-Agent": "curl/7.83.1"})
                resp = conn.getresponse()
                conn.close()
                return resp.status < 500
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("HTTP probe failed for %s:%s", host, port)
        return False
    except (socket.timeout, OSError):
        logging.debug("Exception occurred", exc_info=True)
        return False

# ========== 丢包率检测 ==========


def packet_loss_check(host, port, timeout=2.0, attempts=3):
    if not host:
        return 0, attempts, False
    success = 0
    for _ in range(attempts):
        lat = _tcp_ping(host, port, timeout=timeout)
        if lat < 9999:
            success += 1
        time.sleep(0.15)
    return success, attempts, success >= 2

# ========== 二次 TCP 验证 ==========

# BUGFIX v28.20: IPv6 兼容的 socket 创建
def _create_socket(host, timeout=None):
    """创建兼容 IPv4/IPv6 的 TCP socket"""
    if ":" in host:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout is not None:
        s.settimeout(timeout)
    return s
# ========== v28.6: 协议握手验证（TCP 层粗筛核心）==========


def _proto_handshake_ok(host, port, ptype, proxy=None, timeout=3.0):
    """验证端口不仅在监听，而且确实在响应代理协议。
    对于 vmess/vless: 检查 TLS ClientHello 后服务器是否返回合法 ServerHello
    对于 trojan: 检查 TLS 握手后服务器是否接受连接
    对于 ss/ssr: 尝试发送少量数据看是否被断开（无明确协议头）
    对于 http/socks5: 发送代理协议握手
    """
    try:
        if ptype in ("vmess", "vless", "trojan"):
            # BUGFIX v28.20: 只有标记 TLS 的节点才做 TLS 握手检测
            # 非 TLS 节点（纯 TCP 传输）做 TLS 握手必然失败，导致误杀
            # proxy 参数由调用方传入，携带完整节点信息
            if proxy and proxy.get("tls"):
                tls_ok, _ = tls_handshake_ok(host, port, timeout=timeout)
                return tls_ok
            # 非 TLS 节点：仅做 TCP 连通性检测（已在 tcp_ping 中完成），默认放过
            return True
        elif ptype in ("ss", "ssr"):
            # Shadowsocks 收到未知数据会静默丢弃或断开
            # 策略：发送垃圾数据后，如果服务器立即回显数据或立即 RST → 不是 SS
            # 如果超时无响应 → 可能是 SS（默认放过，不误杀）
            s = None
            try:
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"\x00")
                try:
                    data = s.recv(16)
                    # BUGFIX: recv 返回 b'' 表示对端已关闭连接（FIN），
                    # 不是 SS 特征；返回非空数据 = 服务器回显了 = 肯定不是 SS
                    # b''（连接关闭）→ 保守放过，不误杀
                    if data and data != b'':
                        return False  # 服务器回显了数据，不是 SS
                    return True  # 连接关闭或空，可能是 SS，不误杀
                except socket.timeout:
                    return True  # 超时 = 服务器没断开 = 可能是 SS
                except (ConnectionResetError, ConnectionAbortedError):
                    # BUGFIX v28.20: SS 服务器收到非法数据后 RST 是正常行为（解密失败重置）
                    # 之前误判为"不是SS"导致大量 SS 节点被误杀
                    return True
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("SS handshake probe failed", exc_info=True)
                return True  # 连接失败默认放过，不误杀
            finally:
                if s:
                    try:
                        s.close()
                    except (OSError, socket.error):
                        logging.debug("Exception occurred", exc_info=True)
                        pass
        elif ptype == "hysteria" or ptype == "hysteria2":
            # Hysteria 是 QUIC/UDP 协议，TCP 探测无意义，默认放过
            return True
        elif ptype == "http":
            # HTTP 代理：发送 CONNECT 请求
            s = None
            try:
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"CONNECT www.gstatic.com:443 HTTP/1.1\r\nHost: www.gstatic.com:443\r\n\r\n")
                data = s.recv(256)
                # HTTP 代理应返回 200/407 等 HTTP 响应
                return b"HTTP/" in data
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("Exception occurred", exc_info=True)
                return False
            finally:
                if s:
                    try:
                        s.close()
                    except (OSError, socket.error):
                        logging.debug("Exception occurred", exc_info=True)
                        pass
        elif ptype == "socks5":
            # SOCKS5: 发送握手
            s = None
            try:
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"\x05\x01\x00")  # SOCKS5, 1 auth method, no auth
                data = s.recv(16)
                # SOCKS5 服务器应返回 0x05 + method
                return len(data) >= 2 and data[0] == 0x05
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("Exception occurred", exc_info=True)
                return False
            finally:
                if s:
                    try:
                        s.close()
                    except (OSError, socket.error):
                        logging.debug("Exception occurred", exc_info=True)
                        pass
        else:
            # 未知协议默认放过
            return True
    except (socket.timeout, OSError, ConnectionRefusedError):
        logging.debug("Exception occurred", exc_info=True)
        return True  # 探测失败不过滤，避免误杀


def tcp_verify(host, port, timeout=1.5):
    if not host:
        return False
    try:
        s = _create_socket(host, timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, OSError, ConnectionRefusedError):
        logging.debug("Exception occurred", exc_info=True)
        return False

# ========== 内部 TCP Ping（兼容旧名 tcp_ping）==========


def _tcp_ping(host, port, timeout=2.5):
    if not host:
        return 9999
    try:
        start = time.time()
        s = _create_socket(host, timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        s.close()
        return round((time.time() - start) * 1000, 1)
    except (socket.timeout, OSError, ConnectionRefusedError):
        logging.debug("Exception occurred", exc_info=True)
        return 9999


# BUGFIX v28.39: 添加 tcp_ping 别名（兼容主流程调用）
tcp_ping = _tcp_ping


def ensure_clash_dir():
    """安全创建目录"""
    if WORK_DIR.exists() and not WORK_DIR.is_dir():
        try:
            WORK_DIR.unlink()
        except (OSError, PermissionError):
            logging.debug("Failed to unlink %s", WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)


class SmartRateLimiter:
    """v28.17: 域名级智能限流 + IP地理缓存持久化"""
    def __init__(self):
        self.locks = {}
        self.last_call = {}
        # v28.17: 按域名分类限流策略
        self.domain_intervals = {
            'default': 1.0 / REQUESTS_PER_SECOND,
            'ip-api.com': 0.5,      # IP查询更严格
            'gstatic.com': 0.2,     # 测速URL宽松
            'cloudflare.com': 0.3,
            'apple.com': 0.3,
            'raw.githubusercontent.com': 0.1,  # GitHub Raw 宽松
            't.me': 1.0,            # Telegram 严格
        }
        # v28.17: IP地理缓存持久化（24h TTL）
        self.ip_geo_cache = TTLCache(maxsize=10000, ttl=86400)
        self._cache_lock = threading.Lock()
        self._load_geo_cache()

    def _get_interval(self, domain):
        """获取域名对应的限流间隔"""
        for key, interval in self.domain_intervals.items():
            if key in domain:
                return interval
        return self.domain_intervals['default']

    def _cleanup_stale(self):
        """v28.22: 清理超过60秒未使用的域名锁和计时器，防止内存无限增长"""
        # BUGFIX: 加锁保护 + 避免迭代时修改字典
        with self._cache_lock:  # 复用缓存锁（都是元数据）
            now = time.time()
            # 复制 key 列表，避免 dictionary changed size during iteration
            stale = [d for d, t in list(self.last_call.items()) if now - t > 60]
            for d in stale:
                self.locks.pop(d, None)
                self.last_call.pop(d, None)

    # BUGFIX: 增加初始化锁，彻底解决 TOCTOU 竞态
    _init_lock = threading.Lock()

    def wait(self, url=""):
        domain = urlparse(url).netloc or "default"
        # 使用初始化锁确保原子性
        with self._init_lock:
            if domain not in self.locks:
                self.locks[domain] = threading.Lock()
                self.last_call[domain] = 0.0
        # v28.22: 每次wait时以1%概率触发清理，避免频繁但防止无限增长
        if len(self.locks) > 50 and random.random() < 0.01:
            self._cleanup_stale()
        with self.locks[domain]:
            now = time.time()
            interval = self._get_interval(domain)
            last = self.last_call.get(domain, 0.0)
            elapsed = now - last
            if elapsed < interval:
                time.sleep(interval - elapsed)
            self.last_call[domain] = now

    def _get_cache_file(self):
        """获取缓存文件路径"""
        return Path(__file__).parent / ".ip_geo_cache.json"

    def _load_geo_cache(self):
        """从文件加载IP地理缓存"""
        try:
            cache_file = self._get_cache_file()
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for ip, item in data.items():
                        # 检查TTL
                        if time.time() - item.get('ts', 0) < 86400:
                            self.ip_geo_cache[ip] = item
                logging.debug(f"[SmartRateLimiter] 已加载 {len(self.ip_geo_cache)} 条IP地理缓存")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.debug("加载IP地理缓存失败: %s", e)

    def save_geo_cache(self):
        """保存IP地理缓存到文件"""
        try:
            with self._cache_lock:
                cache_file = self._get_cache_file()
                data = {}
                for ip, item in self.ip_geo_cache.items():
                    data[ip] = dict(item, ts=time.time())
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                logging.debug(f"[SmartRateLimiter] 已保存 {len(data)} 条IP地理缓存")
        except (OSError, TypeError) as e:
            logging.debug("保存IP地理缓存失败: %s", e)

    def get_geo(self, ip):
        """获取IP地理信息（带缓存）"""
        with self._cache_lock:
            return self.ip_geo_cache.get(ip)

    def set_geo(self, ip, geo_data):
        """设置IP地理信息（带缓存）"""
        with self._cache_lock:
            self.ip_geo_cache[ip] = geo_data


limiter = SmartRateLimiter()

# v28.45: GeoIP2 本地数据库读取器（延迟初始化）
_geoip2_reader = None

def _get_geoip2_reader():
    """获取 GeoIP2 读取器（延迟初始化 + 缓存）"""
    global _geoip2_reader
    if _geoip2_reader is not None:
        return _geoip2_reader
    if not _GEOIP2_AVAILABLE:
        return None
    # 查找可能的 mmdb 文件路径
    mmdb_paths = [
        Path(__file__).parent / "GeoLite2-City.mmdb",
        Path("/usr/share/GeoIP/GeoLite2-City.mmdb"),
        Path(os.environ.get("GEOIP_DB_PATH", "")) if os.environ.get("GEOIP_DB_PATH") else None,
    ]
    for p in mmdb_paths:
        if p and p.exists():
            try:
                _geoip2_reader = geoip2.database.Reader(str(p))
                logging.debug(f"[GeoIP2] 已加载本地数据库: {p}")
                return _geoip2_reader
            except (OSError, ValueError) as e:
                logging.debug("GeoIP2 加载失败: %s", e)
    return None


def _geoip2_lookup(ip):
    """使用 GeoIP2 本地数据库查询 IP 地理位置"""
    reader = _get_geoip2_reader()
    if reader is None:
        return None
    try:
        rec = reader.city(ip)
        cc = rec.country.iso_code
        if cc:
            return {"status": "success", "countryCode": cc.upper(), "query": ip}
    except (geoip2.errors.AddressNotFoundError, ValueError, TypeError):
        logging.debug("GeoIP2 未找到 IP %s 或数据格式异常", ip)
    except (OSError, ImportError) as e:
        logging.debug("GeoIP2 查询异常: %s", e)
    return None


# BUGFIX v28.39: 添加 _ip_geo_batch（主流程依赖）
def _ip_geo_batch(ips):
    """批量查询 IP 地理位置，优先使用 GeoIP2 本地数据库，回退到 ip-api.com"""
    if not ips:
        return
    # 过滤已缓存和无效的
    to_query = [ip for ip in ips if limiter.get_geo(ip) is None and is_pure_ip(ip)]
    if not to_query:
        return

    # v28.45: 优先使用 GeoIP2 本地数据库
    geoip2_reader = _get_geoip2_reader()
    if geoip2_reader is not None:
        local_hits = 0
        for ip in to_query:
            geo = _geoip2_lookup(ip)
            if geo:
                limiter.set_geo(ip, geo)
                local_hits += 1
        # 全部命中则直接返回，无需网络查询
        if local_hits == len(to_query):
            return
        # 过滤掉已本地查询的
        to_query = [ip for ip in to_query if limiter.get_geo(ip) is None]

    # 回退到 ip-api.com 批量接口（每批最多 100 个）
    # v28.46-fix3: 使用 HTTPS + 重试，避免 Connection reset by peer
    BATCH = 100
    for i in range(0, len(to_query), BATCH):
        batch = to_query[i:i + BATCH]
        last_err = None
        for attempt in range(3):
            try:
                c = get_http_client()
                r = c.post("https://ip-api.com/batch?fields=status,countryCode,query",
                           json=batch, timeout=15)
                if r.status_code == 200:
                    for item in r.json():
                        if item.get("status") == "success":
                            limiter.set_geo(item["query"], item)
                    logging.debug(f"   IP 地理位置查询：{len(batch)} 个（已缓存 {len(limiter.ip_geo_cache)}）")
                    break
                elif r.status_code in (429, 503):
                    time.sleep(2 ** attempt)
                    continue
            except (requests.RequestException, httpx.HTTPError, ValueError) as e:
                last_err = e
                time.sleep(1.5 ** attempt)
        else:
            logging.debug("IP 地理位置查询失败（已重试3次）: %s", last_err)
        # 每批查询后保存缓存
        limiter.save_geo_cache()


def create_session():
    session = requests.Session()
    retry = Retry(total=MAX_RETRIES, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(random.choice(HEADERS_POOL))
    return session


session = create_session()




# [STAR] 节点解析器（保持不变）
# v28.34: 协议解析器已迁移到 parsers/ 包
# 请从 parsers 包导入:
# from parsers import (parse_vmess, parse_vless, parse_trojan, parse_trojan_go,
#     parse_ss, parse_ssr, parse_hysteria, parse_hysteria2,
#     parse_tuic, parse_snell, parse_http_proxy, parse_socks,
#     parse_anytls, parse_node)




def filter_quality(p):
    """【v28.39】节点质量过滤，含 CN IP/域名黑名单 + 非代理端口过滤 + 大陆友好性评分"""
    if not p or not isinstance(p, dict):
        return False
    name = p.get("name", "").lower()

    # 仅排除明显无效的
    exclude_keywords = ["过期", "到期", "失效", "expire", "expired", "广告", "推广", "官网", "购买"]
    for kw in exclude_keywords:
        if kw in name:
            return False

    # 排除内地直连
    if is_china_mainland(p):
        return False

    # 非代理端口过滤（v24）
    try:
        port = int(p.get("port", 0))
    except (ValueError, TypeError):
        port = 0
    if port <= 0 or port > 65535:
        return False
    if port in NON_PROXY_PORTS:
        return False

    # v28.39: 大陆友好性评分过滤 - 过滤掉极低友好度的节点
    try:
        mf_score = mainland_friendly_score(p)
        if mf_score < 10:  # 友好度低于10分的节点大概率不可用
            logging.debug("Filter: skip low mainland-friendly node %s (score=%s)", p.get('name', '?'), mf_score)
            return False
    except (ValueError, KeyError, TypeError):
        logging.debug("mainland_friendly_score error for %s", p.get('name', '?'), exc_info=True)
        # 评分失败时不过滤，避免误杀

    return True

# [STAR] Clash 管理（保持不变）
class ClashManager:
    def __init__(self):
        self.process = None
        ensure_clash_dir()

    def download_clash(self):
        if CLASH_PATH.exists():
            return True
        # ISSUE-3-03: 跨平台 Clash 二进制下载
        import platform
        sys = platform.system().lower()
        arch = platform.machine().lower()
        if sys == "windows":
            if "arm" in arch:
                clang_name = f"mihomo-windows-arm64-compatible-{CLASH_VERSION}.exe.gz"
            else:
                clang_name = f"mihomo-windows-amd64-compatible-{CLASH_VERSION}.exe.gz"
        elif sys == "darwin":
            if "arm" in arch:
                clang_name = f"mihomo-darwin-arm64-compatible-{CLASH_VERSION}.gz"
            else:
                clang_name = f"mihomo-darwin-amd64-compatible-{CLASH_VERSION}.gz"
        else:  # Linux
            if "arm" in arch:
                clang_name = f"mihomo-linux-arm64-compatible-{CLASH_VERSION}.gz"
            else:
                clang_name = f"mihomo-linux-amd64-compatible-{CLASH_VERSION}.gz"
        url = (
            f"https://github.com/MetaCubeX/mihomo/releases/download/{CLASH_VERSION}/"
            f"{clang_name}"
        )
        try:
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code != 200:
                return False
            temp = WORK_DIR / "mihomo.gz"
            with open(temp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            # v28.50: 使用独立变量确保文件句柄可关闭
            f_in = None
            f_out = None
            try:
                f_in = gzip.open(temp, "rb")
                f_out = open(CLASH_PATH, "wb")
                shutil.copyfileobj(f_in, f_out)
            finally:
                if f_in:
                    try:
                        f_in.close()
                    except OSError as e:
                        logging.debug(f"关闭输入文件失败: {e}", exc_info=True)
                if f_out:
                    try:
                        f_out.close()
                    except OSError as e:
                        logging.debug(f"关闭输出文件失败: {e}", exc_info=True)
            if os.name != 'nt':  # Windows 不支持 os.chmod 的 Unix 权限
                os.chmod(CLASH_PATH, 0o755)
            temp.unlink(missing_ok=True)
            return CLASH_PATH.exists()
        except (requests.RequestException, OSError, gzip.BadGzipFile):
            logging.debug("Exception occurred", exc_info=True)
            return False

    def _clean_proxy_for_clash(self, p):
        """清洗代理字典，移除内部字段和 Clash 不支持的字段"""
        # 白名单：Clash Meta 支持的字段
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
            # hysteria2
            'password','obfs','obfs-password','sni',
            # anytls
            'password','client-fingerprint',
        }
        cleaned = {}
        for k, v in p.items():
            if k.startswith('_'):  # 内部字段（_src_weight 等）
                continue
            if k not in CLASH_FIELDS:
                logging.debug("Clash: 移除不支持字段 %s from %s", k, p.get('name','?'))
                continue
            # None 值保留（yaml.dump 会写成 null，Clash 可处理）
            cleaned[k] = v
        # BUGFIX v28.40: 校验并清理 REALITY short-id，防止 Clash 崩溃
        if cleaned.get('reality-opts'):
            ro = cleaned['reality-opts']
            if isinstance(ro, dict):
                sid = ro.get('short-id', '')
                # Clash Meta 要求 short-id 为 8/16/32 字符十六进制，或空字符串
                if sid and not re.fullmatch(r'[0-9a-fA-F]{8}|[0-9a-fA-F]{16}|[0-9a-fA-F]{32}', str(sid)):
                    logging.warning("Clash: 移除无效 REALITY short-id '%s' from %s", sid, cleaned.get('name', '?'))
                    del ro['short-id']
                    if not ro:
                        del cleaned['reality-opts']
        return cleaned

    def create_config(self, proxies):
        ensure_clash_dir()
        # BUGFIX v28.26: 过滤 Clash 不支持的协议（anytls 等）
        SUPPORTED_TYPES = {
            'ss', 'ssr', 'vmess', 'vless', 'trojan', 'socks5', 'http',
            'hysteria', 'hysteria2', 'tuic', 'snell', 'mieru', 'juicity'
        }
        filtered = []
        for p in proxies:
            if p.get('type', '').lower() not in SUPPORTED_TYPES:
                logging.debug("Clash: 跳过不支持的协议类型 %s from %s", p.get('type'), p.get('name','?'))
                continue
            filtered.append(p)
        if not filtered:
            logging.debug("   [WARN] 所有节点协议均不支持，无法生成 Clash 配置")
            return False
        # BUGFIX: 移除内部双重截断，调用方已用 batch_size 限制了 proxies 数量
        # 原代码 proxies[:MAX_PROXY_TEST_NODES] 出现两次，与外层 batch_size 职责重叠
        names = []
        seen = set()
        cleaned_proxies = [self._clean_proxy_for_clash(p) for p in filtered]

        # BUG[4-02] 修复：必填字段验证
        required_fields = {"name", "type", "server", "port"}
        valid_proxies = []
        for p in cleaned_proxies:
            missing = required_fields - set(p.keys())
            if missing:
                logging.warning("Clash: 跳过缺少必填字段 %s 的节点 %s", missing, p.get("name", "?"))
                continue
            # port 必须是有效数字
            try:
                port = int(p["port"])
                if not (1 <= port <= 65535):
                    raise ValueError
            except (ValueError, TypeError):
                logging.warning("Clash: 跳过端口无效 %s 的节点 %s", p.get("port"), p.get("name", "?"))
                continue
            valid_proxies.append(p)

        if not valid_proxies:
            logging.warning("所有节点均缺少必填字段或端口无效，无法生成 Clash 配置")
            return False

        for i, p in enumerate(valid_proxies):
            name = p["name"]
            if name in seen:
                name = f"{name}-{i}"
            seen.add(name)
            names.append(name)
            p["name"] = name
        # 大陆路由规则：环境变量 CN_DIRECT=1 启用
        cn_direct = os.getenv("CN_DIRECT", "0") == "1"
        rules = []
        if cn_direct:
            # 动态规则集（大陆域名直连 + GFW 列表代理）
            rules += [
                "DOMAIN-SUFFIX,icloud.com,DIRECT",  # 保留常用直连域名
                "RULE-SET,cn_domains,DIRECT",       # 大陆域名动态规则
                "RULE-SET,gfw_list,PROXY",          # GFW 列表走代理
                "GEOIP,CN,DIRECT,no-resolve",       # 大陆 IP 直连
                # 局域网/本地地址直连
                "IP-CIDR,192.168.0.0/16,DIRECT",
                "IP-CIDR,10.0.0.0/8,DIRECT",
                "IP-CIDR,172.16.0.0/12,DIRECT",
                "IP-CIDR,127.0.0.0/8,DIRECT",
            ]
        # 剩余流量走 TEST 代理组
        rules.append("MATCH,TEST")

        config = {
            "port": CLASH_PORT, "socks-port": CLASH_PORT + 1, "allow-lan": False, "mode": "rule",
            "log-level": "error", "external-controller": f"127.0.0.1:{CLASH_API_PORT}",
            "secret": "",  # nosec B105: Clash API local only
            "ipv6": False, "unified-delay": True, "tcp-concurrent": True,
            # 动态规则提供者（大陆域名直连 + GFW 列表代理）
            "rule-providers": {
                "cn_domains": {
                    "type": "http",
                    "url": "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/cn.txt",
                    "behavior": "domain",
                    "interval": 86400,  # 每天更新一次
                },
                "gfw_list": {
                    "type": "http",
                    "url": "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/gfw.txt",
                    "behavior": "domain",
                    "interval": 86400,
                }
            },
            # 防 DNS 泄露配置
            "dns": {
                "enable": True,
                "listen": "0.0.0.0:53",
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "nameserver": [
                    "https://dns.alidns.com/dns-query",  # 阿里云 DoH（大陆优先）
                    "https://doh.pub/dns-query",          # 腾讯云 DoH
                ],
                "fallback": [
                    "https://cloudflare-dns.com/dns-query",
                    "https://dns.google/dns-query",
                ],
                "fallback-filter": {
                    "geoip": True,
                    "ipcidr": ["198.18.0.1/16"],  # 排除 fake-ip 范围
                }
            },
            "proxies": valid_proxies,
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": names}],
            "rules": rules
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, Dumper=yaml.SafeDumper)
        return True

    def start(self):
        ensure_clash_dir()
        if not CLASH_PATH.exists() and not self.download_clash():
            return False
        LOG_FILE.touch()
        try:
            cmd = [str(CLASH_PATH.absolute()), "-d", str(WORK_DIR.absolute()), "-f", str(CONFIG_FILE.absolute())]
            # BUGFIX v28.15: preexec_fn=os.setsid 仅 Linux 可用，Windows 不支持
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "cwd": str(
                    WORK_DIR.absolute())}
            if os.name != "nt":
                # pylint: disable=no-member
                popen_kwargs["preexec_fn"] = os.setsid  # type: ignore[attr-defined]
            self.process = subprocess.Popen(cmd, **popen_kwargs)
            # v28.39: 初始化 out 避免未定义
            out = ""
            # v28.50: 确保进程管道正确关闭
            try:
                for i in range(30):
                    time.sleep(1)
                    if self.process.poll() is not None:
                        try:
                            out, _ = self.process.communicate(timeout=5)
                            # 打印首尾各 500 字符，YAML 错误通常在末尾
                            out_short = out[:500] + "\n...\n" + out[-500:] if len(out) > 1000 else out
                            logging.debug(f"   [FAIL] Clash 崩溃:\n{out_short}")
                        except (subprocess.TimeoutExpired, OSError):
                            logging.debug("   [FAIL] Clash 崩溃")
                        return False
                    try:
                        if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                            logging.debug("   [OK] Clash API 就绪")
                            return True
                    except requests.RequestException:
                        logging.debug("Clash API version check failed")
                logging.debug("   [TIMEOUT] Clash 启动超时")
                return False
            finally:
                # 确保 stdout/stderr 管道关闭
                if self.process and self.process.stdout:
                    try:
                        self.process.stdout.close()
                    except OSError as e:
                        logging.debug(f"关闭 stdout 管道失败: {e}", exc_info=True)
                try:
                    if requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/version", timeout=2).status_code == 200:
                        logging.debug("   [OK] Clash API 就绪")
                        return True
                except requests.RequestException:
                    logging.debug("Clash API version check failed")
            logging.debug("   [TIMEOUT] Clash 启动超时")
            return False
        except (OSError, subprocess.SubprocessError) as e:
            logging.debug(f"   [ERROR] Clash 启动异常：{e}")
            return False
        # v28.50: 启动成功时关闭管道避免泄漏
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except OSError as e:
                logging.debug(f"关闭 stdout 管道失败: {e}", exc_info=True)

    def stop(self):
        if self.process:
            try:
                # BUGFIX v28.15: os.killpg/signal.SIGTERM 仅 Linux 可用
                if os.name != "nt":
                    # pylint: disable=no-member
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)  # type: ignore[attr-defined]
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                logging.debug("Clash stop failed")
            self.process = None

    def test_proxy(self, name, retry=True):
        """v28.7: 多URL测速 + 失败重试"""
        result = {"success": False, "latency": 9999.0, "speed": 0.0, "error": ""}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST", json={"name": name}, timeout=2)
            time.sleep(0.05)
            px = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            # 多 URL 测速：任一成功即通过
            for url in TEST_URLS:
                try:
                    start = time.time()
                    resp = requests.get(url, proxies=px, timeout=5, allow_redirects=False)
                    lat = (time.time() - start) * 1000
                    if resp.status_code in [200, 204, 301, 302]:
                        result = {"success": True, "latency": round(lat, 1), "speed": 0.0, "error": ""}
                        break
                except requests.RequestException as e:
                    logging.debug("Test URL failed for proxy %s: %s", name, str(e)[:50])
                    continue
            # 大陆端点测试（v28.56）强制项 + 超时放宽15s
            if ENABLE_MAINLAND_TEST and result["success"]:
                ml_ok = False
                for ml_url in MAINLAND_TEST_URLS:
                    try:
                        r = requests.get(ml_url, proxies=px, timeout=15,
                                         allow_redirects=True, headers={"User-Agent": "curl/7.83.1"})
                        if r.status_code in [200, 204, 301, 302]:
                            ml_ok = True
                            break
                    except requests.RequestException as e:
                        logging.debug("Mainland test URL failed: %s", str(e)[:50])
                        continue
                if not ml_ok:
                    result["success"] = False
                    result["error"] = "Mainland unreachable"
                    logging.debug("Mainland test failed for %s", name)
            if not result["success"]:
                result["error"] = "All test URLs failed"
        except requests.RequestException as e:
            result["error"] = str(e)[:60]
        # 失败重试一次（减少网络抖动误杀）
        if retry and not result["success"]:
            time.sleep(0.5)
            return self.test_proxy(name, retry=False)
        return result


# [STAR] 节点命名（优化版：无后缀）
class NodeNamer:
    FANCY = {
        'A': '𝔄',
        'B': '𝔅',
        'C': '𝔆',
        'D': '𝔇',
        'E': '𝔈',
        'F': '𝔉',
        'G': '𝔊',
        'H': '𝔋',
        'I': 'ℑ',
        'J': '𝔍',
        'K': '𝔎',
        'L': '𝔏',
        'M': '𝔐',
        'N': '𝔑',
        'O': '𝔒',
        'P': '𝔓',
        'Q': '𝔔',
        'R': '𝔕',
        'S': '𝔖',
        'T': '𝔗',
        'U': '𝔘',
        'V': '𝔙',
        'W': '𝔚',
        'X': '𝔛',
        'Y': '𝔜',
        'Z': '𝔝'}

    def __init__(self):
        self.counters = {}

    def to_fancy(self, t):

        return ''.join(self.FANCY.get(c.upper(), c) for c in t)

    def generate(self, flag, lat=None, score=None, speed=None, tcp=False, server=None, sni=None):
        """【v28.55】命名包含区域emoji + 编号 + 延迟 + 评分 + 哥特体后缀"""
        code, region = get_region(flag, server=server, sni=sni)
        self.counters[region] = self.counters.get(region, 0) + 1
        num = self.counters[region]
        # 延迟信息（仅保留整数）
        lat_str = f"{int(lat)}ms" if lat is not None and lat < 9999 else "N/A"
        # 大陆友好评分（保留1位小数）
        score_str = f"s{score:.1f}" if score is not None else ""
        # 哥特体后缀
        gothic = "𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶"
        return f"{code}{num}-{lat_str}{score_str}-{gothic}"


# [STAR] 协议链接转换（扩展版）
def format_proxy_to_link(p):
    """将代理对象转换为协议链接"""
    try:
        ptype = p.get("type", "")
        name_enc = urllib.parse.quote(p.get("name", "node"), safe="")

        if ptype == "vmess":
            # v28.19: 修复host来源，优先从ws-opts获取
            ws_opts = p.get("ws-opts", {})
            host = ws_opts.get("headers", {}).get("Host", "")
            if not host:
                host = p.get("sni", "")
            data = {"v": "2", "ps": p["name"], "add": p["server"], "port": p["port"],
                    "id": p["uuid"], "aid": p.get("alterId", 0), "net": p.get("network", "tcp"),
                    "type": "none", "host": host, "path": ws_opts.get("path", ""),
                    "tls": "tls" if p.get("tls") else ""}
            # BUGFIX v28.20: 补充 alpn 字段
            if p.get("alpn"):
                data["alpn"] = ",".join(p["alpn"]) if isinstance(p["alpn"], list) else p["alpn"]
            # BUGFIX v28.20: h2 传输层信息
            if p.get("network") == "h2" and p.get("h2-opts"):
                h2o = p["h2-opts"]
                data["path"] = h2o.get("path", data["path"])
                h2_host = h2o.get("host", [])
                if isinstance(h2_host, list) and h2_host:
                    data["host"] = h2_host[0]
                elif isinstance(h2_host, str) and h2_host:
                    data["host"] = h2_host
            # BUGFIX: grpc 传输层信息
            if p.get("grpc-opts"):
                data["path"] = p["grpc-opts"].get("grpc-service-name", "")
                data["host"] = ""
                data["type"] = "gun"
            return "vmess://" + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()

        elif ptype == "trojan":
            pwd_enc = urllib.parse.quote(p.get('password', ''), safe='')
            sni = p.get('sni', p.get('server', ''))
            # BUGFIX v28.20: 添加传输层类型和参数
            ttype = p.get('network', 'tcp')
            params = f"sni={urllib.parse.quote(str(sni), safe='')}&type={ttype}&allowInsecure=1"
            # WS 传输参数
            if ttype == 'ws':
                ws_opts = p.get('ws-opts', {})
                if ws_opts.get('path'):
                    params += f"&path={urllib.parse.quote(ws_opts['path'], safe='')}"
                ws_host = ws_opts.get('headers', {}).get('Host', '')
                if ws_host:
                    params += f"&host={urllib.parse.quote(ws_host, safe='')}"
            # GRPC 传输参数
            if ttype == 'grpc' and p.get('grpc-opts'):
                svc = p['grpc-opts'].get('grpc-service-name', '')
                if svc:
                    params += f"&serviceName={urllib.parse.quote(svc, safe='')}"
            # alpn/fingerprint
            # v28.23: alpn 类型容错（YAML直接加载时可能是字符串）
            if p.get('alpn'):
                alpn_val = p['alpn']
                if isinstance(alpn_val, str):
                    alpn_list = [a.strip() for a in alpn_val.split(',') if a.strip()]
                elif isinstance(alpn_val, list):
                    alpn_list = alpn_val
                else:
                    alpn_list = []
                if alpn_list:
                    params += f"&alpn={','.join(alpn_list)}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"trojan://{pwd_enc}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "vless":
            uuid = p.get('uuid', '')
            # v28.19: 修复reality参数丢失
            has_reality = bool(p.get('reality-opts'))
            security = "reality" if has_reality else ("tls" if p.get('tls') else "none")
            flow = p.get('flow', '')
            params = f"encryption=none&type={p.get('network', 'tcp')}&security={security}"
            # BUGFIX v28.20: vless WS 传输层参数（path/host）
            if p.get('network') == 'ws':
                ws_opts = p.get('ws-opts', {})
                if ws_opts.get('path'):
                    params += f"&path={urllib.parse.quote(ws_opts['path'], safe='')}"
                ws_host = ws_opts.get('headers', {}).get('Host', '')
                if ws_host:
                    params += f"&host={urllib.parse.quote(ws_host, safe='')}"
            # BUGFIX: grpc 传输层信息
            if p.get('network') == 'grpc' and p.get('grpc-opts'):
                svc = p['grpc-opts'].get('grpc-service-name', '')
                if svc:
                    params += f"&serviceName={svc}"
            if flow:
                params += f"&flow={flow}"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            # v28.19: 添加reality必要参数
            if has_reality:
                ro = p['reality-opts']
                params += f"&pbk={ro.get('public-key', '')}&sid={ro.get('short-id', '')}"
                fp = p.get('client-fingerprint', 'chrome')
                params += f"&fp={fp}"
            return f"vless://{uuid}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "ss":
            auth = f"{p['cipher']}:{p['password']}"
            auth_enc = base64.b64encode(auth.encode()).decode()
            return f"ss://{auth_enc}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "ssr":
            # BUGFIX v28.20: 输出合法 SSR 链接（而非注释）
            # SSR 格式: ssr://base64(server:port:protocol:method:obfs:base64pass/?params)
            try:
                server = p.get('server', '')
                port = p.get('port', 0)
                protocol = p.get('protocol', 'origin')
                method = p.get('method') or p.get('cipher', 'aes-256-cfb')
                obfs = p.get('obfs', 'plain')
                password = p.get('password', '')
                b64_pwd = base64.b64encode(password.encode()).decode().rstrip('=')
                main_part = f"{server}:{port}:{protocol}:{method}:{obfs}:{b64_pwd}"
                params_parts = []
                obfs_param = p.get('obfs-param', '')
                if obfs_param:
                    b64_op = base64.b64encode(obfs_param.encode()).decode().rstrip('=')
                    params_parts.append(f"obfsparam={b64_op}")
                proto_param = p.get('protocol-param', '')
                if proto_param:
                    b64_pp = base64.b64encode(proto_param.encode()).decode().rstrip('=')
                    params_parts.append(f"protoparam={b64_pp}")
                remarks = p.get('name', '')
                if remarks:
                    b64_name = base64.b64encode(remarks.encode()).decode().rstrip('=')
                    params_parts.append(f"remarks={b64_name}")
                params_str = '/?' + '&'.join(params_parts) if params_parts else ''
                full = main_part + params_str
                b64_full = base64.b64encode(full.encode()).decode()
                return f"ssr://{b64_full}"
            except (KeyError, ValueError, TypeError):
                logging.debug("Exception occurred", exc_info=True)
                return None  # v28.22: SSR 序列化失败时返回 None 而非注释行，避免客户端解析错误

        elif ptype == "hysteria2":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            params = "insecure=1"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            # BUGFIX v28.20: 补充 obfs/obfs-password/fp 参数
            if p.get('obfs'):
                params += f"&obfs={urllib.parse.quote(p['obfs'], safe='')}"
            if p.get('obfs-password'):
                params += f"&obfs-password={urllib.parse.quote(p['obfs-password'], safe='')}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"hysteria2://{pwd}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "hysteria":
            pwd = urllib.parse.quote(p.get('password', ''), safe='')
            return f"hysteria://{pwd}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "tuic":
            uuid_val = p.get('uuid', '')
            # BUGFIX v28.20: tuic password 和 uuid 可能不同
            password = p.get('password', uuid_val)
            params = "congestion_control=cubic"
            if p.get('sni'):
                params += f"&sni={urllib.parse.quote(str(p['sni']), safe='')}"
            if p.get('alpn'):
                # v28.23: alpn 类型容错
                _alpn_v = p['alpn']
                if isinstance(_alpn_v, str):
                    _alpn_v = [a.strip() for a in _alpn_v.split(',') if a.strip()]
                if isinstance(_alpn_v, list) and _alpn_v:
                    params += f"&alpn={','.join(_alpn_v)}"
            if p.get('client-fingerprint'):
                params += f"&fp={p['client-fingerprint']}"
            return f"tuic://{uuid_val}:{password}@{p['server']}:{p['port']}?{params}#{name_enc}"

        elif ptype == "snell":
            pwd = urllib.parse.quote(p.get('psk', ''), safe='')
            return f"snell://{pwd}@{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "socks5":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            return f"socks5://{auth}{p['server']}:{p['port']}#{name_enc}"

        elif ptype == "http":
            auth = ""
            if p.get('username') and p.get('password'):
                auth = f"{urllib.parse.quote(p['username'])}:{urllib.parse.quote(p['password'])}@"
            scheme = "https" if p.get('tls') else "http"
            return f"{scheme}://{auth}{p['server']}:{p['port']}#{name_enc}"

        return None  # v28.22: 未知协议返回None而非注释行，避免客户端解析错误
    except (KeyError, ValueError, TypeError):
        logging.debug("Exception occurred", exc_info=True)
        return None  # v28.22: 异常时返回None而非注释行


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
    def _signal_handler(sig, frame):
        logging.debug(f"[EXIT] 捕获信号 {sig}，保存运行数据...")
        _save_node_history()
        _save_source_history()
        limiter.save_geo_cache()
        sys.exit(0)
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
        nlist = asia_nodes_list[:asia_quota] + non_asia_nodes_list[:non_asia_quota]
        logging.info(f"   [STAT] TCP测试队列：{len(asia_nodes_list[:asia_quota])} 亚洲"
              f" + {len(non_asia_nodes_list[:non_asia_quota])} 非亚洲 = {len(nlist)} 总计")
        nres = []

        def test_tcp_node(proxy):
            try:
                server = proxy.get("server", "")
                port = proxy.get("port", 0)
                if not server or not port:
                    return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # BUGFIX v28.20: IPv6 地址安全提取 host
                if server.startswith("[") and "]" in server:
                    host = server.split("]")[0][1:]  # 提取 [xxx] 中的 xxx
                elif is_pure_ip(server) and ":" in server:
                    host = server  # 纯 IPv6 地址（如 fe80::1），整体就是 host
                elif ":" in server:
                    host = server.split(":")[0]  # IPv4:port 格式
                else:
                    host = server
                # v28.13: 预查询 IP 地理位置（用于后续排序优化）
                if is_pure_ip(host) and limiter.get_geo(host) is None:
                    _ip_geo_batch([host])
                lat = tcp_ping(host, port)
                if lat >= 9999:
                    return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # v28.47: 亚洲节点放宽丢包检测，提高亚洲节点通过率
                if is_asia(proxy):
                    ok, total, usable = packet_loss_check(host, port, timeout=4.0, attempts=2)
                else:
                    ok, total, usable = packet_loss_check(host, port, timeout=3.0, attempts=2)
                if not usable:
                    return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # BUGFIX v28.20: TLS 握手检测扩展到所有常用 TLS 端口
                # 原来只检测 port==443，遗漏 8443/2053/2083/2087/2096 等
                TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096, 8880}
                if proxy.get("tls") and port in TLS_PORTS:
                    tls_ok, _ = tls_handshake_ok(host, port, timeout=3.0)
                    if not tls_ok:
                        return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                # v28.47: 协议握手验证 - 亚洲节点放宽验证
                ptype = proxy.get("type", "").lower()
                if ptype in ("ss", "ssr", "socks5", "http", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic", "snell"):
                    if is_asia(proxy):
                        # 亚洲节点握手失败不直接淘汰，降低延迟要求
                        if not _proto_handshake_ok(host, port, ptype, proxy):
                            logging.debug(f"亚洲节点 {host}:{port} 握手失败但保留")
                    else:
                        if not _proto_handshake_ok(host, port, ptype, proxy):
                            return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
                return {"proxy": proxy, "latency": float(lat), "is_asia": is_asia(proxy),
                        "hist_score": history_stability_score(host, port)}
            except (OSError, ValueError, TypeError):
                logging.debug("Exception occurred", exc_info=True)
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}
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

        def _geo_score(item):
            """IP 地理位置评分：亚洲高分，非友好区域低分"""
            srv = item["proxy"].get("server", "")
            # BUGFIX v28.20: IPv6 安全提取 host
            if srv.startswith("[") and "]" in srv:
                host = srv.split("]")[0][1:]
            elif is_pure_ip(srv) and ":" in srv:
                host = srv  # 纯 IPv6（如 fe80::1）整体就是 host
            elif ":" in srv:
                host = srv.split(":")[0]
            else:
                host = srv
            score = 0
            geo = limiter.get_geo(host)  # v28.22: 统一使用 limiter.get_geo()
            if geo:
                score += 2  # 有地理位置信息，更可靠
                cc = geo.get("countryCode", "").upper()
                # v28.8: 亚洲友好区域高额加分
                if cc in ASIA_REGIONS:
                    score += ASIA_PRIORITY_BONUS
                # v28.8: 非友好区域扣分
                elif cc in NON_FRIENDLY_REGIONS:
                    score -= NON_FRIENDLY_PENALTY
            # 大陆友好加分：名称含大陆/CN/内地关键词
            name_lower = item.get("proxy", {}).get("name", "").lower()
            cn_friendly_kw = ["cn", "china", "国内", "大陆", "直连", "beijing", "shanghai", "guangzhou", "shenzhen"]
            if any(kw in name_lower for kw in cn_friendly_kw):
                score += 30
            return score

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

                def test_one(item):
                    p = item["proxy"]
                    r = clash.test_proxy(p["name"])
                    return item, p, r

                try:
                    with ThreadPoolExecutor(max_workers=40) as tex:  # v28.7: 20→40 并发（Clash API 异步，不需要保守）
                        test_futures = {tex.submit(test_one, item): item for item in batch_items}
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
                                        server=srv, sni=sni_val
                                    )
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
                            fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val
                        ) + "[TCP]"
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
                            fl, int(item["latency"]), tcp=True, server=srv, sni=sni_val
                        ) + "[TCP]"
                        final.append(p)
                        logging.info(f"   [TCP] {p['name']}")
                    else:
                        tested.add(k)

        final = final[:MAX_FINAL_NODES]

        # v28.14: 最终排序 — 强制亚洲优先+Reality+协议评分+区域权重综合加权
        def final_sort_key(p):
            # v28.23: 排序整合大陆友好性评分 + 源权重
            asia = 3 if is_asia(p) else 0  # v28.14: 提高亚洲权重（2→3）
            reality = 1 if is_reality_friendly(p) else 0
            proto_score = PROTOCOL_SCORE.get(p.get("type", ""), 0) / 10.0  # normalize
            # v28.23: 大陆友好性综合评分（替代纯 region_bonus）
            mf_score = mainland_friendly_score(p)
            # v28.49: 亚洲节点额外加分（提高亚洲排序优先级）
            if asia > 0:
                mf_score += 15
            # v28.54: 使用动态源权重（1-20分），替代静态权重
            src_weight = p.get("_src_weight", 3)
            # 兼容旧 region_bonus 逻辑（IP geo 额外惩罚不友好地区）
            region_bonus = 0
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
            geo = limiter.get_geo(host)
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc in NON_FRIENDLY_REGIONS:
                    region_bonus = -NON_FRIENDLY_PENALTY
            # v28.14: extract latency from name for secondary sort
            lat_from_name = 0
            m = re.search(r"\d+", p.get("name", ""))
            if m:
                lat_from_name = int(m.group(0))
            # v28.53: 融合历史可用性评分（0-20分）
            hist_score = _get_node_history_score(p)
            # sort: asia > mainland_friendly > src_weight > reality > proto > region_penalty > hist > latency
            return (-asia, -mf_score, -src_weight, -reality, -proto_score, -region_bonus, -hist_score, lat_from_name)

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
