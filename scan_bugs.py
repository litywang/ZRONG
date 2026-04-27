#!/usr/bin/env python3
"""Deep bug scanner for ZRONG project"""
import ast, os, sys

bugs = []

def scan(path, rel):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    lines = src.split('\n')
    
    # 1. Check for bare excepts
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == 'except:' or stripped == 'except Exception:':
            bugs.append(f'[BARE_EXCEPT] {rel}:{i}: {stripped}')
    
    # 2. Check for mutable default args
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        bugs.append(f'[MUTABLE_DEFAULT] {rel}:{node.lineno}: {node.name}')
    except:
        pass
    
    # 3. Check for unreachable code after return
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body = node.body
                for j, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Return, ast.Raise)) and j < len(body) - 1:
                        next_stmt = body[j+1]
                        if not isinstance(next_stmt, (ast.Pass, ast.Expr)):
                            bugs.append(f'[UNREACHABLE] {rel}:{stmt.lineno}: code after return in {node.name}')
    except:
        pass

for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, '.')
            scan(path, rel)

for b in bugs:
    print(b)
print(f'Total bugs: {len(bugs)}')
