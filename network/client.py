#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/client.py - HTTP 客户端管理

从 crawler.py 提取，负责：
- 同步 httpx 客户端（连接池 + HTTP/2）
- 异步 httpx 客户端（异步抓取）
- 客户端关闭（同步/异步上下文）
"""

import asyncio
import logging
import os
import threading
import time

import httpx


# ========== v30.6: 代理可达性检测 ==========

def _detect_proxy() -> str | None:
    """检测本地代理是否可达，返回代理URL或None。
    
    仅在本地运行时检测 127.0.0.1:3067（Karing HTTP代理），
    CI 环境（GitHub Actions）中代理不可达，返回 None。
    """
    import socket as _socket
    proxy_url = os.getenv("HTTP_PROXY", "http://127.0.0.1:3067")
    if not proxy_url:
        return None
    host_port = proxy_url.replace("http://", "").replace("https://", "").split(":")
    if len(host_port) != 2:
        return None
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((host_port[0], int(host_port[1])))
        s.close()
        return proxy_url
    except (OSError, ValueError):
        return None


# ========== httpx 同步客户端（高性能连接池 + HTTP/2）==========

_http_client = None
_http_client_lock = threading.Lock()


def get_http_client():
    """获取全局同步 HTTP 客户端（单例，线程安全）。"""
    global _http_client
    if _http_client is None:
        with _http_client_lock:
            if _http_client is None:  # 双重检查锁定
                proxy = _detect_proxy()
                _http_client = httpx.Client(
                    timeout=httpx.Timeout(15.0, connect=8.0),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
                    follow_redirects=True,
                    verify=False,  # nosec: B501 - Intentional for proxy testing with self-signed certs
                    trust_env=False,  # v30.6: 不从环境变量读取代理
                    proxy=proxy,  # v30.6: 显式传入代理（本地可达时）或None（直连）
                )
    return _http_client


# ========== httpx 异步客户端（异步抓取）==========

_async_http_client = None
_async_http_client_lock = threading.Lock()


def get_async_http_client():
    """获取全局异步 HTTP 客户端（单例，线程安全）。"""
    global _async_http_client
    if _async_http_client is None:
        with _async_http_client_lock:
            if _async_http_client is None:  # 双重检查锁定
                proxy = _detect_proxy()
                _async_http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(15.0, connect=8.0),
                    limits=httpx.Limits(
                        max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "200")),
                        max_keepalive_connections=int(os.getenv("HTTP_KEEPALIVE", "50")),
                        keepalive_expiry=30.0
                    ),
                    follow_redirects=True,
                    verify=False,  # nosec: B501
                    http2=True,
                    trust_env=False,  # v30.6: 不从环境变量读取代理
                    proxy=proxy,  # v30.6: 显式传入代理（本地可达时）或None（直连）
                )
    return _async_http_client


async def close_async_http_client():
    """v28.52: 关闭全局异步HTTP客户端，修复 RESOURCE_LEAK"""
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
    global _async_http_client
    if _async_http_client is not None:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                asyncio.create_task(close_async_http_client())
            else:
                loop.run_until_complete(close_async_http_client())
        except (OSError, RuntimeError, asyncio.TimeoutError):
            logging.debug("同步关闭异步客户端失败")


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
    import random
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
