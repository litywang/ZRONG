import yaml

with open('proxies.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

proxies = cfg.get('proxies', [])
print(f'Total proxies: {len(proxies)}')

# 统计区域分布
from collections import Counter
regions = Counter()
for p in proxies:
    name = p.get('name', '')
    # 提取emoji flag
    if name and len(name) >= 2:
        # emoji flag 是两个字符
        flag = name[:2]
        regions[flag] += 1

print('\nRegion distribution:')
for flag, count in regions.most_common(15):
    print(f'  {flag}: {count}')

# 检查前5个节点
print('\nFirst 5 nodes:')
for i, p in enumerate(proxies[:5]):
    ptype = p.get('type', '')
    server = p.get('server', '')
    port = p.get('port', '')
    name = p.get('name', '')
    print(f'  {i+1}. {ptype} {server}:{port} | {name}')
    # 检查关键字段
    if ptype == 'vmess':
        uuid = p.get('uuid', '')
        tls = p.get('tls', '')
        print(f'     uuid={uuid[:8]}... tls={tls}')
    elif ptype == 'vless':
        uuid = p.get('uuid', '')
        flow = p.get('flow', '')
        tls = p.get('tls', '')
        print(f'     uuid={uuid[:8]}... flow={flow} tls={tls}')
    elif ptype == 'trojan':
        pwd = p.get('password', '')
        sni = p.get('sni', '')
        print(f'     pwd={pwd[:8]}... sni={sni}')
