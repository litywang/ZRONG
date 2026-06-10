# core/stages/speed_test.py - 真实代理测速 + TCP 补充
# v28.99 Phase C: 从 main_flow.py 提取
# 第二层筛选：通过 Clash 代理实测速度，TCP 补充保底

import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from core import ClashManager, NodeNamer
from core.validator import is_asia, is_node_disabled
from core.testing import test_one
from core.scorer import mainland_friendly_score
from core.history import update_node_history
from utils import get_region
from network.tls import is_reality_friendly
from sources.config import (
    MAX_FINAL_NODES, MAX_PROXY_TEST_NODES, MAX_PROXY_LATENCY,
    MAX_TCP_TEST_NODES, ASIA_TCP_RELAX, TEST_URL,
)


def _name_node(p: dict, item: dict, namer: NodeNamer, tcp: bool = False) -> None:
    """为节点生成规范名称并附加元数据"""
    srv = p.get("server", "")
    sni_val = p.get("sni", "") or p.get("servername", "")
    ws_opts = p.get("ws-opts", {})
    if isinstance(ws_opts, dict):
        ws_host = ws_opts.get("headers", {}).get("Host", "")
        if ws_host:
            sni_val = ws_host
    fl, _ = get_region(p.get("name", ""), server=srv, sni=sni_val)
    mf_score = mainland_friendly_score(p)
    if tcp:
        p["name"] = namer.generate(
            fl, lat=int(item["latency"]), score=mf_score, tcp=True,
            server=srv, sni=sni_val, mainland_reachable=False,
            proto=p.get("type", "")
        )
        p["mainland_reachable"] = False
    else:
        p["name"] = namer.generate(
            fl, lat=int(item["latency"]), score=mf_score, speed=item.get("speed", 0),
            tcp=False, server=srv, sni=sni_val,
            mainland_reachable=item.get("mainland_reachable", False),
            proto=p.get("type", "")
        )
        p["mainland_reachable"] = item.get("mainland_reachable", False)
        p["_speed"] = item.get("speed", 0.0)


def run_speed_test(nres: list, clash: ClashManager) -> list:
    """通过 Clash 代理执行真实测速，返回合格节点列表"""
    final = []
    tested = set()

    if not nres:
        return final

    batch_enough = False
    untested_items = None
    batch_id = 0
    nres_untested = nres[:MAX_TCP_TEST_NODES]

    while len(final) < MAX_FINAL_NODES and not batch_enough:
        batch_id += 1
        if untested_items is None:
            untested_items = [
                item for item in nres_untested
                if f"{item['proxy']['server']}:{item['proxy']['port']}" not in tested
                and not is_node_disabled(item['proxy'])
            ]
        batch_items = untested_items[:MAX_PROXY_TEST_NODES]
        untested_items = untested_items[MAX_PROXY_TEST_NODES:]
        if not batch_items:
            break

        tprox = [item["proxy"] for item in batch_items]
        logging.info(f"[PACKAGE] 第{batch_id}批：{len(tprox)} 个节点...")

        if not clash.create_config(tprox) or not clash.start():
            logging.warning("   [FAIL] Clash 启动失败，跳过本批")
            clash.stop()
            break

        namer = NodeNamer()

        try:
            with ThreadPoolExecutor(max_workers=40) as tex:
                futures = {tex.submit(test_one, item, clash, namer): item
                           for item in batch_items}
                done_count = 0
                for future in as_completed(futures):
                    try:
                        item, p, r = future.result(timeout=8)
                        done_count += 1
                        k = f"{p['server']}:{p['port']}"
                        # v29: 亚洲节点延迟放宽 2.5 倍
                        latency_ok = (
                            r["latency"] < MAX_PROXY_LATENCY
                            or (is_asia(p) and r["latency"] < MAX_PROXY_LATENCY * 1.5)
                        )
                        if r["success"] and latency_ok:
                            _name_node(p, r, namer, tcp=False)
                            final.append(p)
                            tested.add(k)
                            update_node_history(p, success=True)
                            logging.info(f"   [OK] {p['name']}")
                        else:
                            update_node_history(p, success=False)
                        if len(final) >= MAX_FINAL_NODES:
                            batch_enough = True
                            break
                        if done_count % 20 == 0:
                            logging.info(f"   进度：{done_count}/{len(batch_items)} | 合格：{len(final)}")
                    except (OSError, ValueError, TypeError):
                        logging.debug("Batch proxy test error")
            logging.debug(f"\n   第{batch_id}批完成：累计合格 {len(final)} 个\n")
        except Exception:
            logging.debug(f"   [FAIL] Clash 异常")
            clash.stop()
            break

    return final


def supplement_tcp(final: list, nres: list, tested: set) -> list:
    """TCP 延迟保底补充：测速合格不足时补充 TCP 低延迟节点"""
    if len(final) >= MAX_FINAL_NODES:
        return final

    logging.warning(f"\n[WARN] 测速合格 {len(final)} 个/{MAX_FINAL_NODES} 目标，使用 TCP 补充...")
    namer = NodeNamer()

    for item in nres:
        if len(final) >= MAX_FINAL_NODES:
            break
        p = item["proxy"]
        k = f"{p['server']}:{p['port']}"
        if k in tested:
            continue
        if item["is_asia"] and item["latency"] < ASIA_TCP_RELAX * 1.5:
            tested.add(k)
            _name_node(p, item, namer, tcp=True)
            final.append(p)
            logging.info(f"   [TCP] {p['name']}")
        elif item["latency"] < 450:
            tested.add(k)
            _name_node(p, item, namer, tcp=True)
            final.append(p)
            logging.info(f"   [TCP] {p['name']}")
        else:
            tested.add(k)

    return final[:MAX_FINAL_NODES]
