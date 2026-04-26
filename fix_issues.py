import re

with open('crawler.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = 0

# Fix F541: f-string without placeholders - 按行精确匹配
for i, line in enumerate(lines):
    if '强制亚洲置顶' in line and 'asia_nodes' in line and 'non_asia_nodes' in line:
        lines[i] = line.replace(
            'print(f"   🔄 强制亚洲置顶：{len(asia_nodes)} 亚洲 + {len(non_asia_nodes)} 非亚洲")',
            'print("   强制亚洲置顶：{} 亚洲 + {} 非亚洲".format(len(asia_nodes), len(non_asia_nodes)))'
        )
        fixed += 1
        break  # v28.22: 只修复第一个匹配项，避免误伤

# Fix E712: comparison to True - 按行精确匹配
for i, line in enumerate(lines):
    if 'proxy.get("tls") == True' in line and 'port == 443' in line:
        lines[i] = line.replace(
            'if proxy.get("tls") == True and port == 443:',
            'if proxy.get("tls") and port == 443:'
        )
        fixed += 1
        break  # v28.22: 只修复第一个匹配项

with open('crawler.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f'Fixed {fixed} issues (F541, E712)')
