import subprocess, os

os.chdir(r"C:\tools\ZRONG(Github Actiongs)")

def run(cmd):
    print(f"\n=== {' '.join(cmd)} ===")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.stdout: print("STDOUT:", r.stdout[:500])
    if r.stderr: print("STDERR:", r.stderr[:500])
    return r.returncode

# stash 未暂存的变化
run(["git", "stash", "push", "-m", "auto-stash-before-pull"])
# pull
code = run(["git", "pull", "--rebase", "origin", "main"])
# 恢复 stash
run(["git", "stash", "pop"])
if code != 0:
    print("[WARN] pull --rebase failed, try merge")
    run(["git", "rebase", "--abort"])
    run(["git", "pull", "origin", "main"])

# 现在提交推送
for cmd in [
    ["git", "add", "-A"],
    ["git", "status"],
    ["git", "commit", "-m", "v30.2: MAX_FINAL_NODES=250, add apply_quota debug log"],
    ["git", "push"],
]:
    code = run(cmd)
    if code != 0 and cmd[1] == "push":
        print("[FAIL] push failed")
        break
