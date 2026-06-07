# core/testing.py - TCP 节点测试函数
# v28.45 Phase5 重构：从 crawler.py 提取 test_tcp_node

import logging

from utils import is_pure_ip
from core.validator import is_asia
from network.tcp import tcp_ping, packet_loss_check
from network.tls import tls_handshake_ok, _proto_handshake_ok
from network.geo import limiter, _ip_geo_batch
from core import history_stability_score


def test_tcp_node(proxy):
    """测试单个节点的 TCP 可达性，返回结果字典。

    从 main() 提取（原 ~50 行）。
    对亚洲节点使用更宽松的丢包检测参数。
    """
    try:
        server = proxy.get("server", "")
        port = proxy.get("port", 0)
        if not server or not port:
            return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

        # BUGFIX v28.20: IPv6 地址安全提取 host
        if server.startswith("[") and "]" in server:
            host = server.split("]")[0][1:]
        elif is_pure_ip(server) and ":" in server:
            host = server  # 纯 IPv6 地址如 fe80::1 需保留原样
        elif ":" in server:
            host = server.split(":")[0]
        else:
            host = server

        # v28.13: 预加载 IP 地理位置，避免后续重复查询
        if is_pure_ip(host) and limiter.get_geo(host) is None:
            _ip_geo_batch([host])

        lat = tcp_ping(host, port)
        if lat >= 9999:
            return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

        # v28.47: 亚洲节点宽松丢包检测
        if is_asia(proxy):
            ok, total, usable = packet_loss_check(host, port, timeout=4.0, attempts=2)
        else:
            ok, total, usable = packet_loss_check(host, port, timeout=3.0, attempts=2)
        if not usable:
            return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

        # BUGFIX v28.20: TLS 握手检测 - 扩展 TLS 端口列表
        TLS_PORTS = {443, 8443, 2053, 2083, 2087, 2096, 8880}
        if proxy.get("tls") and port in TLS_PORTS:
            tls_ok, _ = tls_handshake_ok(host, port, timeout=3.0)
            if not tls_ok:
                return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

        # v28.47: 协议握手验证 - 亚洲节点失败不剔除，非亚洲节点失败剔除
        ptype = proxy.get("type", "").lower()
        if ptype in ("ss", "ssr", "socks5", "http", "vmess", "vless",
                     "trojan", "hysteria", "hysteria2", "tuic", "snell"):
            if is_asia(proxy):
                if not _proto_handshake_ok(host, port, ptype, proxy):
                    logging.debug(f"亚洲节点 {host}:{port} 协议握手失败（仅记录）")
            else:
                if not _proto_handshake_ok(host, port, ptype, proxy):
                    return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

        return {
            "proxy": proxy,
            "latency": float(lat),
            "is_asia": is_asia(proxy),
            "hist_score": history_stability_score(host, port),
        }

    except (OSError, ValueError, TypeError):
        logging.debug("test_tcp_node exception", exc_info=True)
        return {"proxy": proxy, "latency": 9999.0, "is_asia": False}

def test_one(item, clash, namer):
    p = item["proxy"]
    r = clash.test_proxy(p["name"], server=p.get("server"), port=p.get("port"))
    return item, p, r
