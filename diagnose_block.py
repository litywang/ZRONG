#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断主程序阻塞点
逐步运行 main()，在每个关键步骤打印日志，找出阻塞位置
"""

import sys
import os
import time
import logging
import subprocess
import signal

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

print("[START] 开始诊断主程序阻塞点...")
print("=" * 80)

try:
    # 步骤1: 导入模块
    print("\n[1/10] 导入 crawler 模块...")
    import crawler
    print("[OK] crawler 导入成功")
    
    # 步骤2: 导入 main 函数
    print("\n[2/10] 导入 main 函数...")
    from core.main_flow import main
    print("[OK] main() 导入成功")
    
    # 步骤3: 检查环境变量
    print("\n[3/10] 检查环境变量...")
    env_vars = ["TIMEOUT", "MAX_FETCH_NODES", "MAX_TCP_TEST_NODES", "MAX_PROXY_TEST_NODES", "MAX_FINAL_NODES"]
    for var in env_vars:
        val = os.getenv(var, "(未设置)")
        print(f"  {var} = {val}")
    print("[OK] 环境变量检查完成")
    
    # 步骤4: 尝试调用 main() (但设置极短超时)
    print("\n[4/10] 尝试调用 main() (15s 后超时)...")
    print("[WARN] 如果这里卡住，说明 main() 内部有阻塞")
    print("[INFO] 请等待 15 秒...")
    
    # 使用 subprocess 运行，避免阻塞当前进程
    result = subprocess.run(
        [sys.executable, "-c", "from core.main_flow import main; main()"],
        capture_output=True,
        text=True,
        timeout=15  # 15秒超时
    )
    
    print("[OK] main() 在 15 秒内完成 (或超时)")
    print(f"STDOUT: {result.stdout[:500]}")
    print(f"STDERR: {result.stderr[:500]}")
    
except subprocess.TimeoutExpired:
    print("\n[FAIL] main() 超过 15 秒未完成，存在阻塞")
    print("[INFO] 阻塞可能位置：")
    print("  1. collect_nodes() - 节点采集（网络请求）")
    print("  2. test_tcp_node() - TCP 测试")
    print("  3. clash.start() - Clash 启动")
    print("  4. test_one() - 真实测速")
    
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
print("[END] 诊断完成")
