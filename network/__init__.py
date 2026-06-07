# network 包：ZRONG 网络工具模块
# v28.40 Phase 2 重构：从 crawler.py 提取网络相关函数

from .client import (
    retry_on_exception,
    get_http_client,
    get_async_http_client,
    close_async_http_client,
    sync_close_async_http_client,
)
from .dns import resolve_domain, _DNS_CACHE, _DNS_CACHE_LOCK, DNS_CACHE_TTL
from .tcp import check_node_reachability, tcp_verify, _tcp_ping, tcp_ping, packet_loss_check, _create_socket
from .tls import is_reality_friendly, tls_handshake_ok, http_head_check, _proto_handshake_ok
from .geo import (
    is_cn_proxy_ip,
    _init_cn_lookup,
    SmartRateLimiter,
    limiter,
    _get_geoip2_reader,
    _geoip2_lookup,
    _ip_geo_batch,
)

__all__ = [
    # client.py
    "retry_on_exception",
    "get_http_client",
    "get_async_http_client",
    "close_async_http_client",
    "sync_close_async_http_client",
    # dns.py
    "resolve_domain",
    "_DNS_CACHE",
    "_DNS_CACHE_LOCK",
    "DNS_CACHE_TTL",
    # tcp.py
    "check_node_reachability",
    "tcp_verify",
    "_tcp_ping",
    "tcp_ping",
    "packet_loss_check",
    "_create_socket",
    # tls.py
    "is_reality_friendly",
    "tls_handshake_ok",
    "http_head_check",
    "_proto_handshake_ok",
    # geo.py
    "is_cn_proxy_ip",
    "_init_cn_lookup",
    "SmartRateLimiter",
    "limiter",
    "_get_geoip2_reader",
    "_geoip2_lookup",
    "_ip_geo_batch",
]
