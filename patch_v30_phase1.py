#!/usr/bin/env python3
"""v30.0 Phase 1.1: Clash配置简化 + test_proxy超时优化"""
import re

PATH = 'core/clash.py'

with open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# === Change 1: Simplify Clash config (remove rule-providers, fake-ip DNS) ===
# Replace from "# 大陆路由规则" to the closing of the config dict, before "with open(CONFIG_FILE"
old_config_start = '# 大陆路由规则'
new_config = '''        # v30.0: 简化Clash配置——移除rule-providers/DNS fake-ip（下载耗时不稳定）
        # 测速环境只需：所有流量走TEST代理组，无需路由规则和DNS提供者
        rules = ["MATCH,TEST"]

        config = {
            "port": CLASH_PORT, "socks-port": CLASH_PORT + 1, "allow-lan": False, "mode": "global",
            "log-level": "error", "external-controller": f"127.0.0.1:{CLASH_API_PORT}",
            "secret": "",
            "ipv6": False, "unified-delay": True, "tcp-concurrent": True,
            # v30.0: 简化DNS——仅用公共DNS，无需fake-ip和规则提供者
            "dns": {
                "enable": True,
                "listen": "0.0.0.0:1053",
                "enhanced-mode": "normal",
                "nameserver": [
                    "8.8.8.8",
                    "1.1.1.1",
                ],
            },
            "proxies": valid_proxies,
            "proxy-groups": [{"name": "TEST", "type": "select", "proxies": names}],
            "rules": rules
        }'''

# Find the start marker
start_idx = content.find(old_config_start)
if start_idx == -1:
    print("ERROR: Cannot find start marker")
    exit(1)

# Find the end: look for 'with open(CONFIG_FILE' after start
end_marker = 'with open(CONFIG_FILE'
end_idx = content.find(end_marker, start_idx)
if end_idx == -1:
    print("ERROR: Cannot find end marker")
    exit(1)

# Get the whitespace before 'with'
pre_with = content[:end_idx].rstrip('\n')
trailing = content[end_idx - len(pre_with.rsplit('\n', 1)[-1]):end_idx]

old_text = content[start_idx:end_idx]
content = content[:start_idx] + new_config + '\n        ' + content[end_idx:]

print(f"Change 1: Replaced Clash config ({len(old_text)} -> {len(new_config)} bytes)")

# === Change 2: Optimize test_proxy timeouts ===
old_test_proxy = '''    def test_proxy(self, name, server=None, port=None, retry=True):
        """v29.04: 真实测速 - 添加详细日志，记录每个URL的失败原因"""'''

new_test_proxy = '''    def test_proxy(self, name, server=None, port=None, retry=False):
        """v30.0: 优化测速——连接超时3s+读取超时5s，ConnectTimeout直接失败"""'''

idx = content.find(old_test_proxy)
if idx == -1:
    print("ERROR: Cannot find test_proxy method signature")
    exit(1)

# Find the end of test_proxy (next method)
next_method = content.find('\n    def ', idx + len(old_test_proxy))
if next_method == -1:
    # Maybe it's the last method
    next_method = len(content)

old_method = content[idx:next_method]

new_method = '''    def test_proxy(self, name, server=None, port=None, retry=False):
        """v30.0: 优化测速——连接超时3s+读取超时5s，ConnectTimeout直接失败"""
        result = {"success": False, "latency": 9999.0, "speed": 0.0, "error": "", "mainland_reachable": False}
        try:
            requests.put(f"http://127.0.0.1:{CLASH_API_PORT}/proxies/TEST", json={"name": name}, timeout=2)
            time.sleep(0.03)
            px = {"http": f"http://127.0.0.1:{CLASH_PORT}", "https": f"http://127.0.0.1:{CLASH_PORT}"}
            # v30.0: 连接超时3s + 读取超时5s（分离超时，快速识别不可达节点）
            timeout_main = (3, 5)

            # 主池：HTTP 204检测
            for url in TEST_URLS:
                try:
                    start = time.time()
                    resp = requests.get(url, proxies=px, timeout=timeout_main, allow_redirects=True)
                    elapsed = (time.time() - start) * 1000
                    if resp.status_code in (200, 204):
                        content_len = len(resp.content) if resp.content else 0
                        speed_kbs = content_len / 1024 / max(elapsed / 1000, 0.01) if content_len > 0 else 1.0
                        result = {"success": True, "latency": round(elapsed, 1), "speed": round(speed_kbs, 1), "error": "", "mainland_reachable": False}
                        break
                except requests.ConnectTimeout:
                    logging.debug("test_proxy %s: ConnectTimeout -> skip", name)
                    break  # 连接超时=网络不可达，无需尝试其他URL
                except requests.ReadTimeout:
                    logging.debug("test_proxy %s: ReadTimeout", name)
                    break  # 读取超时=线路质量差
                except requests.RequestException as e:
                    logging.debug("test_proxy %s: %s", name, str(e)[:60])
                    continue  # 其他错误，尝试下一个URL

            # 备用池：更短超时
            if not result["success"]:
                timeout_bak = (2, 3)
                for url in TEST_URLS_BACKUP:
                    try:
                        start = time.time()
                        resp = requests.get(url, proxies=px, timeout=timeout_bak, allow_redirects=True)
                        elapsed = (time.time() - start) * 1000
                        if resp.status_code in (200, 204):
                            content_len = len(resp.content) if resp.content else 0
                            speed_kbs = content_len / 1024 / max(elapsed / 1000, 0.01) if content_len > 0 else 1.0
                            result = {"success": True, "latency": round(elapsed, 1), "speed": round(speed_kbs, 1), "error": "", "mainland_reachable": False}
                            break
                    except requests.RequestException:
                        continue

            if not result["success"]:
                result["error"] = "All test URLs failed"
        except requests.RequestException as e:
            result["error"] = str(e)[:60]

        # v30.0: 默认不重试（重试浪费大量时间且结果通常相同）
        # retry=True 仅由调用方在有充分理由时手动传入
        if retry and not result["success"]:
            time.sleep(0.3)
            return self.test_proxy(name, server=server, port=port, retry=False)
        return result'''

content = content[:idx] + new_method + content[next_method:]
print(f"Change 2: Replaced test_proxy ({len(old_method)} -> {len(new_method)} bytes)")

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: core/clash.py updated")
