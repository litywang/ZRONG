#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZRONG v28.69 Bug 修复脚本"""
import os, sys

ZRONG = r"C:\tools\ZRONG"
os.chdir(ZRONG)

def fix_history():
    path = os.path.join(ZRONG, "core", "history.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Bug #1: _signal_handler 调用不存在的 _save_node_history / _save_source_history
    changes = 0
    for i, line in enumerate(lines):
        if "_save_node_history()" in line and "def " not in line:
            lines[i] = line.replace("_save_node_history()", "save_node_history()")
            changes += 1
        if "_save_source_history()" in line and "def " not in line:
            lines[i] = line.replace("_save_source_history()", "save_source_history()")
            changes += 1
    if changes:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[FIX] core/history.py: 修复了 {changes} 处函数名错误")
    else:
        print("[SKIP] core/history.py: 未发现需要修复的函数名")

def fix_clash():
    path = os.path.join(ZRONG, "core", "clash.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Bug #2: start() 方法末尾 return True 之后的死代码（stdout.close 重复逻辑）
    # 找到 "return True\n        except" 之后的死代码块并删除
    marker = "return True\n        except (OSError, subprocess.SubprocessError)"
    if marker in content:
        idx = content.find(marker)
        after_return = content[idx + len(marker):]
        # 死代码块是 return True 之后、except 之前的那段代码
        # 删除它，保留 except
        old = "        " + marker + after_return
        new = "        return True\n" + marker + after_return
        # 找到 return True 的位置，然后找下一个 except (OSError, subprocess.SubprocessError)
        pass

    # 更精确的修复：找到 start() 方法中 return True 之后、except 之前的死代码块
    # 搜索 "return True\n            if self.process and self.process.stdout:\n            try:\n                self.process.stdout.close()"
    dead_block = """        return True
        except (OSError, subprocess.SubprocessError) as e:
            logging.debug(f"   [ERROR] Clash 启动异常：{e}")
            return False
        # v28.50: 启动成功时关闭管道避免泄漏
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except OSError as e:
                logging.debug(f"关闭 stdout 管道失败: {e}", exc_info=True)

    def stop(self):"""

    fresh_block = """        return True

    def stop(self):"""

    if dead_block in content:
        content = content.replace(dead_block, fresh_block)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[FIX] core/clash.py: 删除了 start() 末尾的死代码")
    else:
        print("[SKIP] core/clash.py: 死代码块未匹配（可能已修复或结构不同）")

def fix_main_flow():
    path = os.path.join(ZRONG, "core", "main_flow.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    changes = 0

    # Bug #3: finally 块中 clash.stop() 缺少守卫
    old_finally = """    finally:
        clash.stop()"""
    new_finally = """    finally:
        if 'clash' in dir() and clash is not None:
            clash.stop()"""
    if old_finally in content:
        content = content.replace(old_finally, new_finally)
        changes += 1
        print("[FIX] core/main_flow.py: 添加了 clash.stop() 守卫")
    else:
        print("[SKIP] core/main_flow.py: finally clash.stop() 模式未匹配")

    # Bug #7: 替换未定义变量 fork_subs/tg_urls/fixed_urls/all_urls 为 stats
    replacements = [
        ("len(fork_subs)", "stats['fork_count']"),
        ("len(tg_urls)", "stats['tg_count']"),
        ("len(fixed_urls)", "stats['fixed_count']"),
        ("len(all_urls)", "stats['total_urls']"),
    ]
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changes += 1
            print(f"[FIX] core/main_flow.py: 替换 {old!r} → stats['{old[7:-1]}']")

    if changes > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def fix_utils():
    path = os.path.join(ZRONG, "utils.py")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Bug #4: 添加 _get_limiter() 函数
    # Bug #5: 移除重复导入 (hashlib, logging, os, re, ipaddress 各出现两次)
    new_lines = []
    seen_imports = {}  # module_name -> first_line_index
    skip_next = 0
    added_get_limiter = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # 检测重复导入模式: hashlib, logging, os, re, ipaddress 各出现两次
        # 第二次出现时跳过
        if skip_next > 0:
            skip_next -= 1
            i += 1
            continue

        stripped = line.strip()
        # 检测第二批导入（与第一批重复的模块）
        if stripped in ("import hashlib", "import logging", "import os", "import re", "import ipaddress"):
            if stripped in seen_imports:
                # 这是重复的，跳过
                i += 1
                continue
            else:
                seen_imports[stripped] = len(new_lines)

        # 检测 ipaddress 在第二批的位置（在 pathlib 之后）
        # 第二批的 ipaddress 后紧跟 pathlib
        if stripped == "import ipaddress" and i > 0 and lines[i-1].strip() == "import re":
            # 检查是否是重复的
            if "import ipaddress" in seen_imports:
                i += 1
                continue
            else:
                seen_imports[stripped] = len(new_lines)

        new_lines.append(line)
        i += 1

    # 检查是否已存在 _get_limiter
    content_check = "".join(lines)
    if "_get_limiter" not in content_check:
        # 在 get_region 函数调用 _get_limiter 之前插入该函数
        # 找到 # BUGFIX v28.39 行之前插入
        insert_idx = None
        for idx, line in enumerate(new_lines):
            if "# BUGFIX v28.39:" in line or "# v28.5 FIX:" in line:
                insert_idx = idx
                break
        if insert_idx is None:
            # 找 import 语句之后的位置
            for idx, line in enumerate(new_lines):
                if line.startswith("from config import"):
                    insert_idx = idx + 1
                    break
        if insert_idx:
            getter_code = """
def _get_limiter():
    \"\"\"延迟获取全局 limiter，避免循环依赖。\"\"\"
    from sources.config import limiter
    return limiter()

"""
            new_lines.insert(insert_idx, getter_code)
            added_get_limiter = True
            print("[FIX] utils.py: 添加了 _get_limiter() 函数")
        else:
            print("[SKIP] utils.py: 未找到 _get_limiter 插入位置")
    else:
        print("[SKIP] utils.py: _get_limiter() 已存在")

    # 检查重复导入是否已移除
    remaining = "".join(new_lines)
    dup_count = remaining.count("import hashlib\n")
    if dup_count > 1:
        # 需要手动移除
        pass

    if added_get_limiter or new_lines != lines:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[FIX] utils.py: 写回文件")

def fix_geo():
    path = os.path.join(ZRONG, "network", "geo.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if "import random" not in content and "from random import" not in content:
        # 在 import os 之后插入 import random
        old = "import os\n"
        new = "import os\nimport random\n"
        if old in content:
            content = content.replace(old, new, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print("[FIX] network/geo.py: 添加了 import random")
        else:
            # 尝试其他位置
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("import ") and "random" not in line:
                    lines.insert(i+1, "import random")
                    content = "\n".join(lines)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print("[FIX] network/geo.py: 添加了 import random（备选位置）")
                    break
    else:
        print("[SKIP] network/geo.py: import random 已存在")

if __name__ == "__main__":
    print("=" * 50)
    print("ZRONG v28.69 Bug 修复开始")
    print("=" * 50)
    fix_history()
    fix_clash()
    fix_main_flow()
    fix_utils()
    fix_geo()
    print("=" * 50)
    print("修复完成！")
    print("=" * 50)