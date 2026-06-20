# core/stages/tcp_test.py - TCP 延迟测试
# v28.99 Phase C: 从 main_flow.py 提取
# 第一层筛选：TCP Ping 过滤高延迟节点

import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.validator import is_asia
from core.scorer import mainland_friendly_score
from core.testing import test_tcp_node
from core.history import update_node_history
from sources.config import MAX_LATENCY


def build_tcp_queue(all_nodes_list: list, tcp_workers: int = 200) -> list:
    """v30.12: 构建TCP测试队列——所有去重节点全部进入测试，不再截断"""
    asia_nodes = [n for n in all_nodes_list if is_asia(n)]
    non_asia_nodes = [n for n in all_nodes_list if not is_asia(n)]

    # 亚洲节点按大陆友好度评分排序（高分优先）
    try:
        asia_nodes.sort(key=lambda n: mainland_friendly_score(n), reverse=True)
    except (ValueError, KeyError, TypeError):
        logging.debug("Asia nodes sort by mf_score failed, using original order")

    # v30.12: 全量入队，不再受 MAX_TCP_TEST_NODES 截断
    queue = asia_nodes + non_asia_nodes
    logging.info(f"   [STAT] TCP测试队列：{len(asia_nodes)} 亚洲"
                 f" + {len(non_asia_nodes)} 非亚洲 = {len(queue)} 总计（全量）")
    return queue


def run_tcp_test(nlist: list, tcp_workers: int = 200) -> list:
    """v30.12: 并发执行TCP测试（分批报告），返回合格节点列表（latency < MAX_LATENCY）"""
    nres = []
    tcp_workers = min(int(os.getenv("TCP_WORKERS", str(tcp_workers))), 500)
    total = len(nlist)
    batch_size = 500  # v30.12: 每500个节点报告一次

    with ThreadPoolExecutor(max_workers=tcp_workers) as ex:
        futures = {ex.submit(test_tcp_node, p): p for p in nlist}
        completed = 0
        for future in as_completed(futures):
            try:
                result = future.result(timeout=5)  # v30.12: 2→5s（test_tcp_node内部含多次重试）
                if result["latency"] < MAX_LATENCY:
                    nres.append(result)
                    update_node_history(result["proxy"], success=True)
                else:
                    update_node_history(result["proxy"], success=False)
            except (OSError, ValueError, TypeError):
                logging.debug("Proxy test error for node")
            completed += 1
            if completed % batch_size == 0 or completed == total:
                logging.info(f"   [TCP] 进度：{completed}/{total} | 合格：{len(nres)}"
                             f" ({len(nres)*100//max(completed,1)}%)")
    return nres


def sort_tcp_results(nres: list) -> list:
    """TCP 测试后排序：地理位置 > is_asia > Reality > 协议 > 延迟"""
    from network.tls import is_reality_friendly
    from core.scorer import PROTOCOL_SCORE
    from core.filter import _geo_score

    nres.sort(key=lambda x: (
        -_geo_score(x),
        -x["is_asia"],
        -(1 if is_reality_friendly(x["proxy"]) else 0),
        -PROTOCOL_SCORE.get(x["proxy"].get("type", ""), 0) / 10.0,
        x["latency"]
    ))

    # v29: 如果亚洲节点不足 80%，强制亚洲置顶
    asia_count = sum(1 for n in nres if n["is_asia"])
    if asia_count > 0 and asia_count < len(nres) * 0.80:
        asia_nodes = [n for n in nres if n["is_asia"]]
        non_asia_nodes = [n for n in nres if not n["is_asia"]]
        nres = asia_nodes + non_asia_nodes
        logging.info(f"   强制亚洲置顶：{len(asia_nodes)} 亚洲 + {len(non_asia_nodes)} 非亚洲")

    asia_count = sum(1 for n in nres if n["is_asia"])
    tcp_asia_pct = round(asia_count * 100 / max(len(nres), 1), 1)
    logging.debug(f"[OK] 第一层合格：{len(nres)} 个（亚洲：{asia_count}，占比：{tcp_asia_pct}%）\n")
    return nres
