# core/stages/dedup.py - 同服务器跨协议优选去重
# v28.99 Phase C: 从 main_flow.py 提取
# 同一服务器同一端口有多个协议节点时，只保留大陆友好度评分最高的那个

import logging
from core.scorer import mainland_friendly_score


def deduplicate_by_server_port(nodes: dict) -> dict:
    """同服务器跨协议去重，返回去重后的 nodes dict"""
    before = len(nodes)
    srvport_best = {}
    for h, p in nodes.items():
        srv = p.get("server", "").lower()
        port = str(p.get("port", 0))

        # 提取裸主机名（处理 IPv6 和带端口格式）
        if srv.startswith("[") and "]" in srv:
            host = srv.split("]")[0][1:]
        elif ":" in srv:
            host = srv.rsplit(":", 1)[0] if srv.count(":") > 1 else srv.split(":")[0]
        else:
            host = srv

        key = f"{host}:{port}"
        mf = mainland_friendly_score(p)
        if key not in srvport_best or mf > srvport_best[key][1]:
            srvport_best[key] = (h, mf)

    nodes = {h: nodes[h] for h, _ in srvport_best.values()}
    after = len(nodes)
    if before > after:
        logging.info(f"[OK] 同服务器跨协议去重：{before} → {after} 个（保留每IP:Port最优协议）")
    return nodes
