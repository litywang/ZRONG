#!/usr/bin/env python3
"""
ZRONG Quality Check Script for Heartbeat Monitoring
Checks proxies.yaml output quality from GitHub Gist
"""

import sys
import os
import yaml
import requests
from collections import Counter

def check_quality_from_gist(gist_id):
    """Check quality from GitHub Gist"""
    try:
        # Get Gist content
        url = f"https://api.github.com/gists/{gist_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        gist_data = response.json()
        
        # Find proxies.yaml file in gist
        proxies_content = None
        for filename, file_data in gist_data.get('files', {}).items():
            if filename == 'proxies.yaml' or filename.endswith('.yaml'):
                proxies_content = file_data.get('content', '')
                break
        
        if not proxies_content:
            print("❌ No proxies.yaml found in Gist")
            return False
        
        # Parse YAML
        proxies = yaml.safe_load(proxies_content)
        # Handle proxies.yaml with 'proxies:' root key
        if isinstance(proxies, dict):
            proxies = proxies.get('proxies', proxies)
        
        if not proxies or not isinstance(proxies, list):
            print("❌ Invalid proxies.yaml format")
            return False
        
        return analyze_proxies(proxies)
        
    except Exception as e:
        print(f"❌ Error checking Gist: {e}")
        return False

def analyze_proxies(proxies):
    """Analyze proxy quality"""
    total = len(proxies)
    
    # Count Asia nodes (support both flag emoji and country codes)
    asia_count = 0
    asia_flags = [
        '\U0001f1ed\U0001f1f0',  # HK
        '\U0001f1f9\U0001f1fc',  # TW
        '\U0001f1ef\U0001f1f5',  # JP
        '\U0001f1f8\U0001f1ec',  # SG
        '\U0001f1f0\U0001f1f7',  # KR
        '\U0001f1f2\U0001f1f4',  # MO
        '\U0001f1e8\U0001f1f3',  # CN
        'HK', 'TW', 'JP', 'SG', 'KR', 'MO', 'CN',
        'TH', 'MY', 'PH', 'ID', 'VN', 'IN', 'TR',
    ]
    
    latencies = []
    
    for proxy in proxies:
        name = proxy.get('name', '') if isinstance(proxy, dict) else str(proxy)
        
        # Check if it's Asia node
        if any(flag in name for flag in asia_flags):
            asia_count += 1
        
        # Extract latency if available
        # Look for patterns like "200ms", "200 ms", etc.
        import re
        latency_match = re.search(r'(\d+)\s*ms', name)
        if latency_match:
            latencies.append(int(latency_match.group(1)))
    
    asia_ratio = (asia_count / total * 100) if total > 0 else 0
    min_latency = min(latencies) if latencies else None
    
    # Quality baseline
    baseline_nodes = 100
    baseline_asia = 35
    baseline_latency = 800
    
    # Check
    print(f"[QUALITY CHECK]")
    print(f"  Total nodes: {total} (baseline: >={baseline_nodes}) {'[OK]' if total >= baseline_nodes else '[FAIL]'}")
    print(f"  Asia ratio: {asia_ratio:.1f}% (baseline: >={baseline_asia}%) {'[OK]' if asia_ratio >= baseline_asia else '[FAIL]'}")
    if min_latency:
        print(f"  - Min latency: {min_latency}ms (baseline: ≤{baseline_latency}ms) {'✅' if min_latency <= baseline_latency else '❌'}")
    else:
        print(f"  - Min latency: N/A")
    
    # Determine pass/fail
    issues = []
    if total < baseline_nodes:
        issues.append(f"节点数不足: {total} < {baseline_nodes}")
    if asia_ratio < baseline_asia:
        issues.append(f"亚洲占比不足: {asia_ratio:.1f}% < {baseline_asia}%")
    if min_latency and min_latency > baseline_latency:
        issues.append(f"延迟过高: {min_latency}ms > {baseline_latency}ms")
    
    if issues:
        print(f"\n❌ Quality check FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print(f"\n✅ Quality check PASSED")
        return True

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python heartbeat_quality_check.py <gist_id>")
        print("  or: python heartbeat_quality_check.py <path_to_proxies.yaml>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    # Check if it's a file path or Gist ID
    if os.path.exists(target):
        print(f"📁 Checking local file: {target}")
        with open(target, 'r', encoding='utf-8') as f:
            proxies = yaml.safe_load(f)
        # Handle proxies.yaml with 'proxies:' root key
        if isinstance(proxies, dict):
            proxies = proxies.get('proxies', proxies)
        success = analyze_proxies(proxies)
    else:
        print(f"🌐 Checking GitHub Gist: {target}")
        success = check_quality_from_gist(target)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
