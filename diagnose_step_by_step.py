#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐函数诊断阻塞点
单独测试 collect_nodes() 中的每个阶段，找出真正阻塞的函数调用
"""

import sys
import os
import time
import logging
import subprocess

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    force=True
)

print("[START] 逐函数诊断阻塞点...")
print("=" * 80)

try:
    # 步骤1: 导入模块
    print("\n[1/6] 导入模块...")
    import crawler
    from sources.config import init_config
    init_config()
    print("[OK] 模块导入并初始化成功")
    
    # 步骤2: 测试 crawl_telegram_channels()
    print("\n[2/6] 测试 Telegram 爬取（10秒超时）...")
    from sources import crawl_telegram_channels, TELEGRAM_CHANNELS, strip_url
    
    def test_telegram():
        tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS, pages=1, limits=10)
        tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
        return len(tg_urls)
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from sources.config import init_config
init_config()
from sources import crawl_telegram_channels, TELEGRAM_CHANNELS, strip_url
tg_subs = crawl_telegram_channels(TELEGRAM_CHANNELS[:2], pages=1, limits=5)
tg_urls = list(set([strip_url(u) for u in tg_subs.keys()]))
print(f'OK: {len(tg_urls)} Telegram URLs')
"""],
            capture_output=True,
            text=True,
            timeout=10  # 10秒超时
        )
        print(f"[OK] Telegram 爬取在 10 秒内完成")
        print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        print(f"[FAIL] Telegram 爬取超过 10 秒，存在阻塞")
        print(f"  [INFO] 阻塞位置：crawl_telegram_channels()")
    
    # 步骤3: 测试 discover_github_forks()
    print("\n[3/6] 测试 GitHub Forks 发现（15秒超时）...")
    from sources import discover_github_forks
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from sources.config import init_config
init_config()
from sources import discover_github_forks
fork_urls = discover_github_forks()
print(f'OK: {len(fork_urls)} fork URLs')
"""],
            capture_output=True,
            text=True,
            timeout=15  # 15秒超时
        )
        print(f"[OK] GitHub Forks 发现在 15 秒内完成")
        print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        print(f"[FAIL] GitHub Forks 发现超过 15 秒，存在阻塞")
        print(f"  [INFO] 阻塞位置：discover_github_forks()")
    
    # 步骤4: 测试单个 fetch_and_parse() (使用一个已知可用的 URL)
    print("\n[4/6] 测试单个节点抓取（10秒超时）...")
    test_url = "https://raw.githubusercontent.com/Loyalsoldier/v2ray-rules-dat/release/proxies.txt"
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '.')
from sources.config import init_config
init_config()
from sources.subscription import fetch_and_parse
nodes, is_yaml = fetch_and_parse('{test_url}')
print(f'OK: fetched {{len(nodes)}} nodes')
"""],
            capture_output=True,
            text=True,
            timeout=10  # 10秒超时
        )
        print(f"[OK] 单个节点抓取在 10 秒内完成")
        print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        print(f"[FAIL] 单个节点抓取超过 10 秒，存在阻塞")
        print(f"  [INFO] 阻塞位置：fetch_and_parse()")
        print(f"  [INFO] 可能原因：网络请求没有超时设置，或目标服务器无响应")
    
    # 步骤5: 测试 collect_nodes() (整体，30秒超时)
    print("\n[5/6] 测试 collect_nodes() 整体（30秒超时）...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from sources.config import init_config
init_config()
from core.collector import collect_nodes
nodes, stats = collect_nodes(use_async=False, max_fetch_nodes=50, fetch_workers=5)
print(f'OK: collected {len(nodes)} nodes')
print(f'Stats: {stats}')
"""],
            capture_output=True,
            text=True,
            timeout=30  # 30秒超时
        )
        print(f"[OK] collect_nodes() 在 30 秒内完成")
        print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print(f"[FAIL] collect_nodes() 超过 30 秒，存在阻塞")
        print(f"  [INFO] 阻塞可能在：")
        print(f"    1. ThreadPoolExecutor 中的某个 fetch_and_parse() 调用")
        print(f"    2. 某个网络请求没有正确超时")
    
    # 步骤6: 建议修复方案
    print("\n[6/6] 建议修复方案...")
    print("[INFO] 如果 fetch_and_parse() 阻塞：")
    print("  1. 检查 sources/subscription.py 中的 fetch() 函数")
    print("  2. 确保 httpx client 有正确的超时设置")
    print("  3. 考虑添加全局超时（比如 10 秒）给每个 fetch_and_parse() 调用")
    print("\n[INFO] 如果 ThreadPoolExecutor 阻塞：")
    print("  1. 使用 as_completed() 的 timeout 参数")
    print("  2. 或使用 concurrent.futures.wait() 替代 as_completed()")
    
except ImportError as e:
    print(f"\n[FAIL] 导入错误: {e}")
    import traceback
    traceback.print_exc()
    
except Exception as e:
    print(f"\n[FAIL] 其他错误: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    pass
    
print("\n" + "=" * 80)
print("[END] 逐函数诊断完成")
