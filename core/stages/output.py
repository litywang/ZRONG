# core/stages/output.py - 输出生成与推送
# v28.99 Phase C: 从 main_flow.py 提取
# 生成 proxies.yaml、subscription.txt、Telegram 推送

import os
import re
import base64
import logging
import time
import yaml
from datetime import datetime
from core import format_proxy_to_link
from core.validator import is_asia
from core.filter import final_sort_key
from core.history import _SOURCE_HISTORY, dynamic_source_weight
from sources.config import (
    MAX_FINAL_NODES, TARGET_ASIA_RATIO, ASIA_MIN_COUNT,
    BOT_TOKEN, CHAT_ID, REPO_NAME, TEST_URL,
)

# v29.1: [WEB]NET 节点数量上限
from core.filter import MAX_WEB_NET_NODES

# 标准输出字段（防止内部字段写入 YAML）
CLASH_FIELDS = {
    'name', 'type', 'server', 'port', 'udp', 'tfo', 'mptcp',
    'skip-cert-verify', 'sni', 'servername', 'tls', 'alpn', 'ca', 'cert', 'key',
    'client-fingerprint', 'obfs', 'obfs-password',
    'network', 'ws-opts', 'grpc-opts', 'h2-opts', 'http-opts',
    'reality-opts', 'flow', 'pinned-sha256', 'dialer-proxy',
    'cipher', 'password', 'plugin', 'plugin-opts',
    'uuid', 'alterId', 'aid',
    'protocol', 'protocol-param', 'obfs', 'obfs-param',
    'auth-str', 'up', 'down',
    'congestion-controller',
}


def _cn_direct_rules() -> list:
    """生成大陆直连规则"""
    if os.getenv("CN_DIRECT", "1") != "1":
        return []

    _cn_domains = [
        "cn", "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
        "taobao.com", "tmall.com", "jd.com", "baidu.com", "bilibili.com",
        "qq.com", "weibo.com", "alipay.com", "alicdn.com", "aliyun.com",
        "weixin.qq.com", "163.com", "126.com", "sina.com.cn", "sohu.com",
        "youku.com", "douyin.com", "xiaohongshu.com", "zhihu.com",
        "cnblogs.com", "csdn.net", "jianshu.com", "oschina.net",
        "gitee.com", "coding.net", "tencent.com", "tencentcloud.com",
        "alibaba.com", "alibaba-inc.com", "antgroup.com", "ele.me",
        "meituan.com", "dianping.com", "58.com", "ganji.com",
        "autohome.com.cn", "xcar.com.cn", "pcauto.com.cn",
        "ithome.com", "sspai.com", "geekpark.net", "36kr.com",
        "chinaunicom.com", "10010.com", "189.cn", "10086.cn",
        "bankcomm.com", "icbc.com.cn", "ccb.com", "boc.cn",
        "aliyuncs.com", "qcloud.com", "qiniu.com", "upaiyun.com",
    ]
    rules = [f"DOMAIN-SUFFIX,{d},DIRECT" for d in _cn_domains]
    rules += [
        "GEOIP,CN,DIRECT",
        "IP-CIDR,127.0.0.0/8,DIRECT",
        "IP-CIDR,172.16.0.0/12,DIRECT",
        "IP-CIDR,192.168.0.0/16,DIRECT",
        "IP-CIDR,10.0.0.0/8,DIRECT",
        "IP-CIDR,100.64.0.0/10,DIRECT",
        "IP-CIDR,169.254.0.0/16,DIRECT",
        "IP-CIDR,224.0.0.0/4,DIRECT",
        "IP-CIDR,240.0.0.0/4,DIRECT",
        "IP-CIDR,255.255.255.255/32,DIRECT",
        "DOMAIN-SUFFIX,dns.alidns.com,DIRECT",
        "DOMAIN-SUFFIX,doh.pub,DIRECT",
        "DOMAIN-SUFFIX,dns.pub,DIRECT",
        "MATCH,[GEO] Select",
    ]
    return rules


