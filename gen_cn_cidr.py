#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate CN CIDR data from APNIC
v28.1: 跨平台路径 + 完整导入
"""
import ipaddress
import urllib.request
from pathlib import Path
from datetime import datetime

print("[gen_cn_cidr] Fetching CN CIDR from APNIC...")

try:
    data = urllib.request.urlopen(
        'https://raw.githubusercontent.com/gaoyifan/china-operator-ip/ip-lists/china.txt',
        timeout=15
    ).read().decode()
except Exception as e:
    print(f"[gen_cn_cidr] Download failed: {e}")
    raise

lines = [l.strip() for l in data.strip().split('\n') if l.strip() and not l.startswith('#')]

output_path = Path(__file__).parent / "cn_cidr_data.py"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('#!/usr/bin/env python3\n')
    f.write('# -*- coding: utf-8 -*-\n')
    f.write('# CN CIDR blocks from APNIC (auto-generated)\n')
    f.write('# Source: https://github.com/gaoyifan/china-operator-ip\n')
    f.write(f'# Total: {len(lines)} CIDR blocks | Generated: {datetime.now()}\n\n')
    f.write('import ipaddress\n\n')
    f.write('CN_IP_RANGES = [\n')
    for line in lines:
        f.write(f'    ipaddress.ip_network("{line}"),\n')
    f.write(']\n')

print(f"[gen_cn_cidr] Done: {len(lines)} CIDR blocks -> {output_path}")
