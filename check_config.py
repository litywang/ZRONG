import re

with open('crawler.py', 'r', encoding='utf-8') as f:
    content = f.read()

patterns = [
    'MAX_FINAL_NODES',
    'TARGET_ASIA_RATIO', 
    'ASIA_MIN_COUNT',
    'ASIA_PRIORITY_BONUS',
    'ASIA_TCP_RELAX',
    'MAX_TCP_TEST_NODES',
    'MAX_PROXY_TEST_NODES',
    'MAX_PROXY_LATENCY',
]

for p in patterns:
    # 匹配多行默认值
    matches = re.findall(p + r'\s*=\s*int\(os\.getenv\(["\']' + p + r'["\'],\s*([^\)]+)\)\)', content)
    if not matches:
        matches = re.findall(p + r'\s*=\s*float\(os\.getenv\(["\']' + p + r'["\'],\s*([^\)]+)\)\)', content)
    if not matches:
        matches = re.findall(p + r'\s*=\s*([^\s#\n]+)', content)
    if matches:
        print(f'{p}: {matches[0]}')
