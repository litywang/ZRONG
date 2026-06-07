#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/tcp.py - TCP 连接验证工具

从 crawler.py 提取，负责：
- check_node_reachability()：节点可达性检测
- tcp_verify()：TCP 快速握手验证
- _tcp_ping()：TCP 延迟测量
- packet_loss_check()：丢包率检测
- _create_socket()：兼容 IPv4/IPv6 的 socket 创建
"""

import logging
import socket
import time

from utils import is_pure_ip
from core.validator import is_cn_proxy_domain


def check_node_reachability(server, timeout=3.0):
    """v28.19: 放宽检测，解析到 CN IP 不直接排除（可能是 CDN/中转节点）"""
    if not server:
        return False, "空server"
    if is_pure_ip(server):
        return True, "纯IP"
    if is_cn_proxy_domain(server):
        return False, "CN域名"
    # v28.19: 移除 CN IP 硬排除，改为仅记录日志
    from network.dns import resolve_domain
    from network.geo import is_cn_proxy_ip
    resolved_ip = resolve_domain(server, timeout=timeout)
    if resolved_ip and is_cn_proxy_ip(resolved_ip):
        logging.debug("Node %s resolves to CN IP %s, keeping for test", server, resolved_ip)
    return True, "通过"


def packet_loss_check(host, port, timeout=2.0, attempts=3):
    """丢包率检测：多次 TCP ping，统计成功率。"""
    if not host:
        return 0, attempts, False
    success = 0
    for _ in range(attempts):
        lat = _tcp_ping(host, port, timeout=timeout)
        if lat < 9999:
            success += 1
        time.sleep(0.15)
    return success, attempts, success >= 2


def _create_socket(host, timeout=None):
    """创建兼容 IPv4/IPv6 的 TCP socket。"""
    if ":" in host:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout is not None:
        s.settimeout(timeout)
    return s


def tcp_verify(host, port, timeout=1.5):
    """TCP 快速握手验证（仅验证端口在监听）。"""
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


def _tcp_ping(host, port, timeout=2.5):
    """TCP 延迟测量（毫秒），失败返回 9999。"""
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
