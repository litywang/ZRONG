#!/usr/bin/env python3
# Generate CN CIDR data from APNIC
# v28.0: 修复硬编码路径，使用 Path(__file__) 跨平台兼容
import ipaddress
from datetime import datetime
from pathlib import Path

print("🔄 正在从 APNIC 更新中国 CIDR 数据...")

try:
    import urllib.request
    data = urllib.request.urlopen(
        'https://raw.githubusercontent.com/gaoyifan/china-operator-ip/ip-lists/china.txt',
        timeout=15
    ).read().decode()
except Exception as e:
    print(f"❌ 下载失败: {e}")
    raise

lines = [
    l.strip() for l in data.strip().split('\n')
    if l.strip() and not l.strip().startswith('#')
]

# v28.0: 跨平台路径，不再硬编码 C:\tools\...
output_path = Path(__file__).parent / "cn_cidr_data.py"

with open(output_path, 'w', encoding='utf-8') as f:
    f.write('# CN CIDR blocks from APNIC (auto-generated)\n')
    f.write('# Source: https://github.com/gaoyifan/china-operator-ip\n')
    f.write(f'# Total: {len(lines)} CIDR blocks | Generated: {datetime.now()}\n\n')
    f.write('CN_IP_RANGES = [\n')
    for line in lines:
        f.write(f'    ipaddress.ip_network("{line}"),\n')
    f.write(']\n')

print(f'✅ Done: {len(lines)} CIDR blocks written to {output_path}')
