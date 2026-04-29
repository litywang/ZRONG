# sources/subscription.py - 订阅源抓取模块
# v28.53: 重构，使用 sources.config 替代 sys.modules hack

import os
import re
import time
import random
import base64
import hashlib
import logging
import asyncio
from typing import Dict, List, Tuple, Optional

import httpx
import yaml
from . import config
from .utils import (
    clean_url, is_valid_url, check_subscription_quality,
    strip_url, check_url_fast, check_url,
    is_base64, decode_b64,
    is_yaml_content, parse_yaml_proxies,
    source_weight,
)

# clean_url, is_valid_url, check_subscription_quality 等函数已移至 utils.py
# 此处统一从 utils 导入，避免重复定义，行为完全一致


# source_weight 已从 utils.py 导入，此处不再重复定义
# 如需调整国内友好节点权重，请修改 utils.source_weight 或 crawler._dynamic_source_weight


# ===== 同步抓取 =====

def fetch(url: str) -> str:
    """同步抓取单个 URL（GitHub URL 多镜像池遍历 + HTTP/2 + 重试）"""
    limiter = config.limiter()
    client = config.get_http_client()
    cfg = config.config()
    headers = random.choice(cfg.get('HEADERS_POOL', [{}]))
    is_github = "github" in url.lower() or "raw.githubusercontent" in url

    limiter.wait(url)

    # 非GitHub URL：直连
    if not is_github:
        try:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.text.strip()
            elif resp.status_code in (403, 429):
                time.sleep(3)
        except (httpx.RequestError, httpx.TimeoutException):
            logging.debug("fetch failed for %s", url, exc_info=True)
        return ""

    # GitHub: 镜像池 + 原始URL兜底
    all_urls = []
    for mirror in cfg.get('SUB_MIRRORS', []):
        if mirror:
            mirror_host = mirror.rstrip("/").replace("https://", "")
            all_urls.append(url.replace("raw.githubusercontent.com", mirror_host))
    all_urls.append(url)

    for try_url in all_urls:
        try:
            resp = client.get(try_url, headers=headers)
            if resp.status_code == 200:
                text = resp.text.strip()
                if text.startswith("<!") or text.startswith("<html"):
                    continue
                if len(text) > 50:
                    return text
            elif resp.status_code in (403, 429, 503):
                time.sleep(random.uniform(2.0, 5.0))
        except (httpx.RequestError, httpx.TimeoutException):
            logging.debug("fetch failed for %s", try_url, exc_info=True)
            time.sleep(random.uniform(0.5, 1.5))
    return ""


def fetch_and_parse(url: str) -> Tuple[Dict, bool]:
    """同步获取并解析单个 URL 的节点（用于 ThreadPoolExecutor）"""
    parse_node_fn = config.parse_node()
    ProxyNode_cls = config.ProxyNode()

    if parse_node_fn is None or ProxyNode_cls is None:
        logging.debug("parse_node or ProxyNode not available")
        return {}, False

    local_nodes = {}
    c = fetch(url)
    if not c:
        return local_nodes, False

    src_weight = source_weight(url)

    if is_yaml_content(c):
        yaml_nodes = parse_yaml_proxies(c)
        for p in yaml_nodes:
            h = ProxyNode_cls.from_dict(p).dedup_key()
            if h not in local_nodes:
                p["_src_weight"] = src_weight
                local_nodes[h] = p
        return local_nodes, True

    if is_base64(c):
        c = decode_b64(c)
    for line in c.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = parse_node_fn(line)
        if p:
            h = ProxyNode_cls.from_dict(p).dedup_key()
            if h not in local_nodes:
                p["_src_weight"] = src_weight
                local_nodes[h] = p
    return local_nodes, False


# ===== 异步抓取 =====

_async_fetch_sem = None


def _get_async_sem():
    global _async_fetch_sem
    if _async_fetch_sem is None:
        _async_fetch_sem = asyncio.Semaphore(80)
    return _async_fetch_sem


async def async_fetch_url(client: httpx.AsyncClient, url: str, mirror_pool: List[str] = None) -> str:
    """异步抓取单个 URL（带镜像池）"""
    if mirror_pool is None:
        mirror_pool = config.SUB_MIRRORS()

    sem = _get_async_sem()
    headers = random.choice(config.HEADERS_POOL())
    is_github = "github" in url.lower() or "raw.githubusercontent" in url

    if not is_github:
        async with sem:
            for _ in range(2):
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        return resp.text.strip()
                    elif resp.status_code in (403, 429):
                        await asyncio.sleep(3)
                        continue
                except (httpx.RequestError, httpx.TimeoutException):
                    logging.debug("async_fetch_url failed", exc_info=True)
                    await asyncio.sleep(1)
        return ""

    # GitHub: 镜像池 + 原始URL兜底
    all_urls = []
    for mirror in mirror_pool:
        if mirror:
            mirror_host = mirror.rstrip("/").replace("https://", "").replace("http://", "")
            all_urls.append(url.replace("raw.githubusercontent.com", mirror_host))
    all_urls.append(url)

    async with sem:
        for try_url in all_urls:
            for _ in range(2):
                try:
                    resp = await client.get(try_url, headers=headers)
                    if resp.status_code == 200:
                        text = resp.text.strip()
                        if text.startswith("<!") or text.startswith("<html"):
                            continue
                        if len(text) > 50:
                            return text
                    elif resp.status_code in (403, 429, 503):
                        await asyncio.sleep(random.uniform(2.0, 5.0))
                        continue
                except (httpx.RequestError, httpx.TimeoutException):
                    logging.debug("async_fetch_url failed", exc_info=True)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
    return ""


