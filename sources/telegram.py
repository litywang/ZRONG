# sources/telegram.py - Telegram 频道爬虫模块
# v28.39: 从 crawler.py 解耦

import re
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional


def _get_session():
    """延迟导入 session，避免循环依赖"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.session


def _get_config():
    """获取 crawler.py 中的配置常量"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return {
        'TIMEOUT': getattr(crawler, 'TIMEOUT', 12),
        'MAX_WORKERS': getattr(crawler, 'MAX_WORKERS', 80),
        'USER_AGENT_POOL': getattr(crawler, 'USER_AGENT_POOL', [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ]),
    }


def _get_limiter():
    """获取限流器"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        import importlib
        crawler = importlib.import_module('crawler')
    return crawler.limiter


def get_telegram_pages(channel: str) -> int:
    """获取 Telegram 频道的总页数（兼容新旧两种 HTML 结构）"""
    try:
        session = _get_session()
        config = _get_config()
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=config['TIMEOUT']).text

        # 多种格式兼容
        patterns = [
            rf'<meta\s+content="/s/{channel}\?before=(\d+)">?',
            rf'<link[^>]*href=["\']?/s/{channel}/?\??before=(\d+)["\']?[^>]*>',
            rf'/s/{channel}[^"]*before=(\d+)',
        ]

        for pattern in patterns:
            groups = re.findall(pattern, content, re.IGNORECASE)
            if groups and groups[0].isdigit():
                return int(groups[0])

        # 降级策略：尝试访问频道主页判断是否存在
        resp = session.get(f"https://t.me/{channel}", timeout=10)
        if resp.status_code == 200 and channel in resp.url:
            return 1  # 至少有一页

        return 0
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ {channel} 页码获取失败：{str(e)[:50]}")
        return 0


def clean_url(url: str) -> str:
    """URL 规范化（比 wzdnzd 更全面）"""
    if not url:
        return ""

    # 移除所有不可见字符和换行符
    cleaned = re.sub(r'\s+', '', url)

    # 统一协议为 https（仅对 github 域名，其他保持原样）
    if 'github' in cleaned.lower():
        cleaned = cleaned.replace("http://", "https://", 1)

    # 去除尾部标点
    cleaned = cleaned.rstrip('.,;:!?"\\')

    # 长度检查
    if len(cleaned) < 15:
        return ""

    # 域名长度检查
    from urllib.parse import urlparse
    domain = urlparse(cleaned).netloc
    if not domain or len(domain) < 4:
        return ""

    return cleaned


def is_valid_url(url: str) -> bool:
    """URL 有效性检查（核心优化）"""
    if not url or len(url) < 10:
        return False

    url = url.strip().rstrip('.,;:')

    # 协议检查
    if not (url.startswith("http://") or url.startswith("https://")):
        return False

    # 排除无效域名
    invalid_domains = ["t.me", "telegram.org"]
    if any(domain in url for domain in invalid_domains):
        return False

    return True


def check_subscription_quality(url: str) -> bool:
    """订阅质量快速筛查（借鉴 wzdnzd）"""
    quality_indicators = [
        "token=",
        "/subscribe/",
        "/api/v1/client/",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        "/link/"
    ]

    url_lower = url.lower()
    match_count = sum(1 for indicator in quality_indicators if indicator in url_lower)
    return match_count >= 1


def crawl_telegram_page(url: str, limits: int = 25) -> Dict[str, dict]:
    """爬取单个 Telegram 页面，提取订阅链接

    Args:
        url: Telegram 页面 URL
        limits: 最大返回链接数

    Returns:
        {url: {"origin": "TELEGRAM"}}
    """
    try:
        limiter = _get_limiter()
        session = _get_session()
        config = _get_config()

        limiter.wait(url)
        headers = {
            "User-Agent": random.choice(config['USER_AGENT_POOL']),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        content = session.get(url, timeout=config['TIMEOUT'], headers=headers).text

        if not content or len(content) < 100:
            return {}

        collections = {}

        # 多级正则匹配（完整移植 wzdnzd）
        patterns = [
            # 模式 1: 标准订阅链接
            r'https?://[a-zA-Z0-9\u4e00-\u9fa5\-]+\.[a-zA-Z0-9\u4e00-\u9fa5\-]+'
            r'(?::\d+)?(?:/.*)?(?:sub|subscribe|token)[^\s<>]*',

            # 模式 2: GitHub Raw 链接
            r'https?://raw\.githubusercontent\.com/[a-zA-Z0-9\-]+'
            r'/[a-zA-Z0-9\-]+/[a-zA-Z0-9\-]+/(.*\.txt|.*\.yaml|.*\.yml)',

            # 模式 3: 通用域名 + 路径
            r'https?://(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z0-9\-]+/'
            r'(?:(?:sub|subscribe)/|link/[a-zA-Z0-9]+|api/v[0-9]/client/subscribe)',
        ]

        all_links = []
        for pattern in patterns:
            all_links.extend(re.findall(pattern, content))

        # 去重和质量过滤
        processed_urls = set()
        valid_links = []

        for link in all_links[:limits * 2]:
            link = clean_url(link)
            if not link or not is_valid_url(link):
                continue
            if link in processed_urls:
                continue
            processed_urls.add(link)
            if check_subscription_quality(link):
                valid_links.append(link)

        for link in valid_links[:limits]:
            collections[link] = {"origin": "TELEGRAM"}

        if collections:
            print(f"   ✅ 该页面发现 {len(collections)} 个有效订阅链接")
        else:
            print(f"   ⚠️ 该页面未发现有效订阅链接：{url[:60]}")

        return collections

    except (requests.RequestException, ValueError) as e:
        print(f"   ❌ 爬取异常：{str(e)[:50]}")
        return {}


def crawl_single_channel(channel: str, pages: int = 2, limits: int = 20) -> tuple:
    """单个频道爬取（用于并行）

    Returns:
        (channel_subs, channel, status)
    """
    channel_subs = {}
    try:
        count = get_telegram_pages(channel)
        if count == 0:
            return channel_subs, channel, "no_pages"

        page_arrays = range(count, -1, -100)
        page_num = min(pages, len(page_arrays))

        for i, before in enumerate(page_arrays[:page_num]):
            url = f"https://t.me/s/{channel}?before={before}"
            result = crawl_telegram_page(url, limits=limits)

            for link, meta in result.items():
                if link not in channel_subs:
                    channel_subs[link] = meta

            time.sleep(random.uniform(0.1, 0.3))

        return channel_subs, channel, "ok"
    except (requests.RequestException, ValueError) as e:
        # v28.39: 确保 channel_subs 已定义
        if 'channel_subs' not in locals():
            channel_subs = {}
        return channel_subs, channel, str(e)[:50]


def crawl_telegram_channels(channels: List[str], pages: int = 2, limits: int = 20) -> Dict[str, dict]:
    """批量爬取 Telegram 频道 - 并行版本

    Args:
        channels: 频道名列表
        pages: 每个频道爬取页数
        limits: 每页最大链接数

    Returns:
        {url: {"origin": "TELEGRAM"}}
    """
    all_subscribes = {}
    config = _get_config()

    with ThreadPoolExecutor(max_workers=config['MAX_WORKERS']) as ex:
        futures = {ex.submit(crawl_single_channel, ch, pages, limits): ch for ch in channels}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            # v28.39: 安全解构，避免未定义变量
            try:
                channel_subs, channel, status = future.result()
            except (concurrent.futures.CancelledError, RuntimeError) as e:
                logger.debug("Channel crawl failed: %s", e)
                channel_subs = {}
                channel = futures[future]
                status = str(e)[:50]

            for link, meta in channel_subs.items():
                if link not in all_subscribes:
                    all_subscribes[link] = meta

            tg_count = len([c for c in all_subscribes.values() if c.get("origin") == "TELEGRAM"])
            print(f"📄 [{completed}/{len(channels)}] {channel}: {len(channel_subs)} 个 | 总计: {tg_count}")

    return all_subscribes
