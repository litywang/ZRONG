"""
core/collector.py - 节点采集模块

从 core/main_flow.py 的 main() 中提取采集阶段逻辑，负责：
- Telegram 频道爬取
- GitHub Fork 发现
- 固定订阅源加载
- URL 去重与按权重排序
- 节点抓取与解析（同步/异步）
- 节点质量过滤

使用：
    from core.collector import collect_nodes
"""

import logging
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def collect_nodes(use_async=False, max_fetch_nodes=5000, fetch_workers=150):
    """采集节点，返回 (nodes_dict, stats_dict)
    
    从 Telegram、GitHub Forks、固定订阅源采集节点，
    进行质量过滤后返回节点字典。
    
    Args:
        use_async: 是否使用异步抓取（默认False，使用同步）
        max_fetch_nodes: 最大抓取节点数（默认5000）
        fetch_workers: 同步抓取并发数（默认150）
    
    Returns:
        (nodes, stats) where stats = {
            'tg_count': ...,
            'fork_count': ...,
            'fixed_count': ...,
            'total_urls': ...,
            'yaml_count': ...,
            'txt_count': ...,
            'nodes_before_filter': ...,
            'nodes_after_filter': ...,
        }
    """
    # 延迟导入，避免循环依赖
    from sources import (
        crawl_telegram_channels, strip_url, discover_github_forks,
        fetch_and_parse, async_fetch_nodes,
    )
    from sources.config import is_url_healthy
    from sources.config import TELEGRAM_CHANNELS, CANDIDATE_URLS
    from core.history import dynamic_source_weight, update_source_history
    from core.filter import filter_quality, reset_filter_state
    from core.validator import is_asia

    # v30.0: 重置 [WEB] 节点计数器（按自然日清零）
    reset_filter_state()

    # 1. Telegram 频道爬取（最高优先级）
    logger.info("[TG] 爬取 Telegram 频道（优先）...")
    tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=1, limits=20)
    tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
    logger.debug(f"[OK] Telegram 订阅：{len(tg_urls)} 个")
    
    # 2. GitHub Fork 发现（中等优先级）
    logger.info("[SEARCH] GitHub Fork 发现...")
    fork_subs = discover_github_forks()
    
    # 3. 固定订阅源（最低优先级，放最后）
    logger.info("[LOAD] 加载固定订阅源（补充）...")
    fixed_urls = [strip_url(u) for u in CANDIDATE_URLS if strip_url(u)]
    
    # 4. 合并去重
    all_urls = []
    all_urls.extend(tg_urls)
    all_urls.extend(fork_subs)
    all_urls.extend(fixed_urls)
    all_urls = list(set(all_urls))
    
    # 5. 按动态权重排序订阅源（高权重源优先抓取）
    url_weights = {u: dynamic_source_weight(u) for u in all_urls}
    all_urls.sort(key=lambda u: -url_weights[u])
    logger.info(f"[STAT] 源权重排序完成（最高权重: {url_weights[all_urls[0]]:.1f})")
    
    # 6. 抓取节点
    logger.info("[LOAD] 抓取节点...")
    nodes = {}
    yaml_count = 0
    txt_count = 0
    url_results = {}  # url -> (success, node_count, asia_count)
    
    if use_async:
        logger.info("[WEB] 使用异步抓取模式...")
        # v30.0: URL 健康检查（快速过滤死链，减少无效请求）
        healthy_urls = [u for u in all_urls if is_url_healthy(u)]
        skipped = len(all_urls) - len(healthy_urls)
        if skipped > 0:
            logger.info(f"[WEB] 健康检查：跳过 {skipped} 个不可达 URL，剩余 {len(healthy_urls)} 个")
        nodes, yaml_count, txt_count, url_results = asyncio.run(
            async_fetch_nodes(healthy_urls, max_fetch_nodes)
        )
    else:
        # v30.0: URL 健康检查（同步模式）
        healthy_urls = [u for u in all_urls if is_url_healthy(u)]
        skipped = len(all_urls) - len(healthy_urls)
        if skipped > 0:
            logger.info(f"[WEB] 健康检查：跳过 {skipped} 个不可达 URL，剩余 {len(healthy_urls)} 个")
        with ThreadPoolExecutor(max_workers=fetch_workers) as ex:
            futures = {ex.submit(fetch_and_parse, u): u for u in healthy_urls}
            completed = 0
            for future in as_completed(futures):
                url = futures[future]
                completed += 1
                local_nodes, is_yaml = future.result()
                node_count = len(local_nodes)
                asia_count = sum(1 for p in local_nodes.values() if is_asia(p))
                url_results[url] = (node_count > 0, node_count, asia_count)
                for h, p in local_nodes.items():
                    if h not in nodes:
                        p["_src_weight"] = dynamic_source_weight(url)
                        nodes[h] = p
                if local_nodes:
                    if is_yaml:
                        yaml_count += 1
                    else:
                        txt_count += 1
                if completed % 50 == 0:
                    logger.debug(f"   进度: {completed}/{len(all_urls)} | 节点: {len(nodes)}")
                if len(nodes) >= max_fetch_nodes:
                    break
    
    # 6.5. 更新所有源的历史记录
    for url, (success, node_count, asia_count) in url_results.items():
        update_source_history(url, success, node_count, asia_count)
    
    logger.debug(f"[OK] 唯一节点：{len(nodes)} 个 (YAML源: {yaml_count}, TXT源: {txt_count})")
    
    if not nodes:
        logger.warning("[FAIL] 无有效节点!")
        return {}, {}
    
    # 7. 节点质量过滤
    logger.info("[SEARCH] 节点质量过滤...")
    before_filter = len(nodes)
    nodes = {h: p for h, p in nodes.items() if filter_quality(p)}
    after_filter = len(nodes)
    logger.info(f"[OK] 质量过滤：{before_filter} → {after_filter} 个（排除 {before_filter - after_filter} 个低质量节点)")
    
    stats = {
        'tg_count': len(tg_urls),
        'fork_count': len(fork_subs),
        'fixed_count': len(fixed_urls),
        'total_urls': len(all_urls),
        'yaml_count': yaml_count,
        'txt_count': txt_count,
        'nodes_before_filter': before_filter,
        'nodes_after_filter': after_filter,
    }
    
    return nodes, stats
