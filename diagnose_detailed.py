#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细诊断主程序阻塞点
使用 faulthandler 捕获挂起时的堆栈跟踪
"""

import sys
import os
import time
import logging
import subprocess
import faulthandler

# 启用 faulthandler，在崩溃时打印堆栈
faulthandler.enable()
# Windows 不支持 faulthandler.register (SIGUSR1)
# 但 faulthandler.enable() 仍然可以在崩溃时打印堆栈

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    force=True
)

print("[START] 开始详细诊断主程序阻塞点...")
print("=" * 80)

try:
    # 步骤1: 导入模块
    print("\n[1/5] 导入模块...")
    import crawler
    print("[OK] crawler 导入成功")
    
    # 步骤2: 导入 main 函数
    print("\n[2/5] 导入 main 函数...")
    from core.main_flow import main
    print("[OK] main() 导入成功")
    
    # 步骤3: 检查关键配置
    print("\n[3/5] 检查关键配置...")
    try:
        from core.config import check_network_baseline
        print(f"  check_network_baseline available: {check_network_baseline is not None}")
    except ImportError:
        print("  check_network_baseline not found in core.config")
    print("[OK] 配置检查完成")
    
    # 步骤4: 尝试调用 collect_nodes() (单独测试采集阶段)
    print("\n[4/5] 尝试调用 collect_nodes() (单独测试采集阶段)...")
    print("[WARN] 如果这里卡住，说明 collect_nodes() 内部有阻塞")
    print("[INFO] 请等待 20 秒...")
    
    # 使用 subprocess 运行，避免阻塞当前进程
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from core.collector import collect_nodes
from sources.config import init_config
init_config()
nodes, stats = collect_nodes(use_async=False, max_fetch_nodes=100, fetch_workers=10)
print(f'OK: collected {len(nodes)} nodes')
print(f'Stats: {stats}')
"""],
        capture_output=True,
        text=True,
        timeout=20  # 20秒超时
    )
    
    print("[OK] collect_nodes() 在 20 秒内完成 (或超时)")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr[:1000]}")
    
    # 步骤5: 尝试调用 main() (但如果 collect_nodes 成功，可能 main 也会成功)
    print("\n[5/5] 尝试调用 main() (30s 后超时)...")
    print("[WARN] 如果这里卡住，说明 main() 内部有阻塞（可能在测速阶段）")
    print("[INFO] 请等待 30 秒...")
    
    result = subprocess.run(
        [sys.executable, "-c", "from core.main_flow import main; main()"],
        capture_output=True,
        text=True,
        timeout=30  # 30秒超时
    )
    
    print("[OK] main() 在 30 秒内完成 (或超时)")
    print(f"STDOUT:\n{result.stdout[:500]}")
    print(f"STDERR:\n{result.stderr[:500]}")
    
except subprocess.TimeoutExpired:
    print("\n[FAIL] 调用超时，存在阻塞")
    print("[INFO] 阻塞位置：")
    print("  1. collect_nodes() - 如果在步骤4超时")
    print("  2. main() - 如果在步骤5超时")
    print("\n[INFO] 可能原因：")
    print("  - 网络请求没有超时设置")
    print("  - 线程池死锁")
    print("  - 无限循环")
    print("  - Clash 进程启动失败")
    
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
print("[END] 详细诊断完成")

# 如果挂起，按 Ctrl+C 或发送 SIGUSR1 (Unix) 查看堆栈
print("\n[TIP] 如果程序挂起，在另一个终端运行：")
print(f"  kill -SIGUSR1 {os.getpid()}  # Unix only")
print("  或者在 Windows 上按 Ctrl+Break 查看堆栈")
