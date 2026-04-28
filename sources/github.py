# sources/github.py - GitHub Fork 发现模块
# v28.39: 从 crawler.py 解耦

import os
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

# 从 crawler.py 导入需要的全局对象和常量
# 注意：这里通过延迟导入避免循环依赖

# 潜在路径（每个 fork 的可能订阅文件）
POTENTIAL_PATHS = [
    "proxies.yaml",
    "subscription.txt",
    "v2ray.txt",
]


def _get_session():
    """延迟导入 session，避免循环依赖"""
    import sys
    crawler = sys.modules.get('crawler')
    if crawler is None:
        # 如果 crawler 还没加载，动态导入
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
        'GITHUB_TOKEN': getattr(crawler, 'GITHUB_TOKEN', os.getenv('GITHUB_TOKEN', '')),
        'MAX_FORK_REPOS': getattr(crawler, 'MAX_FORK_REPOS', 60),
        'MAX_FORK_URLS': getattr(crawler, 'MAX_FORK_URLS', 1500),
        'MAX_WORKERS': getattr(crawler, 'MAX_WORKERS', 80),
        'GITHUB_BASE_REPOS': getattr(crawler, 'GITHUB_BASE_REPOS', []),
    }


def fetch_forks(base: str, session=None, config=None) -> List[dict]:
    """获取单个 base repo 的 fork 列表"""
    if session is None:
        session = _get_session()
    if config is None:
        config = _get_config()

    url = f"https://api.github.com/repos/{base}/forks?per_page={config['MAX_FORK_REPOS']}&sort=newest"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if config['GITHUB_TOKEN']:
        headers["Authorization"] = f"token {config['GITHUB_TOKEN']}"

    for attempt in range(2):
        try:
            resp = session.get(url, timeout=10, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403:
                reset = int(resp.headers.get("X-RateLimit-Reset", 0))
                if reset and attempt == 0:
                    wait_time = max(reset - int(time.time()), 1)
                    wait_time = min(wait_time, 30)
                    print(f"   ⏳ GitHub API 限流，等待 {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logging.debug("GitHub API rate limited: %s", base)
                return []
            elif resp.status_code == 404:
                return []
        except (requests.RequestException, requests.Timeout):
            logging.debug("GitHub API request failed: %s", url)
    return []


def discover_github_forks() -> List[str]:
    """全面发掘 GitHub Fork 的高质量订阅源 - 并行优化版

    Returns:
        候选订阅 URL 列表
    """
    print("[SEARCH] 动态发现 GitHub Fork...")

    session = _get_session()
    config = _get_config()
    base_repos = config['GITHUB_BASE_REPOS']

    if not base_repos:
        print("   [WARN] GITHUB_BASE_REPOS 为空，跳过 Fork 发现")
        return []

    # 并行获取所有 base repo 的 fork 列表
    all_forks = []
    with ThreadPoolExecutor(max_workers=config['MAX_WORKERS']) as ex:
        futures = {ex.submit(fetch_forks, base, session, config): base for base in base_repos}
        for future in as_completed(futures):
            forks = future.result()
            all_forks.extend(forks)
            if forks:
                print(f"   [PACKAGE] {futures[future]}: {len(forks)} forks")

    print(f"   [STAT] 共获取 {len(all_forks)} 个 fork...")

    # 批量构建所有潜在 URL
    all_urls_to_check = []
    for fork in all_forks:
        if fork.get("full_name") and fork.get("fork"):
            fullname = fork["full_name"]
            branch = fork.get("default_branch", "main")
            for path in POTENTIAL_PATHS:
                raw_url = f"https://raw.githubusercontent.com/{fullname}/{branch}/{path}"
                all_urls_to_check.append(raw_url)

    # 限制总URL数量，避免爬取时间过长
    all_urls_to_check = list(set(all_urls_to_check))
    if len(all_urls_to_check) > config['MAX_FORK_URLS']:
        random.shuffle(all_urls_to_check)
        all_urls_to_check = all_urls_to_check[:config['MAX_FORK_URLS']]

    print(f"   🔗 构建 {len(all_urls_to_check)} 个潜在 URL（跳过验证，直接拉取）...")
    print(f"[OK] GitHub Fork 共发现 {len(all_urls_to_check)} 个候选来源\n")
    return all_urls_to_check
