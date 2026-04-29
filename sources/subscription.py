# sources/subscription.py - 订阅源抓取模块
# v28.39: 从 crawler.py 解耦

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


def _get_http_client():
    """延迟导入同步 HTTP 客户端"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.get_http_client()


def _get_async_http_client():
    """延迟导入异步 HTTP 客户端"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.get_async_http_client()


def _get_config():
    """获取 crawler.py 中的配置常量"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return {
        'HEADERS_POOL': getattr(crawler, 'HEADERS_POOL', [{}]),
        'SUB_MIRRORS': getattr(crawler, 'SUB_MIRRORS', []),
        'TIMEOUT': getattr(crawler, 'TIMEOUT', 12),
        'MAX_FETCH_NODES': getattr(crawler, 'MAX_FETCH_NODES', 5000),
        'FETCH_WORKERS': getattr(crawler, 'FETCH_WORKERS', 150),
    }


def _get_limiter():
    """获取限流器"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.limiter


def _source_weight(url: str) -> int:
    """根据URL特征推断源权重（1-10），国内友好源得分更高"""
    u = url.lower()
    domestic_keywords = [
        "ermaozi", "peasoft", "aiboboxx", "mfuu", "freefq", "kxswa",
        "llywhn", "adiwzx", "changfengoss", "mymysub", "yeahwu",
        "mksshare", "bulianglin", "yiiss", "free18", "shaoyouvip",
        "yonggekkk", "vxiaodong", "wxloststar",
    ]
    for kw in domestic_keywords:
        if kw in u:
            return 8
    aggregator_keywords = ["mahdibland", "epodonios", "barry-far"]
    for kw in aggregator_keywords:
        if kw in u:
            return 5
    if "vless" in u or "hysteria2" in u:
        return 7
    if "trojan" in u:
        return 6
    return 3


# ===== URL 工具函数 =====

def strip_url(u: str) -> str:
    """确保 URL 无空格"""
    if u:
        return u.strip().replace("\n", "").replace(" ", "")
    return ""


def check_url_fast(u: str) -> bool:
    """跳过 HEAD 验证，直接返回 True（零验证直拉策略）"""
    return True


def check_url(u: str) -> bool:
    """跳过 HEAD 验证（零验证直拉策略，统一入口）"""
    return True


def clean_url(url: str) -> str:
    """URL 规范化"""
    if not url:
        return ""
    cleaned = re.sub(r'\s+', '', url)
    if 'github' in cleaned.lower():
        cleaned = cleaned.replace("http://", "https://", 1)
    cleaned = cleaned.rstrip('.,;:!?"\\')
    if len(cleaned) < 15:
        return ""
    from urllib.parse import urlparse
    domain = urlparse(cleaned).netloc
    if not domain or len(domain) < 4:
        return ""
    return cleaned


def is_valid_url(url: str) -> bool:
    """URL 有效性检查"""
    if not url or len(url) < 10:
        return False
    url = url.strip().rstrip('.,;:')
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    invalid_domains = ["t.me", "telegram.org"]
    if any(domain in url for domain in invalid_domains):
        return False
    return True


def check_subscription_quality(url: str) -> bool:
    """订阅质量快速筛查"""
    quality_indicators = [
        "token=", "/subscribe/", "/api/v1/client/",
        ".txt", ".yaml", ".yml", ".json", "/link/"
    ]
    url_lower = url.lower()
    match_count = sum(1 for indicator in quality_indicators if indicator in url_lower)
    return match_count >= 1


# ===== 编码/解码工具 =====

def is_base64(s: str) -> bool:
    """判断是否为 base64 编码"""
    try:
        s = s.strip()
        if len(s) < 10 or not re.match(r'^[A-Za-z0-9+/=]+$', s):
            return False
        base64.b64decode(s + "=" * (-len(s) % 4), validate=True)
        return True
    except (ValueError, base64.binascii.Error):
        logging.debug("is_base64 failed", exc_info=True)
        return False


def decode_b64(c: str) -> str:
    """Base64 解码"""
    try:
        c = c.strip()
        m = len(c) % 4
        if m:
            c += "=" * (4 - m)
        d = base64.b64decode(c).decode("utf-8", errors="ignore")
        return d if "://" in d else c
    except (ValueError, base64.binascii.Error):
        logging.debug("decode_b64 failed", exc_info=True)
        return c


# ===== YAML 解析 =====

def is_yaml_content(content: str) -> bool:
    """判断内容是否为 YAML 订阅源"""
    c_lower = content[:2000].lower()
    return ("proxies:" in c_lower or "proxy:" in c_lower) and ("server:" in c_lower)


