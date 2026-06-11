#!/usr/bin/env python3
"""v30.0 Phase 4: [WEB]节点过滤 + 亚洲优先采集 + Workflow清理"""
import re

# === Change 1: core/stages/speed_test.py - 预过滤 [WEB] 节点 + 亚洲优先排序 ===
PATH_SPEED = 'core/stages/speed_test.py'
with open(PATH_SPEED, 'r', encoding='utf-8') as f:
    content = f.read()

old_build_queue = """        untested_items = [
            item for item in nres_untested
            if f"{item['proxy']['server']}:{item['proxy']['port']}" not in tested
            and not is_node_disabled(item['proxy'])
        ]"""

new_build_queue = """        # v30.0: [WEB] 节点预过滤（CDN/WEB代理节点大陆用户不可靠）
        untested_items = [
            item for item in nres_untested
            if f"{item['proxy']['server']}:{item['proxy']['port']}" not in tested
            and not is_node_disabled(item['proxy'])
            and not item['proxy'].get('name', '').startswith('[WEB]')
        ]

        # v30.0: 亚洲节点优先（更快被测速、获得更好的speed数据参与排序）
        untested_items.sort(key=lambda x: (
            0 if is_asia(x['proxy']) else 1,  # Asia first
            x.get('latency', 9999)             # then by TCP latency
        ))"""

content = content.replace(old_build_queue, new_build_queue)

with open(PATH_SPEED, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: speed_test.py - [WEB] filter + Asia-first sorting")


# === Change 2: core/filter.py - 收紧 [WEB] 节点上限 ===
PATH_FILTER = 'core/filter.py'
with open(PATH_FILTER, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'MAX_WEB_NET_NODES = int(os.getenv("MAX_WEB_NET_NODES", "15"))',
    'MAX_WEB_NET_NODES = int(os.getenv("MAX_WEB_NET_NODES", "10"))'
)

with open(PATH_FILTER, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: filter.py - MAX_WEB_NET_NODES 15→10")


# === Change 3: GitHub Actions workflow - 更新为 v30.0 + 清理废弃配置 ===
PATH_WORKFLOW = '.github/workflows/update.yml'
with open(PATH_WORKFLOW, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'name: Update Subscription Nodes - v28',
    'name: Update Subscription Nodes - v30'
)
content = content.replace(
    '      - name: Run Crawler v28.98',
    '      - name: Run Crawler v30.0'
)
content = content.replace(
    "git commit -m \"Update proxies $(date '+%Y-%m-%d %H:%M') [v28.98]\"",
    "git commit -m \"Update proxies $(date '+%Y-%m-%d %H:%M') [v30.0]\""
)
# Remove ENABLE_HEALTH_CHECK=0 block (obsolete)
content = content.replace(
    "          # 🏥 v28.98: 暂时禁用健康检查（Actions环境Clash高并发不稳定，恢复稳定后重新启用）\n          ENABLE_HEALTH_CHECK: '0'\n          HEALTH_CHECK_MAX_WORKERS: '8'\n          HEALTH_CHECK_TIMEOUT: '10'\n\n          ",
    "          "
)
# Remove ZRONG_USE_NEW_SCORING (no longer a switch)
content = content.replace(
    "          # 🌏 v28.50: 启用新版大陆友好评分\n          ZRONG_USE_NEW_SCORING: '1'\n\n          # 🌏 v28.58: 大陆可达性测试通过后的额外加分",
    "          # 🌏 v28.58: 大陆可达性测试加分（默认关闭MAINLAND_TEST时不生效）"
)
# Update MAX_WEB_NET_NODES
content = content.replace(
    "          # 🏷 v29.1: CDN伪装节点数量限制\n          MAX_WEB_NET_NODES: '15'",
    "          # 🏷 v30.0: CDN伪装节点数量上限（收紧到10个）\n          MAX_WEB_NET_NODES: '10'"
)

with open(PATH_WORKFLOW, 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: update.yml - v30.0 workflow updates + cleanup")
