# sources/__init__.py - 源抓取包
# 包含 GitHub Fork、Telegram 频道、固定订阅源的抓取逻辑
# v28.35: 从 crawler.py 解耦，模块化架构

from .github import discover_github_forks
from .telegram import crawl_telegram_channels, get_telegram_pages, crawl_telegram_page, crawl_single_channel
from .subscription import (
    fetch, fetch_and_parse, async_fetch_and_parse, async_fetch_nodes,
    async_fetch_url, async_fetch_urls,
    check_subscription_quality, is_valid_url, clean_url,
    is_base64, decode_b64, is_yaml_content, parse_yaml_proxies,
    strip_url, check_url, check_url_fast
)

__all__ = [
    # GitHub
    "discover_github_forks",
    # Telegram
    "crawl_telegram_channels", "get_telegram_pages", "crawl_telegram_page", "crawl_single_channel",
    # Subscription
    "fetch", "fetch_and_parse", "async_fetch_and_parse", "async_fetch_nodes",
    "async_fetch_url", "async_fetch_urls",
    "check_subscription_quality", "is_valid_url", "clean_url",
    "is_base64", "decode_b64", "is_yaml_content", "parse_yaml_proxies",
    "strip_url", "check_url", "check_url_fast",
]
