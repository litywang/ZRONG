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
            with ThreadPoolExecutor(max_workers=max(1, int(os.getenv('CLASH_TEST_WORKERS', '3')))) as tex:  # v30.10: Actions直连可用并发
                futures = {tex.submit(test_one, item, clash, namer): item
                           for item in batch_items}
                done_count = 0
                batch_success = 0  # v30.1: 跟踪本批成功率
                for future in as_completed(futures):
                    try:
                        item, p, r = future.result(timeout=20)  # v30.6: 匹配requests 15s timeout
                        done_count += 1
                        k = f"{p['server']}:{p['port']}"
                        # v30.1: 分层合格率判断（避免合格率为0）
                        # 第一层：完全合格（success=True + 延迟达标）
                        # 阈值：通用5000ms，亚洲8000ms（宽松，慢节点>死节点）
                        # v30.6: 移除延迟硬上限（dialer-proxy 经 Karing 转发延迟加成大）
                        latency_ok = 0 < r["latency"] < 30000
                        # v30.1: 放宽速度要求（最低0.5KB/s，避免误杀）
                        speed_ok = r.get("speed", 0) >= 0.1  # v30.10: Actions环境代理节点速度低，0.5→0.1
                        if r["success"] and latency_ok and speed_ok:
                            _name_node(p, r, namer, tcp=False)
                            final.append(p)
                            tested.add(k)
                            batch_success += 1
                            update_node_history(p, success=True)
                            logging.info(f"   [OK] {p['name']}")
                        else:
                            update_node_history(p, success=False)
                            # v30.7: 打印第一个失败原因（调试用）
                            if batch_success == 0 and done_count == 1:
                                logging.warning(f"   [DEBUG] 第一个失败: {p.get('name','?')} - success={r.get('success')}, latency={r.get('latency')}, speed={r.get('speed')}, error={r.get('error','')}")
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
    """v33.0: TCP保底补充——Clash实测合格节点不足时，从TCP合格列表补充"""
    if proxy_ok and len(final) >= 100:
        logging.info(f"[TCP] Clash合格{len(final)}个已达标，无需TCP保底")
        return final, proxy_ok

    logging.info(f"[TCP] Clash合格{len(final)}个不足，开始TCP保底补充...")
    # 从 final 列表构建已测节点集合（main_flow 传递的 tested 可能为空）
    if not tested:
        tested = {f"{p['server']}:{p['port']}" for p in final if p.get('server')}

    # 从TCP合格列表中找未被Clash测过的节点
    untested_tcp = [
        item for item in nres
        if f"{item['proxy']['server']}:{item['proxy']['port']}" not in tested
        and item.get("latency", 9999) < 8000
    ]

    # 优先亚洲节点
    untested_tcp.sort(key=lambda x: (
        0 if x.get("is_asia") else 1,
        x.get("latency", 9999)
    ))

    # 取排名靠前的作为保底节点（质量由TCP测试保证）
    need = max(0, 100 - len(final))
    if untested_tcp:
        untested_tcp = untested_tcp[:min(need * 2, len(untested_tcp))]
        logging.info(f"   TCP保底候选：{len(untested_tcp)}个")

        from core.namer import NodeNamer
        namer = NodeNamer()
        from network.tls import is_reality_friendly
        from core.scorer import mainland_friendly_score
        from utils import get_region

        for item in untested_tcp:
            p = item["proxy"]
            srv = p.get("server", "")
            sni_val = p.get("sni", "") or p.get("servername", "")
            ws_opts = p.get("ws-opts", {})
            if isinstance(ws_opts, dict):
                ws_host = ws_opts.get("headers", {}).get("Host", "")
                if ws_host:
                    sni_val = ws_host
            fl, _ = get_region(p.get("name", ""), server=srv, sni=sni_val)
            mf_score = mainland_friendly_score(p)
            p["name"] = namer.generate(
                fl, lat=int(item["latency"]), score=mf_score, tcp=True,
                server=srv, sni=sni_val, mainland_reachable=False,
                proto=p.get("type", "")
            )
            p["mainland_reachable"] = False
            tested.add(f"{srv}:{p.get('port', '')}")

        # 合并 + 重新应用配额
        combined = final + [item["proxy"] for item in untested_tcp]
        from core.stages.output import apply_quota as _apply_quota
        result = _apply_quota(combined)
        added = len(result) - len(final)
        logging.info(f"[TCP] 保底补充完成：原始{len(final)}个 + 新增{added}个 = 共{len(result)}个")
        return result, True

    logging.info(f"[TCP] 无可用的TCP保底节点")
    return final, proxy_ok
