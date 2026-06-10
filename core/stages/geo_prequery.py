# core/stages/geo_prequery.py - IP 地理位置预查询
# v28.99 Phase C: 从 main_flow.py 提取
# 在测速前批量查询 IP 地理位置，用于节点区域识别和排序

import logging
from utils import is_pure_ip
from network.geo import _ip_geo_batch


def prequery_ip_geos(nodes: list) -> int:
    """批量预查询节点服务器 IP 地理位置，返回查询数量"""
    all_servers = set()
    for p in nodes:
        srv = p.get("server", "")

        # 提取裸主机名（处理 IPv6 和带端口格式）
        if srv.startswith("[") and "]" in srv:
            host = srv.split("]")[0][1:]
        elif is_pure_ip(srv) and ":" in srv:
            host = srv
        elif ":" in srv:
            host = srv.split(":")[0]
        else:
            host = srv

        if is_pure_ip(host):
            all_servers.add(host)

    servers = list(all_servers)[:500]
    if servers:
        logging.info(f"[GEO] 预查询 IP 地理位置（{len(servers)} 个）...")
        _ip_geo_batch(servers)
    return len(servers)
