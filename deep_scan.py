#!/usr/bin/env python3
"""
ZRONG 深度扫描器 - 逐行扫描BUG和潜在问题
扫描一个 → 修复一个 → 验证一个 → 提交一个
如遇错回滚，继续扫描
"""
import ast
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

PROJECT_ROOT = Path("C:/tools/ZRONG")
PYTHON_FILES = list(PROJECT_ROOT.rglob("*.py"))
# 排除已知的非项目文件和已删除文件
EXCLUDE_PATTERNS = [
    "__pycache__", ".git", ".github", "node_modules",
    "deep_scan.py",  # 扫描器自身
]

def should_scan(path: Path) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if pat in str(path):
            return False
    return True

PYTHON_FILES = [p for p in PYTHON_FILES if should_scan(p)]

print(f"[*] 扫描目标: {len(PYTHON_FILES)} 个Python文件")
for p in PYTHON_FILES[:10]:
    print(f"    {p.relative_to(PROJECT_ROOT)}")
if len(PYTHON_FILES) > 10:
    print(f"    ... 等共 {len(PYTHON_FILES)} 个")

# ==================== 扫描规则 ====================

class Issue:
    def __init__(self, file: Path, line: int, col: int, rule: str, msg: str, severity: str = "warning"):
        self.file = file
        self.line = line
        self.col = col
        self.rule = rule
        self.msg = msg
        self.severity = severity  # error, warning, info
    
    def __repr__(self):
        return f"[{self.severity.upper()}] {self.file.name}:{self.line}:{self.col} {self.rule}: {self.msg}"

