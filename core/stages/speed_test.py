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
    MAX_TCP_TEST_NODES,
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


def run_speed_test(nres: list, clash: ClashManager) -> tuple:
    """通过 Clash 代理执行真实测速，返回 (final_list, proxy_ok)"""
    final = []
    tested = set()
    proxy_ok = False

    if not nres:
        return final, proxy_ok

    # v30.1: 超时控制（避免Actions SIGKILL）
    import time
    _st = time.time()
    _timeout = int(os.getenv('TIMEOUT_TOTAL', '2850'))  # 与main_flow.py一致
    def _time_left():
        return max(0, _timeout - (time.time() - _st))

    untested_items = None
    batch_id = 0

    while True:
        # v30.1: 超时检查（避免Actions SIGKILL）
        if _time_left() < 300:  # 剩余<5分钟，停止测速
            logging.warning(f"[TIMEOUT] 测速阶段剩余时间不足5分钟，停止测速（已用{ (time.time()-_st)/60:.1f}min）")
            break

        batch_id += 1
        if untested_items is None:
            # v30.0: [WEB] 节点预过滤（CDN/WEB代理节点大陆用户不可靠）
            untested_items = [
                item for item in nres
                if f"{item['proxy']['server']}:{item['proxy']['port']}" not in tested
                and not is_node_disabled(item['proxy'])
                and not item['proxy'].get('name', '').startswith('[WEB]')
            ]
            # v30.0: 亚洲节点优先（更快被测速、获得更好的speed数据参与排序）
            untested_items.sort(key=lambda x: (
                0 if is_asia(x['proxy']) else 1,  # Asia first
                x.get('latency', 9999)             # then by TCP latency
            ))
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
                batch_success = 0  # v30.1: 跟踪本批成功率
                for future in as_completed(futures):
                    try:
                        item, p, r = future.result(timeout=8)
                        done_count += 1
                        k = f"{p['server']}:{p['port']}"
                        # v30.1: 分层合格率判断（避免合格率为0）
                        # 第一层：完全合格（success=True + 延迟达标）
                        # 阈值：通用5000ms，亚洲8000ms（宽松，慢节点>死节点）
                        latency_ok = (
                            r["latency"] < 5000
                            or (is_asia(p) and r["latency"] < 8000)
                        )
                        # v30.1: 放宽速度要求（最低0.5KB/s，避免误杀）
                        speed_ok = r.get("speed", 0) >= 0.5
                        if r["success"] and latency_ok and speed_ok:
                            _name_node(p, r, namer, tcp=False)
                            final.append(p)
                            tested.add(k)
                            batch_success += 1
                            update_node_history(p, success=True)
                            logging.info(f"   [OK] {p['name']}")
                        # v30.1: 第二层：TCP保底（仅亚洲节点，TCP<500ms）
                        elif is_asia(p) and item.get("latency", 9999) < 500:
                            # TCP延迟低但代理测速失败，可能是测速URL问题，保留节点
                            p["name"] = namer.generate(
                                get_region(p.get("name", ""), server=p.get("server", ""))[0],
                                lat=int(item["latency"]),
                                score=mainland_friendly_score(p),
                                tcp=True,
                                server=p.get("server", ""),
                                sni=p.get("sni", "") or p.get("servername", ""),
                                mainland_reachable=False,
                                proto=p.get("type", "")
                            )
                            p["mainland_reachable"] = False
                            p["_speed"] = 0.0
                            final.append(p)
                            tested.add(k)
                            logging.info(f"   [TCP-FALLBACK] {p['name']} (代理测速失败但TCP延迟低)")
                        else:
                            update_node_history(p, success=False)
                        if done_count % 20 == 0:
                            logging.info(f"   进度：{done_count}/{len(batch_items)} | 合格：{len(final)} (本批成功:{batch_success})")
                    except (OSError, ValueError, TypeError):
                        logging.debug("Batch proxy test error")
                # v30.1: 本批成功率过低时记录警告
                if batch_success == 0 and len(batch_items) > 10:
                    logging.warning(f"   [WARN] 第{batch_id}批测速全部失败！可能原因：节点质量问题或Clash配置问题")
            logging.debug(f"\n   第{batch_id}批完成：累计合格 {len(final)} 个\n")
        except Exception:
            logging.debug(f"   [FAIL] Clash 异常")
            clash.stop()
            break

    proxy_ok = True
    return final, proxy_ok


def supplement_tcp(final: list, nres: list, tested: set, proxy_ok: bool) -> tuple:
    """v30.0 Phase 6h: TCP保底补充（宽松约束版本）
    
    约束：
    - 仅speed_test合格>=15节点时才触发（降低基线，避免0输出）
    - 亚洲节点优先，非亚洲也可补充
    - TCP延迟<800ms（GH Actions到海外平均延迟）
    - 跳过UA/TR/IR等低价值区域
    """
    if not proxy_ok:
        logging.warning("[WARN] Clash测速全部失败，跳过TCP补充")
        return final, proxy_ok
    # 基线检查：Clash合格<100时跳过TCP补充（输出节点以下限100为准）
    if len(final) < 100:
        logging.warning(f"[WARN] Clash合格仅{len(final)}个<100，跳过TCP补充，输出{len(final)}个")
        return final, proxy_ok

    asia_count = sum(1 for p in final if is_asia(p))
    tcp_needed = min(50, max(0, 150 - len(final)))  # v30.1: 最多补充50个
    if tcp_needed <= 0:
        return final, proxy_ok

    lf_score = mainland_friendly_score
    from core.filter import is_non_friendly_region, final_sort_key

    logging.warning(f"[WARN] 测速合格{len(final)}个(亚洲{asia_count})，TCP补充上限{tcp_needed}（宽松约束）...")
    namer = NodeNamer()
    added = 0
    for item in nres:
        if added >= tcp_needed:
            break
        p = item["proxy"]
        k = f"{p['server']}:{p['port']}"
        if k in tested:
            continue
        # 亚洲优先，非亚洲但TCP好也可
        is_item_asia = item.get("is_asia", False)
        # TCP延迟<800ms（GH Actions海外平均延迟）
        if item["latency"] >= 800:
            tested.add(k)
            continue
        # 非亚洲节点只接受TCP<300ms
        if not is_item_asia and item["latency"] >= 300:
            tested.add(k)
            continue
        # 排除低价值区域
        if is_non_friendly_region(p):
            tested.add(k)
            continue
        # 通过全部约束
        tested.add(k)
        _name_node(p, item, namer, tcp=True)
        final.append(p)
        added += 1
        logging.info(f"   [TCP] {p['name']}")

    if added:
        logging.info(f"   TCP补充完成：+{added} 个")
    return final, proxy_ok
