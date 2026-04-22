# -*- coding: utf-8 -*-
import subprocess, os
os.chdir(r"C:\Users\Administrator\.qclaw\ZRONG")

# Clean temp files
for f in ["_do_commit.py","_fix_conflict.py"]:
    try: os.remove(f)
    except: pass

# Commit
subprocess.run(["git","add","crawler.py"], capture_output=True)
r = subprocess.run(["git","commit","-m","v28.5: add async HTTP fetch (optional via USE_ASYNC_FETCH=1)"], capture_output=True, encoding="utf-8", errors="replace")
print("commit:", r.stdout[:300], r.stderr[:200])

# Push
r2 = subprocess.run(["git","push"], capture_output=True, encoding="utf-8", errors="replace")
print("push:", r2.stdout[:200], r2.stderr[:200])