def apply_quota(final: list) -> list:
    """柔性配额：亚洲节点保底~目标~上限，非亚洲补足 + [WEB]硬截断 + 低价值地区硬筛"""
    # v30.0 Phase6: [WEB] 硬截断（name.startswith("[WEB]") 而非 "NET" in name）
    web_nodes = [p for p in final if p.get("name", "").lower().startswith("[web]")]
    non_web_final = [p for p in final if not p.get("name", "").lower().startswith("[web]")]
    if len(web_nodes) > MAX_WEB_NET_NODES:
        web_nodes = web_nodes[:MAX_WEB_NET_NODES]
        logging.info(f"   [v30.0] [WEB] 节点截断为 {MAX_WEB_NET_NODES} 个 (原{len(web_nodes)}个)")
    final = non_web_final + web_nodes  # [WEB] 放末尾

    # v30.0 Phase6: 低价值非亚洲 emoji 地区硬筛（在 apply_quota，防止 history 节点绕过）
    LOW_VALUE_FLAGS = {'🇺🇦', '🇹🇷', '🇮🇷'}
    before = len(final)
    final = [p for p in final if not any(fl in p.get("name", "") for fl in LOW_VALUE_FLAGS)]
    if before > len(final):
        logging.info(f"   [v30.0] 低价值非亚洲节点过滤: {before} -> {len(final)}")

    asia_final = sorted([p for p in final if is_asia(p)], key=final_sort_key)
    non_asia_final = sorted([p for p in final if not is_asia(p)], key=final_sort_key)

    # v29.1: [WEB]NET 节点上限（已由上方 [WEB] 截断覆盖，此处保留兼容）
    web_net = [p for p in non_asia_final if "NET" in p.get("name", "")]
    other_non = [p for p in non_asia_final if "NET" not in p.get("name", "")]
    if len(web_net) > MAX_WEB_NET_NODES:
        web_net = web_net[:MAX_WEB_NET_NODES]
        logging.info(f"   [v29.1] [WEB]NET 节点截断为 {MAX_WEB_NET_NODES} 个")
    non_asia_final = other_non + web_net

    target_asia = int(MAX_FINAL_NODES * TARGET_ASIA_RATIO)
    max_asia = int(MAX_FINAL_NODES * 0.75)
    min_asia = min(ASIA_MIN_COUNT, MAX_FINAL_NODES)
    target_non = MAX_FINAL_NODES - target_asia

    if len(asia_final) < min_asia:
        actual_non = min(len(non_asia_final), MAX_FINAL_NODES - len(asia_final))
        result = asia_final + non_asia_final[:actual_non]
        logging.debug(f"   [WARN] 亚洲节点不足保底{min_asia}个，全部保留{len(asia_final)}个 + 非亚洲{actual_non}个")
    elif len(asia_final) <= target_asia:
        actual_non = min(len(non_asia_final), MAX_FINAL_NODES - len(asia_final))
        result = asia_final + non_asia_final[:actual_non]
        logging.debug(f"   [OK] 亚洲{len(asia_final)}个(柔性区间) + 非亚洲{actual_non}个")
    elif len(asia_final) <= max_asia:
        result = asia_final[:target_asia] + non_asia_final[:target_non]
        logging.debug(f"   [OK] 亚洲配额{target_asia}个 + 非亚洲配额{target_non}个")
    else:
        actual_non = min(len(non_asia_final), MAX_FINAL_NODES - max_asia)
        result = asia_final[:max_asia] + non_asia_final[:actual_non]
        logging.debug(f"   [OK] 亚洲截断{max_asia}个(上限) + 非亚洲{actual_non}个")

    return result[:MAX_FINAL_NODES]


def _clean_nodes(nodes: list) -> list:
    """输出前清洗内部字段"""
    return [
        {k: v for k, v in p.items() if not k.startswith('_') and k in CLASH_FIELDS}
        for p in nodes
    ]


def _deduplicate_names(nodes: list) -> list:
    """去重节点名称（同名节点加数字后缀）"""
    names = {}
    result = []
    for p in nodes:
        original = p["name"]
        count = names.get(original, 0)
        if count > 0:
            p["name"] = f"{original}-{count}"
        names[original] = count + 1
        result.append(p)
    return result


