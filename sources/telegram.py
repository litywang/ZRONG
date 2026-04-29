# sources/telegram.py - Telegram 频道爬虫模块
# v28.53: 重构，使用 sources.config 替代 sys.modules hack

import re
import time
import random
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError
from typing import Dict, List, Optional

from . import config
from .utils import clean_url, is_valid_url, check_subscription_quality

logger = logging.getLogger(__name__)


def get_telegram_pages(channel: str) -> int:
    """获取 Telegram 频道的总页数（兼容新旧两种 HTML 结构）"""
    try:
        session = config.session()
        timeout = config.TIMEOUT()
        url = f"https://t.me/s/{channel}"
        content = session.get(url, timeout=timeout).text

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
        logging.debug(f"[WARN] {channel} 页码获取失败：{str(e)[:50]}")
        return 0


# clean_url, is_valid_url, check_subscription_quality 已移至 utils.py，此处直接导入使用


def crawl_telegram_page(url: str, limits: int = 25) -> Dict[str, dict]:
    """爬取单个 Telegram 页面，提取订阅链接

    Args:
        url: Telegram 页面 URL
        limits: 最大返回链接数

    Returns:
        {url: {"origin": "TELEGRAM"}}
    """
    try:
        limiter = config.limiter()
        session = config.session()
        cfg = config.config()

        limiter.wait(url)
        headers = {
            "User-Agent": random.choice(cfg['USER_AGENT_POOL']),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        content = session.get(url, timeout=cfg['TIMEOUT'], headers=headers).text

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
            logging.debug(f"   [OK] 该页面发现 {len(collections)} 个有效订阅链接")
        else:
            logging.debug(f"   [WARN] 该页面未发现有效订阅链接：{url[:60]}")

        return collections

    except (requests.RequestException, ValueError) as e:
        logging.debug(f"   [FAIL] 爬取异常：{str(e)[:50]}")
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
    max_workers = config.MAX_WORKERS()

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(crawl_single_channel, ch, pages, limits): ch for ch in channels}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                channel_subs, channel, status = future.result()
            except (CancelledError, RuntimeError) as e:
                logger.debug("Channel crawl failed: %s", e)
                channel_subs = {}
                channel = futures[future]
                status = str(e)[:50]

            for link, meta in channel_subs.items():
                if link not in all_subscribes:
                    all_subscribes[link] = meta

            tg_count = len([c for c in all_subscribes.values() if c.get("origin") == "TELEGRAM"])
            logging.debug(f"📄 [{completed}/{len(channels)}] {channel}: {len(channel_subs)} 个 | 总计: {tg_count}")

    return all_subscribes