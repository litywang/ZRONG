# -*- coding: utf-8 -*-
import subprocess, os
from pathlib import Path

# v28.22: 使用项目根目录（兼容所有平台）
project_root = Path(__file__).parent.resolve()
os.chdir(project_root)

# Clean temp files (v28.22: 加异常处理)
for f in ["_do_commit.py", "_fix_conflict.py"]:
    try:
        os.remove(f)
    except FileNotFoundError:
        pass  # 文件不存在是正常的
    except PermissionError:
        print(f"⚠️ 无法删除 {f}: 权限不足")

# Commit (v28.22: 加错误处理)
try:
    subprocess.run(["git", "add", "crawler.py"], check=True, capture_output=True)
    r = subprocess.run(
        ["git", "commit", "-m", "v28.22: thread safety + bug fixes + config externalization"],
        capture_output=True, encoding="utf-8", errors="replace"
    )
    print("commit:", r.stdout[:300] if r.stdout else "no output",
          r.stderr[:200] if r.stderr else "")
except subprocess.CalledProcessError as e:
    print(f"❌ Git commit failed: {e}")
    print(f"stderr: {e.stderr}")

# Push (v28.22: 加错误处理)
try:
    r2 = subprocess.run(["git", "push"], capture_output=True, encoding="utf-8", errors="replace")
    print("push:", r2.stdout[:200] if r2.stdout else "no output",
          r2.stderr[:200] if r2.stderr else "")
except subprocess.CalledProcessError as e:
    print(f"❌ Git push failed: {e}")
