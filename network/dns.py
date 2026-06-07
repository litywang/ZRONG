#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/dns.py - DNS 解析与缓存

从 crawler.py 提取，负责：
- resolve_domain()：域名解析（含线程安全缓存）
- _DNS_CACHE / _DNS_CACHE_LOCK：DNS 缓存全局变量
"""

import logging
import socket
import threading
import time

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# ===== DNS 缓存（带TTL）=====
_DNS_CACHE = {}
_DNS_CACHE_LOCK = threading.Lock()

DNS_CACHE_TTL = 300


def resolve_domain(domain, timeout=3):
    """解析域名，带线程安全缓存。"""
    if not domain or not isinstance(domain, str):
        return None
    now = time.time()
    with _DNS_CACHE_LOCK:
        if domain in _DNS_CACHE:
            ip, ts = _DNS_CACHE[domain]
            if now - ts < DNS_CACHE_TTL:
                return ip
    try:
        with ThreadPoolExecutor(max_workers=1) as exc:
            future = exc.submit(socket.gethostbyname, domain)
            try:
                ip = future.result(timeout=timeout)
            except FuturesTimeoutError:
                ip = None
        with _DNS_CACHE_LOCK:
            _DNS_CACHE[domain] = (ip, now)
        return ip
    except (socket.gaierror, socket.timeout, OSError):
        with _DNS_CACHE_LOCK:
            _DNS_CACHE[domain] = (None, now)
        return None
