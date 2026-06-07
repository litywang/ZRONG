#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全项目 .py 文件语法检查"""

import os, py_compile

ROOT = r"C:\tools\ZRONG"
errors = []
checked = 0

for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".github")]
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            checked += 1
            try:
                py_compile.compile(fp, doraise=True)
            except py_compile.PyCompileError as e:
                rel = os.path.relpath(fp, ROOT)
                errors.append(rel)
                print(f"  FAIL: {rel}")
                print(f"        {e.msg}")

print(f"\n检查完成：{checked} 个文件，{len(errors)} 个错误")
if errors:
    print("错误文件：")
    for e in errors:
        print(f"  - {e}")
else:
    print("全部语法检查 PASS")
