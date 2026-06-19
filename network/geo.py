#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/geo.py - GeoIP 查询与限流

从 crawler.py 提取，负责：
- SmartRateLimiter：域名级智能限流 + IP 地理缓存持久化
- _init_cn_lookup / is_cn_proxy_ip：CN IP 快速判断
- _get_geoip2_reader / _geoip2_lookup / _ip_geo_batch：GeoIP2 查询
"""

import json
import random
import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from utils import REQUESTS_PER_SECOND, is_pure_ip
from .cn_cidr_data import CN_IP_RANGES  # v28.15: CN IP 范围常量

# ===== CN IP 查找表 =====
_CN_IP_SET = set()
_CN_IP_NETS = []


def _init_cn_lookup():
    """初始化 CN IP 查找表"""
    global _CN_IP_SET, _CN_IP_NETS
    for net in CN_IP_RANGES:
        _CN_IP_NETS.append(net)
        _CN_IP_SET.add(net.network_address.packed[:1])


_init_cn_lookup()


def is_cn_proxy_ip(ip_str):
    """精确 CN IP 判断（4219 条 CIDR，先 /8 快排再精确匹配）"""
    if not ip_str:
        return None
    try:
        ip = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        logging.debug("Exception occurred", exc_info=True)
        return None
    if isinstance(ip, ipaddress.IPv4Address):
        first_octet = ip.packed[:1]
        if first_octet not in _CN_IP_SET:
            return False
    for cidr in _CN_IP_NETS:
        if ip in cidr:
            return True
    return False


# ===== GeoIP2 本地数据库 =====
_GEOIP2_AVAILABLE = False
try:
    import geoip2.database
    _GEOIP2_AVAILABLE = True
except ImportError:
    pass

_geoip2_reader = None


def _get_geoip2_reader():
    """获取 GeoIP2 读取器（延迟初始化 + 缓存）"""
    global _geoip2_reader
    if _geoip2_reader is not None:
        return _geoip2_reader
    if not _GEOIP2_AVAILABLE:
        return None
    mmdb_paths = [
        Path(__file__).parent / "GeoLite2-City.mmdb",
        Path("/usr/share/GeoIP/GeoLite2-City.mmdb"),
        Path(os.environ.get("GEOIP_DB_PATH", "")) if os.environ.get("GEOIP_DB_PATH") else None,
    ]
    for p in mmdb_paths:
        if p and p.exists():
            try:
                _geoip2_reader = geoip2.database.Reader(str(p))
                logging.debug("[GeoIP2] 已加载本地数据库: %s", p)
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


def _ip_geo_batch(ips):
    """批量查询 IP 地理位置，优先 GeoIP2，回退 ip-api.com"""
    if not ips:
        return
    from network.client import get_http_client
    to_query = [ip for ip in ips if limiter.get_geo(ip) is None and is_pure_ip(ip)]
    if not to_query:
        return
    geoip2_reader = _get_geoip2_reader()
    if geoip2_reader is not None:
        local_hits = 0
        for ip in to_query:
            geo = _geoip2_lookup(ip)
            if geo:
                limiter.set_geo(ip, geo)
                local_hits += 1
        if local_hits == len(to_query):
            return
        to_query = [ip for ip in to_query if limiter.get_geo(ip) is None]
    BATCH_SIZE = 100
    for i in range(0, len(to_query), BATCH_SIZE):
        batch = to_query[i:i + BATCH_SIZE]
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
                    logging.debug("   IP 地理位置查询：%d 个（已缓存 %d）",
                                 len(batch), len(limiter.ip_geo_cache))
                    break
                elif r.status_code in (429, 503):
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_err = e
                time.sleep(1.5 ** attempt)
        else:
            logging.debug("IP 地理位置查询失败（已重试3次）: %s", last_err)
        limiter.save_geo_cache()


# ===== SmartRateLimiter =====
try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(dict):
        def __init__(self, maxsize=10000, ttl=86400):
            super().__init__()
            self.maxsize = maxsize
            self.ttl = ttl


class SmartRateLimiter:
    """v28.17: 域名级智能限流 + IP 地理缓存持久化"""

    def __init__(self):
        self.locks = {}
        self.last_call = {}
        self.domain_intervals = {
            'default': 1.0 / REQUESTS_PER_SECOND,
            'ip-api.com': 0.5,
            'gstatic.com': 0.2,
            'cloudflare.com': 0.3,
            'apple.com': 0.3,
            'raw.githubusercontent.com': 0.1,
            't.me': 1.0,
        }
        self.ip_geo_cache = TTLCache(maxsize=10000, ttl=86400)
        self._cache_lock = threading.Lock()
        self._load_geo_cache()

    def _get_interval(self, domain):
        for key, interval in self.domain_intervals.items():
            if key in domain:
                return interval
        return self.domain_intervals['default']

    def _cleanup_stale(self):
        with self._cache_lock:
            now = time.time()
            stale = [d for d, t in list(self.last_call.items()) if now - t > 60]
            for d in stale:
                self.locks.pop(d, None)
                self.last_call.pop(d, None)

    _init_lock = threading.Lock()

    def wait(self, url=""):
        domain = urlparse(url).netloc or "default"
        with self._init_lock:
            if domain not in self.locks:
                self.locks[domain] = threading.Lock()
                self.last_call[domain] = 0.0
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
        return Path(__file__).parent / ".ip_geo_cache.json"

    def _load_geo_cache(self):
        try:
            cache_file = self._get_cache_file()
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for ip, item in data.items():
                        if time.time() - item.get('ts', 0) < 86400:
                            self.ip_geo_cache[ip] = item
                logging.debug("[SmartRateLimiter] 已加载 %d 条IP地理缓存", len(self.ip_geo_cache))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.debug("加载IP地理缓存失败: %s", e)

    def save_geo_cache(self):
        try:
            with self._cache_lock:
                cache_file = self._get_cache_file()
                data = {}
                for ip, item in self.ip_geo_cache.items():
                    data[ip] = dict(item, ts=time.time())
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                logging.debug("[SmartRateLimiter] 已保存 %d 条IP地理缓存", len(data))
        except (OSError, TypeError) as e:
            logging.debug("保存IP地理缓存失败: %s", e)

    def get_geo(self, ip):
        with self._cache_lock:
            return self.ip_geo_cache.get(ip)

    def set_geo(self, ip, geo_data):
        with self._cache_lock:
            self.ip_geo_cache[ip] = geo_data


limiter = SmartRateLimiter()
