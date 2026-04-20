#!/usr/bin/env python3
# Generate CN CIDR data from APNIC
import urllib.request

data = urllib.request.urlopen('https://raw.githubusercontent.com/gaoyifan/china-operator-ip/ip-lists/china.txt', timeout=15).read().decode()
lines = [l.strip() for l in data.strip().split('\n') if l.strip()]

with open(r'C:\tools\ZRONG-main\cn_cidr_data.py', 'w', encoding='utf-8') as f:
    f.write('# CN CIDR blocks from APNIC (auto-generated)\n')
    f.write('# Source: https://github.com/gaoyifan/china-operator-ip\n')
    f.write('# Total: {} CIDR blocks\n\n'.format(len(lines)))
    f.write('CN_IP_RANGES = [\n')
    for line in lines:
        f.write('    ipaddress.ip_network("{}"),\n'.format(line))
    f.write(']\n')

print(f'Done: {len(lines)} CIDR blocks written to cn_cidr_data.py')
