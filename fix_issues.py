import re

with open('crawler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix F541: f-string without placeholders
content = content.replace(
    'print(f"   🔄 强制亚洲置顶：{len(asia_nodes)} 亚洲 + {len(non_asia_nodes)} 非亚洲")',
    'print("   强制亚洲置顶：{} 亚洲 + {} 非亚洲".format(len(asia_nodes), len(non_asia_nodes)))'
)

# Fix E712: comparison to True
content = content.replace(
    'if proxy.get("tls") == True and port == 443:',
    'if proxy.get("tls") and port == 443:'
)

with open('crawler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed F541 and E712')