def scan_bare_except(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描 bare except"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                # 检查是否是 except: （无类型）
                issues.append(Issue(file, node.lineno, node.col_offset, "BARE_EXCEPT", 
                    "Bare except 会捕获所有异常包括 KeyboardInterrupt 和 SystemExit", "error"))
            elif isinstance(node.type, ast.Tuple) and len(node.type.elts) == 0:
                issues.append(Issue(file, node.lineno, node.col_offset, "BARE_EXCEPT",
                    "Empty except tuple", "error"))
    return issues

def scan_broad_except(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描过于宽泛的 except Exception / except BaseException"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                type_str = ast.unparse(node.type) if hasattr(ast, 'unparse') else "Exception"
                if type_str in ("Exception", "BaseException"):
                    # 检查 except 块内容，如果只是简单记录日志，警告；如果吞掉异常，错误
                    body = ast.unparse(node.body) if hasattr(ast, 'unparse') else ""
                    if 'raise' not in body and 'return' not in body:
                        issues.append(Issue(file, node.lineno, node.col_offset, "BROAD_EXCEPT",
                            f"except {type_str} 吞掉异常未重新抛出", "warning"))
    return issues

def scan_empty_except(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描空的 except 块或只有 pass 的 except"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 0:
                issues.append(Issue(file, node.lineno, node.col_offset, "EMPTY_EXCEPT",
                    "空的 except 块", "error"))
            elif len(body) == 1 and isinstance(body[0], ast.Pass):
                issues.append(Issue(file, node.lineno, node.col_offset, "EMPTY_EXCEPT",
                    "except 块只有 pass，异常被静默吞掉", "error"))
            elif len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                # 只有一个字符串常量，相当于 pass
                issues.append(Issue(file, node.lineno, node.col_offset, "EMPTY_EXCEPT",
                    "except 块只有注释/字符串，异常被静默吞掉", "warning"))
    return issues

def scan_unclosed_resources(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描未使用 with 语句管理的资源（文件、socket等）"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = ast.unparse(node.func) if hasattr(ast, 'unparse') else ""
            if func in ("open", "socket.socket", "socket.create_connection"):
                # 检查是否在 with 语句中
                parent = getattr(node, 'parent', None)
                # 简单检查：如果不在 with 的 items 中，警告
                # AST 不直接支持 parent 遍历，用行号匹配
                issues.append(Issue(file, node.lineno, node.col_offset, "UNCLOSED_RESOURCE",
                    f"{func}() 调用可能未正确关闭，建议使用 with 语句", "warning"))
    return issues

def scan_mutable_defaults(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描可变默认参数"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(Issue(file, node.lineno, node.col_offset, "MUTABLE_DEFAULT",
                        f"函数 {node.name} 使用可变对象作为默认参数", "error"))
                elif isinstance(default, ast.Call):
                    func_name = ast.unparse(default.func) if hasattr(ast, 'unparse') else ""
                    if func_name in ("list", "dict", "set"):
                        issues.append(Issue(file, node.lineno, node.col_offset, "MUTABLE_DEFAULT",
                            f"函数 {node.name} 使用可变对象作为默认参数", "error"))
    return issues

def scan_sql_injection(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描潜在的 SQL 注入（字符串拼接）"""
    issues = []
    # 用正则扫描，AST 对字符串拼接检测不够直接
    for i, line in enumerate(content.split('\n'), 1):
        if re.search(r'execute\s*\(\s*["\'].*%s.*["\']', line) or \
           re.search(r'execute\s*\(\s*f["\']', line) or \
           re.search(r'\.format\s*\(', line) and 'execute' in line:
            issues.append(Issue(file, i, 0, "SQL_INJECTION",
                "潜在的 SQL 注入风险", "warning"))
    return issues

def scan_hardcoded_secrets(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描硬编码密钥/密码"""
    issues = []
    secret_patterns = [
        (r'(?i)(api[_-]?key|apikey)\s*=\s*["\'][^"\']{10,}["\']', "API Key"),
        (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "Password"),
        (r'(?i)(secret|token)\s*=\s*["\'][^"\']{10,}["\']', "Secret/Token"),
        (r'(?i)private[_-]?key\s*=\s*["\'][^"\']{20,}["\']', "Private Key"),
    ]
    for i, line in enumerate(content.split('\n'), 1):
        for pattern, secret_type in secret_patterns:
            if re.search(pattern, line) and 'env' not in line.lower() and 'os.getenv' not in line:
                issues.append(Issue(file, i, 0, "HARDCODED_SECRET",
                    f"可能的硬编码 {secret_type}", "warning"))
    return issues

def scan_debug_code(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描调试代码"""
    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        if re.search(r'(?i)#\s*(TODO|FIXME|HACK|XXX|DEBUG|TEMP)', line):
            issues.append(Issue(file, i, 0, "DEBUG_CODE",
                f"调试/临时标记: {line.strip()}", "info"))
        if 'print(' in line and '# debug' not in line.lower():
            # 检查是否是真正的调试 print
            if re.search(r'^\s*print\s*\(', line):
                issues.append(Issue(file, i, 0, "DEBUG_CODE",
                    f"调试 print 语句", "info"))
    return issues

def scan_import_issues(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描导入问题"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0 and node.module:
                # 相对导入
                pass
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == '*':
                    issues.append(Issue(file, node.lineno, node.col_offset, "WILDCARD_IMPORT",
                        "通配符导入 (*) 会污染命名空间", "warning"))
    return issues

def scan_type_safety(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描类型安全问题"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            value = ast.unparse(node.value) if hasattr(ast, 'unparse') else ""
            if '[' in value and not value.startswith('('):
                # 检查是否有边界检查
                pass  # 过于复杂，简化
    return issues

def scan_resource_leaks(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描资源泄漏"""
    issues = []
    # 检查 asyncio client/session 是否关闭
    for i, line in enumerate(content.split('\n'), 1):
        if 'ClientSession' in line or 'AsyncClient' in line or 'httpx.AsyncClient' in line:
            # 检查是否有 with 或 close
            if 'with' not in line and 'close' not in content.split('\n')[i-1] if i > 1 else True:
                issues.append(Issue(file, i, 0, "RESOURCE_LEAK",
                    "异步客户端可能未正确关闭", "warning"))
    return issues

def scan_yaml_safety(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描 YAML 加载安全问题"""
    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        if 'yaml.load' in line and 'SafeLoader' not in line and 'safe_load' not in line:
            issues.append(Issue(file, i, 0, "YAML_UNSAFE",
                "yaml.load 默认使用 UnsafeLoader，存在安全风险", "error"))
    return issues

def scan_json_loads(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描 JSON 解析缺少错误处理"""
    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        if 'json.loads' in line or 'json.load' in line:
            # 检查是否在 try 块中
            issues.append(Issue(file, i, 0, "JSON_PARSE",
                "json.loads 可能抛出 JSONDecodeError", "info"))
    return issues

def scan_division_by_zero(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描潜在的除零"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            # 检查除数是否可能为零
            divisor = ast.unparse(node.right) if hasattr(ast, 'unparse') else ""
            if divisor in ("0", "0.0", "len()", "count"):
                issues.append(Issue(file, node.lineno, node.col_offset, "DIV_ZERO",
                    f"潜在的除零: /{divisor}", "error"))
    return issues

def scan_string_formatting(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描字符串格式化问题"""
    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        if '%s' in line or '%d' in line:
            # 检查是否有对应的 % 操作
            if line.count('%') > 1 and '%%' not in line:
                issues.append(Issue(file, i, 0, "STRING_FORMAT",
                    "旧的 % 格式化，建议使用 f-string", "info"))
    return issues

def scan_async_issues(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描异步代码问题"""
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = ast.unparse(node.func) if hasattr(ast, 'unparse') else ""
            if func in ("time.sleep", "requests.get", "requests.post"):
                # 检查是否在 async 函数中
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.AsyncFunctionDef):
                        if parent.lineno <= node.lineno <= parent.end_lineno if hasattr(parent, 'end_lineno') else True:
                            issues.append(Issue(file, node.lineno, node.col_offset, "BLOCKING_IN_ASYNC",
                                f"在 async 函数中调用阻塞函数 {func}()", "error"))
                            break
    return issues

def scan_comprehension_variable_leak(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描列表推导式变量泄漏（Python 2 问题，Python 3 已修复，但保留）"""
    return []

def scan_deprecated_functions(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描已弃用函数"""
    issues = []
    deprecated = {
        "asyncio.get_event_loop": "使用 asyncio.get_running_loop() 或 asyncio.new_event_loop()",
        "asyncio.ensure_future": "使用 asyncio.create_task()",
        "imp.load_source": "使用 importlib",
        "urllib.urlopen": "使用 urllib.request.urlopen",
    }
    for i, line in enumerate(content.split('\n'), 1):
        for old, suggestion in deprecated.items():
            if old in line:
                issues.append(Issue(file, i, 0, "DEPRECATED",
                    f"{old} 已弃用，{suggestion}", "warning"))
    return issues

def scan_encoding_issues(file: Path, content: str, tree: ast.AST) -> List[Issue]:
    """扫描编码问题"""
    issues = []
    for i, line in enumerate(content.split('\n'), 1):
        if 'open(' in line and 'encoding=' not in line:
            issues.append(Issue(file, i, 0, "ENCODING",
                "文件打开未指定编码，Windows 上可能使用 GBK", "warning"))
    return issues

# 所有扫描规则
SCANNERS = [
    scan_bare_except,
    scan_broad_except,
    scan_empty_except,
    scan_mutable_defaults,
    scan_yaml_safety,
    scan_async_issues,
    scan_deprecated_functions,
    scan_encoding_issues,
    scan_debug_code,
    scan_hardcoded_secrets,
    scan_import_issues,
    scan_json_loads,
    scan_resource_leaks,
    scan_string_formatting,
    scan_division_by_zero,
]

def scan_file(file: Path) -> List[Issue]:
    """扫描单个文件"""
    try:
        content = file.read_text(encoding='utf-8')
        tree = ast.parse(content)
        # 添加 parent 引用
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                setattr(child, 'parent', node)
    except SyntaxError as e:
        return [Issue(file, e.lineno or 1, e.offset or 0, "SYNTAX_ERROR", str(e), "error")]
    except Exception as e:
        return [Issue(file, 1, 0, "READ_ERROR", str(e), "error")]
    
    all_issues = []
    for scanner in SCANNERS:
        try:
            issues = scanner(file, content, tree)
            all_issues.extend(issues)
        except Exception as e:
            print(f"[!] 扫描器 {scanner.__name__} 在 {file} 上失败: {e}")
    
    return all_issues

def main():
    print("="*60)
    print("ZRONG 深度扫描器 v1.0")
    print("="*60)
    
    all_issues = []
    for py_file in PYTHON_FILES:
        issues = scan_file(py_file)
        all_issues.extend(issues)
        if issues:
            print(f"\n[+] {py_file.relative_to(PROJECT_ROOT)}: {len(issues)} 个问题")
            for issue in issues:
                print(f"    {issue}")
    
    print("\n" + "="*60)
    print("扫描总结")
    print("="*60)
    
    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]
    
    print(f"错误: {len(errors)}")
    print(f"警告: {len(warnings)}")
    print(f"信息: {len(infos)}")
    
    if errors:
        print("\n[错误列表]")
        for issue in errors:
            print(f"  {issue.file.name}:{issue.line} {issue.rule}: {issue.msg}")
    
    if warnings:
        print("\n[警告列表]")
        for issue in warnings:
            print(f"  {issue.file.name}:{issue.line} {issue.rule}: {issue.msg}")
    
    return len(errors), len(warnings)

if __name__ == "__main__":
    errors, warnings = main()
    sys.exit(1 if errors > 0 else 0)