def parse_yaml_proxies(content: str) -> List[dict]:
    """解析 YAML 格式的 Clash/Mihomo 订阅，提取 proxies 列表"""
    try:
        data = yaml.safe_load(content)
        if not data or not isinstance(data, dict):
            return []
        proxies = data.get("proxies") or data.get("Proxy") or []
        if not isinstance(proxies, list):
            return []
        results = []
        for p in proxies:
            if not isinstance(p, dict) or not p.get("server"):
                continue
            ptype = (p.get("type") or "").lower()
            if ptype not in ("vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2", "tuic",
                             "wireguard", "shadowtls", "snell", "http", "socks5", "anytls"):
                continue
            try:
                port = int(p.get("port", 0))
                if port <= 0:
                    continue
            except (ValueError, TypeError):
                continue
            original_name = p.get("name", "")
            if not original_name:
                key = f"{p['server']}:{port}:{p.get('uuid', p.get('password', ''))}"
                h = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8].upper()
                ptype_tag = {"vmess": "VM", "vless": "VL", "trojan": "TJ", "ss": "SS", "ssr": "SR",
                             "hysteria": "HY", "hysteria2": "H2", "tuic": "TU", "wireguard": "WG", "shadowtls": "ST"}
                original_name = f"{ptype_tag.get(ptype, 'XX')}-{h}"
            p["name"] = original_name
            results.append(p)
        return results
    except (yaml.YAMLError, TypeError, AttributeError):
        logging.debug("parse_yaml_proxies failed", exc_info=True)
        return []


# ===== 同步抓取 =====

def fetch(url: str) -> str:
    """同步抓取单个 URL（GitHub URL 多镜像池遍历 + HTTP/2 + 重试）"""
    limiter = _get_limiter()
    client = _get_http_client()
    config = _get_config()
    headers = random.choice(config['HEADERS_POOL'])
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
    for mirror in config['SUB_MIRRORS']:
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
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    parse_node = crawler.parse_node
    ProxyNode = crawler.ProxyNode

    local_nodes = {}
    c = fetch(url)
    if not c:
        return local_nodes, False

    src_weight = _source_weight(url)

    if is_yaml_content(c):
        yaml_nodes = parse_yaml_proxies(c)
        for p in yaml_nodes:
            h = ProxyNode.from_dict(p).dedup_key()
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
        p = parse_node(line)
        if p:
            h = ProxyNode.from_dict(p).dedup_key()
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
        mirror_pool = _get_config()['SUB_MIRRORS']

    sem = _get_async_sem()
    headers = random.choice(_get_config()['HEADERS_POOL'])
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
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    parse_node = crawler.parse_node
    ProxyNode = crawler.ProxyNode

    local_nodes = {}
    content = await async_fetch_url(client, url)
    if not content:
        return local_nodes, False

    src_weight = _source_weight(url)

    if is_yaml_content(content):
        yaml_nodes = parse_yaml_proxies(content)
        for p in yaml_nodes:
            h = ProxyNode.from_dict(p).dedup_key()
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
        p = parse_node(line)
        if p:
            h = ProxyNode.from_dict(p).dedup_key()
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
    client = _get_async_http_client()

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

    # Access crawler module for dynamic weight and is_asia (available since main() runs from crawler.py)
    import sys
    crawler = sys.modules.get('crawler')

    # v28.46-fix1: 先收集所有结果再关闭 client，避免 task 访问已关闭 client
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
                if url and crawler:
                    dw = getattr(crawler, '_dynamic_source_weight', None)
                    is_asia_fn = getattr(crawler, 'is_asia', None)
                    if is_asia_fn:
                        asia_count = sum(1 for pp in local_nodes.values() if is_asia_fn(pp))
                    if dw:
                        for p in local_nodes.values():
                            p["_src_weight"] = dw(url)
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
        if crawler:
            async_client = getattr(crawler, '_async_http_client', None)
            if async_client:
                try:
                    await async_client.aclose()
                except (OSError, RuntimeError) as e:
                    logging.debug("关闭异步客户端时出错: %s", e)
                crawler._async_http_client = None

    return nodes, yaml_count, txt_count, url_results


async def async_fetch_urls(urls: List[str], mirror_pool: List[str] = None) -> Dict[str, str]:
    """异步批量抓取多个 URL

    Returns:
        {url: content}
    """
    if mirror_pool is None:
        mirror_pool = _get_config()['SUB_MIRRORS']

    client = _get_async_http_client()
    # v28.50: 创建 task 对象而非传递 coroutine
    tasks = [asyncio.create_task(async_fetch_url(client, url, mirror_pool)) for url in urls]

    try:
        from tqdm.asyncio import tqdm as async_tqdm
        results = await async_tqdm.gather(*tasks, desc="[WEB] 异步抓取")
    except ImportError:
        results = await asyncio.gather(*tasks)

    return {url: content for url, content in zip(urls, results) if content}
