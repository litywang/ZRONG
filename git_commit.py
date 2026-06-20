import subprocess, os

os.chdir(r"C:\tools\ZRONG(Github Actiongs)")

cmds = [
    ["git", "add", "-A"],
    ["git", "status"],
    ["git", "commit", "-m", "v30.2: 调大MAX_FINAL_NODES=250, 加apply_quota debug log"],
    ["git", "push"],
]

for cmd in cmds:
    print(f"\n=== {' '.join(cmd)} ===")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    print("STDOUT:", r.stdout)
    print("STDERR:", r.stderr)
    if r.returncode != 0:
        print(f"[FAIL] returncode={r.returncode}")
        break
