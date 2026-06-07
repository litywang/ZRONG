#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/tls.py - TLS 握手与协议验证工具

从 crawler.py 提取，负责：
- is_reality_friendly()：REALITY 节点识别
- tls_handshake_ok()：TLS 握手验证
- http_head_check()：HTTP HEAD 探测
- _proto_handshake_ok()：协议层握手验证
"""

import http.client
import logging
import socket
import ssl


def is_reality_friendly(p):
    """检查节点是否 REALITY 友好（优先放行）。"""
    t = p.get("type", "")
    if t == "vless" and p.get("reality-opts"):
        return True
    name = p.get("name", "").lower()
    return any(k in name for k in ["reality", "real-", "vlss", "lima", "fly", "ssrsub"])


def tls_handshake_ok(host, port, timeout=5.0):
    """TLS 握手验证，返回 (ok: bool, reason: str)。"""
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


def http_head_check(host, port, timeout=3.0):
    """HTTP HEAD 探测，返回是否可达。"""
    if not host:
        return False
    try:
        if port in (443, 8443, 8080):
            try:
                conn = http.client.HTTPSConnection(
                    host, port, timeout=timeout,
                    context=ssl._create_unverified_context()
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


def _proto_handshake_ok(host, port, ptype, proxy=None, timeout=3.0):
    """验证端口是否响应代理协议。"""
    try:
        if ptype in ("vmess", "vless", "trojan"):
            if proxy and proxy.get("tls"):
                tls_ok, _ = tls_handshake_ok(host, port, timeout=timeout)
                return tls_ok
            return True
        elif ptype in ("ss", "ssr"):
            s = None
            try:
                from network.tcp import _create_socket
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"\x00")
                try:
                    data = s.recv(16)
                    if data and data != b'':
                        return False
                    return True
                except socket.timeout:
                    return True
                except (ConnectionResetError, ConnectionAbortedError):
                    return True
            except (socket.timeout, OSError, ConnectionRefusedError):
                logging.debug("SS handshake probe failed", exc_info=True)
                return True
            finally:
                if s:
                    try:
                        s.close()
                    except (OSError, socket.error):
                        logging.debug("Exception occurred", exc_info=True)
                        pass
        elif ptype in ("hysteria", "hysteria2"):
            return True
        elif ptype == "http":
            s = None
            try:
                from network.tcp import _create_socket
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"CONNECT www.gstatic.com:443 HTTP/1.1\r\nHost: www.gstatic.com:443\r\n\r\n")
                data = s.recv(256)
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
            s = None
            try:
                from network.tcp import _create_socket
                s = _create_socket(host, timeout)
                s.connect((host, port))
                s.send(b"\x05\x01\x00")
                data = s.recv(2)
                return len(data) >= 2 and data[0] == 5
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
            return True
    except Exception as e:
        logging.debug("Exception occurred", exc_info=True)
        return True
