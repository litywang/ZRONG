import yaml
import sys

# v28.22: 增加 YAML 格式校验
def validate_proxies_yaml(filepath="proxies.yaml"):
    """验证 proxies.yaml 格式正确性"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)

        # 基本结构校验
        assert 'proxies' in cfg, "缺少 proxies 字段"
        assert isinstance(cfg['proxies'], list), "proxies 必须是列表"

        # 节点字段校验 (抽样前10个)
        required_fields = ['name', 'server', 'port', 'type']
        for i, p in enumerate(cfg['proxies'][:10]):
            for field in required_fields:
                assert field in p, f"节点 {i} 缺少 {field}"

        return True, cfg, "✓ 格式验证通过"
    except FileNotFoundError:
        return False, None, f"❌ 文件不存在: {filepath}"
    except Exception as e:
        return False, None, f"❌ 验证失败: {e}"

ok, cfg, msg = validate_proxies_yaml()
print(msg)
if not ok:
    sys.exit(1)

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
