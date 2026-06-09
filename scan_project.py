#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系统性深度扫描 ZRONG 项目"""

import os
import sys
import ast
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
issues = []

def log(section, msg):
    """记录问题"""
    issues.append("[{}] {}".format(section, msg))
    print("[{}] {}".format(section, msg))

def check_syntax(filepath):
    """检查 Python 文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, "Line {}: {}".format(e.lineno, e.msg)
    except Exception as e:
        return False, str(e)

def check_file_imports(filepath):
    """检查文件导入"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(('import', alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(('from', module, alias.name, node.lineno))
        
        return imports
    except Exception as e:
        return None

def scan_project():
    """扫描整个项目"""
    print("=" * 60)
    print("ZRONG Project Deep Scan")
    print("=" * 60)
    
    # 1. 收集所有 Python 文件
    py_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过隐藏目录和缓存
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                py_files.append(Path(root) / f)
    
    print("\n[1/5] Found {} Python files".format(len(py_files)))
    
    # 2. 语法检查
    print("\n[2/5] Syntax check...")
    syntax_errors = 0
    for fpath in py_files:
        ok, err = check_syntax(fpath)
        if not ok:
            log("SYNTAX", "{}: {}".format(fpath, err))
            syntax_errors += 1
    if syntax_errors == 0:
        print("  [OK] All files syntax OK")
    else:
        print("  [FAIL] {} syntax errors".format(syntax_errors))
    
    # 3. 导入检查
    print("\n[3/5] Import chain check...")
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        import crawler
        print("  [OK] crawler module imported")
    except Exception as e:
        log("IMPORT", "crawler: {}".format(e))
        traceback.print_exc()
    
    # 4. 检查重复导入
    print("\n[4/5] Checking duplicate imports...")
    dup_count = 0
    for fpath in py_files:
        if fpath.name.startswith('_'):
            continue
        imports = check_file_imports(fpath)
        if imports is None:
            continue
        
        # 检查重复导入
        seen = {}
        for imp in imports:
            key = (imp[0], imp[1]) if imp[0] == 'import' else (imp[0], imp[1], imp[2])
            if key in seen:
                log("DUP_IMPORT", "{}:{} duplicate {}".format(fpath, imp[-1], key))
                dup_count += 1
            seen[key] = imp[-1]
    
    if dup_count == 0:
        print("  [OK] No duplicate imports")
    else:
        print("  [WARN] {} duplicate imports found".format(dup_count))
    
    # 5. 尝试运行主程序（带超时）
    print("\n[5/5] Try running main program (10s timeout)...")
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, 'crawler.py'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8'
        )
        if result.returncode == 0:
            print("  [OK] Main program can start")
        else:
            log("RUN_FAIL", "returncode={}".format(result.returncode))
            if result.stderr:
                log("STDERR", result.stderr[:500])
    except subprocess.TimeoutExpired:
        print("  [TIMEOUT] Main program timeout (may be blocking)")
    except Exception as e:
        log("RUN_ERROR", str(e))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("Scan complete, found {} issues".format(len(issues)))
    print("=" * 60)
    
    if issues:
        print("\nIssue list:")
        for i, issue in enumerate(issues[:50], 1):
            print("{}. {}".format(i, issue))
        if len(issues) > 50:
            print("... {} more issues".format(len(issues) - 50))
    
    return len(issues) == 0

if __name__ == '__main__':
    success = scan_project()
    sys.exit(0 if success else 1)
