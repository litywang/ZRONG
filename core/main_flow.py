# core/main_flow.py - ZRONG 主流程编排
# v28.99 Phase C: 重构为流水线阶段调用
# main() = 编排器，各阶段逻辑下沉到 core/stages/

import time
import signal
import os
import sys
import logging
import asyncio
import subprocess
from pathlib import Path

from utils import is_pure_ip
from core.validator import (
    is_asia, is_node_disabled, batch_health_check_via_clash,
    get_health_summary,
)
from core.collector import collect_nodes
from core import ClashManager, _signal_handler, create_session
from core.stages import (
    deduplicate_by_server_port, prequery_ip_geos,
    build_tcp_queue, run_tcp_test, sort_tcp_results,
    run_speed_test, supplement_tcp,
    apply_quota, write_output, send_telegram_notify,
)
from core.history import (
    load_node_history, load_source_history,
    save_node_history, save_source_history,
    update_node_history,
)
from sources import sync_close_async_http_client
from sources.config import init_config
from core.testing import test_tcp_node

CLASH_API_PORT = 9090


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ZRONG 代理订阅聚合工具')
    parser.add_argument('--version', action='version', version='ZRONG v30.0')
    parser.add_argument('--skip-health-check', action='store_true',
                        default=(os.getenv('ENABLE_HEALTH_CHECK', '0') != '1'),
                        help='跳过健康检查（默认跳过）')
    parser.add_argument('--run-health-check', action='store_false', dest='skip_health_check',
                        help='启用健康检查')
    args = parser.parse_args()
    st = time.time()
    _TIMEOUT_TOTAL = int(os.getenv('TIMEOUT_TOTAL', '2850'))  # v30.0: 47.5分钟硬上限（留12.5分钟余量）

    def _time_left():
        return max(0, _TIMEOUT_TOTAL - (time.time() - st))

    def _check_timeout(stage):
        left = _time_left()
        if left <= 0:
            logging.error(f"[TIMEOUT] {stage} 阶段超时，剩余时间不足，开始应急输出")
            return True
        logging.info(f"[TIMER] {stage}: 已用 {(time.time()-st)/60:.1f}min, 剩余 {left/60:.1f}min")
        return False

    # ── 初始化 ──────────────────────────────────────────────────────────
    init_config()
    load_node_history()
    load_source_history()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # CN CIDR 有效期检查
    try:
        _cidr_file = Path(__file__).parent / "cn_cidr_data.py"
        if _cidr_file.exists():
            age = (time.time() - _cidr_file.stat().st_mtime) / 86400
            if age > 30:
                logging.warning(f"[WARN] CN_CIDR 数据已过期 ({age:.0f} 天)")
    except (OSError, ValueError):
        pass

    clash = ClashManager()
    session = create_session()
    USE_ASYNC = os.getenv("USE_ASYNC_FETCH", "0") == "1"
    proxy_ok = False
    _emergency_nodes = []  # v30.0: 渐进式输出——每批测速后暂存，超时时应急输出

    logging.info("=" * 50)
    logging.info("[START] ZRONG v30.0 - 稳定性优化版")
    logging.info(f"异步抓取: {'ON' if USE_ASYNC else 'OFF'} | 总超时: {_TIMEOUT_TOTAL/60:.0f}min")
    logging.info("=" * 50)

    # ── 阶段1: 采集节点 ───────────────────────────────────────────────
    nodes, stats = collect_nodes(use_async=USE_ASYNC)
    logging.info(
        f"[STAT] 采集: TG={stats['tg_count']}, "
        f"Fork={stats['fork_count']}, 固定={stats['fixed_count']}, "
        f"总URL={stats['total_urls']}, "
        f"过滤={stats['nodes_before_filter']}->{stats['nodes_after_filter']}"
    )
    if not nodes:
        logging.warning("[FAIL] 无有效节点!")
        return

    if _check_timeout("采集完成"):
        return

    # ── 阶段2: 同服务器跨协议去重 ────────────────────────────────────
    nodes = deduplicate_by_server_port(nodes)
    all_nodes = list(nodes.values())

    # ── 阶段3: IP 地理预查询 ─────────────────────────────────────────
    prequery_ip_geos(all_nodes)

    if _check_timeout("预查询完成"):
        return

    # ── 阶段4: TCP 延迟测试 ─────────────────────────────────────────
    logging.info("[SPEED] 第一层：TCP 延迟测试...")
    nlist = build_tcp_queue(all_nodes)
    nres = run_tcp_test(nlist)
    nres = sort_tcp_results(nres)

    if _check_timeout("TCP测试完成"):
        return

    # ── 阶段5: 真实代理测速（带渐进式输出）─────────────────────────
    logging.info("[START] 真实代理测速（分批）...")
    final, proxy_ok = run_speed_test(nres, clash)

    # ── 阶段6: TCP 保底补充 ─────────────────────────────────────────
    tested = set()
    final, _ = supplement_tcp(final, nres, tested, proxy_ok)

    if not final:
        logging.warning("[FAIL] 无合格节点!")
        clash.stop()
        return

    final = final[:MAX_FINAL_NODES]  # 输出上限100-120

    # ── 阶段7: 健康检查（可选）───────────────────────────────────────
    if not args.skip_health_check:
        if proxy_ok and final:
            if _time_left() > 300:  # v30.0: 至少5分钟才做健康检查
                logging.info(f"[START] 健康检查 {len(final)} 个节点...")
                h_results = batch_health_check_via_clash(
                    final, clash_api_port=CLASH_API_PORT,
                    timeout=int(os.getenv('HEALTH_CHECK_TIMEOUT', '8')),
                    max_workers=int(os.getenv('HEALTH_CHECK_MAX_WORKERS', '8'))
                )
                before = len(final)
                final = [p for p in final if not is_node_disabled(p)]
                summary = get_health_summary()
                logging.info(f"[OK] 健康检查: ok={summary['ok']} degraded={summary['degraded']} "
                             f"disabled={summary['disabled']} (移除 {before - len(final)} 个)")
            else:
                logging.warning(f"[SKIP] 健康检查（剩余 {_time_left():.0f}s < 300s）")

    # ── 阶段8: 配额选择 + 排序 ───────────────────────────────────────
    final = apply_quota(final)
    logging.info(f"[OK] 最终：{len(final)} 个")

    # ── 阶段9: 输出 + 推送 ───────────────────────────────────────────
    elapsed = time.time() - st
    write_output(final, nres, stats, elapsed)
    send_telegram_notify(final, nres, stats, elapsed)

    logging.info(f"[DONE] 完成！耗时 {elapsed:.0f}s ({elapsed/60:.1f}min)")

    # ── 清理 ────────────────────────────────────────────────────────
    clash.stop()
    try:
        sync_close_async_http_client()
    except Exception:
        pass
    try:
        session.close()
    except Exception:
        pass
    try:
        from network.geo import limiter
        limiter.save_geo_cache()
    except Exception:
        pass
    save_node_history()
    save_source_history()