def write_output(final: list, nres: list, stats: dict, elapsed: float) -> None:
    """生成 proxies.yaml 和 subscription.txt"""
    unique_final = _deduplicate_names(final)
    cleaned = _clean_nodes(unique_final)

    # 源权重统计
    if _SOURCE_HISTORY:
        logging.debug("\n[STAT] 源权重统计（Top 10）:")
        sorted_srcs = sorted(
            _SOURCE_HISTORY.items(),
            key=lambda x: dynamic_source_weight(x[0]),
            reverse=True
        )[:10]
        for url, rec in sorted_srcs:
            w = dynamic_source_weight(url)
            rate = rec["success_count"] / max(rec["success_count"] + rec["fail_count"], 1)
            logging.debug(f"   • 权重{w:.1f} | 成功率{rate:.0%} | {url[:60]}...")

    # 写入 proxies.yaml
    cfg = {
        "proxies": cleaned,
        "proxy-groups": [
            {"name": "[START] Auto", "type": "url-test",
             "proxies": [p["name"] for p in cleaned],
             "url": TEST_URL, "interval": 300, "tolerance": 50},
            {"name": "[GEO] Select", "type": "select",
             "proxies": ["[START] Auto"] + [p["name"] for p in cleaned]},
        ],
        "rules": _cn_direct_rules(),
    }
    with open("proxies.yaml", "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, Dumper=yaml.SafeDumper)

    # 写入 subscription.txt（整块 base64）
    plain = '\n'.join(link for p in unique_final
                      if (link := format_proxy_to_link(p)) is not None)
    b64 = base64.b64encode(plain.encode('utf-8')).decode('utf-8')
    with open("subscription.txt", "w", encoding="utf-8") as f:
        f.write(b64)

    # 日志统计
    asia_ct = sum(1 for p in unique_final if is_asia(p))
    min_lat = 9999
    for p in unique_final[:20]:
        m = re.search(r"(\d+)", p.get("name", ""))
        if m and 0 < (lat := int(m.group(1))) < min_lat:
            min_lat = lat
    if min_lat == 9999:
        min_lat = 0
    asia_pct = round(asia_ct * 100 / max(len(unique_final), 1), 1)

    logging.debug("\n" + "=" * 180)
    logging.debug("[STAT] 统计结果")
    logging.debug("=" * 180)
    logging.debug(f"• Fork 来源：{stats['fork_count']}")
    logging.debug(f"• Telegram: {stats['tg_count']} | 固定：{stats['fixed_count']} | 总：{stats['total_urls']}")
    logging.debug(f"• 原始：{len(unique_final)} | TCP: {len(nres)} | 最终：{len(unique_final)}")
    logging.debug(f"• 亚洲：{asia_ct} 个 ({asia_pct}%)")
    logging.debug(f"• 最低延迟：{min_lat:.1f} ms")
    logging.debug(f"• 耗时：{elapsed:.1f} 秒")
    logging.debug("=" * 180 + "\n")


def send_telegram_notify(unique_final: list, nres: list, stats: dict, elapsed: float) -> None:
    """发送 Telegram 通知"""
    if not (BOT_TOKEN and CHAT_ID and REPO_NAME):
        return

    ts = int(time.time())
    repo = REPO_NAME
    yaml_url = f"https://raw.githubusercontent.com/{repo}/main/proxies.yaml?t={ts}"
    txt_url = f"https://raw.githubusercontent.com/{repo}/main/subscription.txt?t={ts}"
    repo_path = f"https://github.com/{repo}/blob/main/"
    yaml_html = f"{repo_path}proxies.yaml"
    txt_html = f"{repo_path}subscription.txt"

    asia_ct = sum(1 for p in unique_final if is_asia(p))
    asia_pct = round(asia_ct * 100 / max(len(unique_final), 1), 1)
    min_lat = 9999
    for p in unique_final[:20]:
        m = re.search(r"(\d+)", p.get("name", ""))
        if m and 0 < (lat := int(m.group(1))) < min_lat:
            min_lat = lat
    if min_lat == 9999:
        min_lat = 0

    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    msg = f"""[START]<b>节点更新完成</b>[CELEBRATE]

[STAT] <b>统计数据:</b>
• Telegram: {stats['tg_count']} | 固定：{stats['fixed_count']} | 总订阅：{stats['total_urls']}
• Fork 来源：{stats['fork_count']}
• 原始：{len(unique_final)} | TCP: {len(nres)} | 最终：<code>{len(unique_final)}</code> 个
• 亚洲：{asia_ct} 个 ({asia_pct}%)
• 最低延迟：{min_lat:.1f} ms
• 平均耗时：{elapsed:.1f} 秒
━━━━━━━━━━━━━━━━━━━━━━━

[SAVE] <b>直链下载:</b>
YAML: <code>{yaml_url}</code>
TXT: <code>{txt_url}</code>

[WEB] <b>网页查看:</b>
YAML: <a href="{yaml_html}">{yaml_html}</a>
TXT: <a href="{txt_html}">{txt_html}</a>

━━━━━━━━━━━━━━━━━━━━━━━

[WEB] <b>支持协议:</b> VMess | VLESS | Trojan | SS | Hysteria2 | Hysteria | TUIC | WireGuard
[PERSON]‍[PC] <b>作者:</b> Anftlity

<b>更新时间:</b> {update_time}"""

    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        logging.debug("[OK] Telegram通知已发送")
    except Exception as e:
        logging.debug(f"[WARN] Telegram推送失败：{e}")
