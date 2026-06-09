"""
ZRONG v28.63 Bug 修复脚本
修复以下确认缺陷：
1. core/clash.py: 移除 start() 末尾不可达代码（lines 311-317）
2. core/history.py: _signal_handler 调用不存在的函数名（_save_* → save_*）
3. network/geo.py: 缺少 import random
"""
import re
from pathlib import Path

BASE = Path(r"C:\tools\ZRONG")

# ── 1. core/clash.py: 移除不可达代码 ──────────────────────────────────────
clash_path = BASE / "core" / "clash.py"
content = clash_path.read_text(encoding="utf-8")

# 找到并移除 start() 方法末尾的不可达代码块
# 在 "        return False" (外层 except) 后，
# 删除注释 "# v28.50: 启动成功时关闭管道避免泄漏" 及 其下3行
old_block = """        except (OSError, subprocess.SubprocessError) as e:
            logging.debug(f"   [ERROR] Clash 启动异常：{e}")
            return False
        # v28.50: 启动成功时关闭管道避免泄漏
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except OSError as e:
                logging.debug(f"关闭 stdout 管道失败: {e}", exc_info=True)

    def stop(self):"""

new_block = """        except (OSError, subprocess.SubprocessError) as e:
            logging.debug(f"   [ERROR] Clash 启动异常：{e}")
            return False

    def stop(self):"""

if old_block in content:
    content = content.replace(old_block, new_block)
    clash_path.write_text(content, encoding="utf-8")
    print("[OK] core/clash.py: 移除不可达代码块")
else:
    print("[WARN] core/clash.py: 未找到目标代码块，跳过")

# ── 2. core/history.py: _signal_handler 函数名修正 ─────────────────────────
history_path = BASE / "core" / "history.py"
content = history_path.read_text(encoding="utf-8")

content = content.replace("_save_node_history()", "save_node_history()")
content = content.replace("_save_source_history()", "save_source_history()")
history_path.write_text(content, encoding="utf-8")
print("[OK] core/history.py: _save_node_history → save_node_history")
print("[OK] core/history.py: _save_source_history → save_source_history")

# ── 3. network/geo.py: 添加 import random ───────────────────────────────────
geo_path = BASE / "network" / "geo.py"
content = geo_path.read_text(encoding="utf-8")

# 检查是否已有 import random
has_random_import = bool(
    re.search(r"^\s*import random", content, re.MULTILINE)
    or re.search(r"^\s*from random import", content, re.MULTILINE)
)

if not has_random_import:
    # 在 import typing 之后添加 import random
    content = re.sub(
        r"(\nimport typing\b)",
        r"\1\nimport random",
        content
    )
    geo_path.write_text(content, encoding="utf-8")
    print("[OK] network/geo.py: 添加 import random")
else:
    print("[INFO] network/geo.py: random 已导入，跳过")

print("\n✅ 所有修复完成")