async def async_fetch_and_parse(client: httpx.AsyncClient, url: str) -> Tuple[Dict, bool]:
    """异步获取并解析单个 URL 的节点"""
    parse_node_fn = config.parse_node()
    ProxyNode_cls = config.ProxyNode()

    if parse_node_fn is None or ProxyNode_cls is None:
        logging.debug("parse_node or ProxyNode not available")
        return {}, False

    local_nodes = {}
    content = await async_fetch_url(client, url)
    if not content:
        return local_nodes, False

    src_weight = source_weight(url)

    if is_yaml_content(content):
        yaml_nodes = parse_yaml_proxies(content)
        for p in yaml_nodes:
            h = ProxyNode_cls.from_dict(p).dedup_key()
            if h not in local_nodes:
                p["_src_weight"] = src_weight
                local_nodes[h] = p
        return local_nodes, True

    if is_base64(content):
        content = decode_b64(content)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = parse_node_fn(line)
        if p:
            h = ProxyNode_cls.from_dict(p).dedup_key()
            if h not in local_nodes:
                p["_src_weight"] = src_weight
                local_nodes[h] = p
    return local_nodes, False


async def async_fetch_nodes(all_urls: List[str], max_nodes: int = 5000) -> Tuple[Dict, int, int, Dict]:
    """异步批量抓取并解析所有节点的入口

    Returns:
        (nodes_dict, yaml_count, txt_count, url_results)
        url_results: {url: (success, node_count, asia_count)}
    """
    sem = asyncio.Semaphore(80)
    client = config.get_async_http_client()

    async def fetch_with_limit(url: str):
        async with sem:
            return await async_fetch_and_parse(client, url)

    logging.debug(f"[WEB] 异步抓取 {len(all_urls)} 个订阅源...")

    # v28.47-fix1: 创建 task 对象，并建立 task→url 映射用于追踪
    task_to_url = {}
    tasks = []
    for url in all_urls:
        task = asyncio.create_task(fetch_with_limit(url))
        tasks.append(task)
        task_to_url[task] = url

    nodes = {}
    yaml_count = 0
    txt_count = 0
    completed = 0
    url_results = {}  # url -> (success, node_count, asia_count)

    pending = set(tasks)
    try:
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                # v28.39: 安全解构，避免未定义变量
                local_nodes = {}
                is_yaml = False
                try:
                    local_nodes, is_yaml = await task
                except (asyncio.CancelledError, ConnectionError, TimeoutError) as e:
                    logging.debug("Fetch task failed: %s", e)
                    local_nodes = {}
                    is_yaml = False
                completed += 1
                url = task_to_url.get(task, "")

                # Track per-URL results and override _src_weight with dynamic weight
                node_count = len(local_nodes)
                asia_count = 0

                # 使用 config 获取动态权重和 is_asia 函数
                if url:
                    dw_fn = config.dynamic_source_weight
                    is_asia_func = config.is_asia
                    if is_asia_func:
                        asia_count = sum(1 for pp in local_nodes.values() if is_asia_func(pp))
                    if dw_fn:
                        for p in local_nodes.values():
                            p["_src_weight"] = dw_fn(url)
                url_results[url] = (node_count > 0, node_count, asia_count)

                for h, p in local_nodes.items():
                    if h not in nodes:
                        nodes[h] = p

                if is_yaml:
                    yaml_count += 1
                else:
                    txt_count += 1

                if completed % 50 == 0:
                    logging.debug(f"   进度: {completed}/{len(all_urls)} | 节点: {len(nodes)}")

                if len(nodes) >= max_nodes:
                    logging.debug(f"   已达上限 {max_nodes}，提前结束")
                    break
            if len(nodes) >= max_nodes:
                break
    finally:
        # 取消剩余未完成的任务
        if pending:
            for task in pending:
                task.cancel()
            # 等待取消完成（忽略 CancelledError）
            await asyncio.gather(*pending, return_exceptions=True)
        # 安全关闭 client
        async_client = config.async_http_client()
        if async_client:
            try:
                await async_client.aclose()
            except (OSError, RuntimeError) as e:
                logging.debug("关闭异步客户端时出错: %s", e)

    return nodes, yaml_count, txt_count, url_results


async def async_fetch_urls(urls: List[str], mirror_pool: List[str] = None) -> Dict[str, str]:
    """异步批量抓取多个 URL

    Returns:
        {url: content}
    """
    if mirror_pool is None:
        mirror_pool = config.SUB_MIRRORS()

    client = config.get_async_http_client()
    # v28.50: 创建 task 对象而非传递 coroutine
    tasks = [asyncio.create_task(async_fetch_url(client, url, mirror_pool)) for url in urls]

    try:
        from tqdm.asyncio import tqdm as async_tqdm
        results = await async_tqdm.gather(*tasks, desc="[WEB] 异步抓取")
    except ImportError:
        results = await asyncio.gather(*tasks)

    return {url: content for url, content in zip(urls, results) if content}
