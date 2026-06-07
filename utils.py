# utils.py - 工具函数（从 crawler.py 提取）
# 包含通用工具函数，减少 crawler.py 行数，便于维护
# 与 crawler.py 原逻辑保持一致，避免引入 BUG

import hashlib
import logging
import os
import re
import ipaddress
import hashlib
import logging
import os
import re
import ipaddress
from pathlib import Path

logger = logging.getLogger(__name__)
from config import (
    NON_FRIENDLY_REGIONS, NON_FRIENDLY_PENALTY,
    ASIA_REGIONS, REQUESTS_PER_SECOND,
    ASIA_PRIORITY_BONUS, MAX_RETRIES,
)



WORK_DIR = Path(os.getcwd()) / "clash_temp"

HEADERS_POOL = [{
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
}, {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}, {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X)"
    " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
}]

def _safe_port(val, default=443):
    """BUGFIX: port 安全转换，防止 None/非法值（与 crawler.py 原逻辑一致）"""
    try:
        p = int(val) if val else default
        if p <= 0 or p > 65535:
            return default
        return p
    except (ValueError, TypeError):
        return default

def is_pure_ip(host: str) -> bool:
    """判断是否为纯IP（不含域名）"""
    try:
        ipaddress.ip_address(host)
        return True
    except (ValueError, TypeError):
        return False

def get_region(name, server=None, sni=None):
    """根据节点名称检测区域 - v27: 修复emoji flag识别 + 域名fallback + sni支持
    server: 可选，节点server字段，用于从域名后缀反推地区（如 .kr/.sg/.vn）
    sni: 可选，节点sni字段，用于从域名后缀反推地区（优先级高于server）
    """
    nl = name.lower()
    # v25 FIX: Regional Indicator emoji flag (如🇭🇰) 由两个U+1F1Ex字符组成
    # 当后接数字时(🇭🇰1)，re.split无法拆开，导致二字母匹配全部失败
    # 修复：先去除Regional Indicator字符对，再用普通分隔符分词
    nl_no_flag = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', '', nl)
    tokens = set(re.split(r'[\s\-_|,.:;/()（）【】\[\]{}]+', nl_no_flag))

    # 辅助函数：区分真正的二字母ASCII代码 vs emoji/多字符
    def match(keywords):
        for k in keywords:
            if len(k) == 2 and k.isalpha() and k.isascii():
                if k in tokens:
                    return True
            else:
                if k in nl:
                    return True
        return False

    # 香港检测
    if match(["hk", "hongkong", "港", "hong kong", "🇭🇰", "香港", "深港", "沪港", "京港"]):
        return "🇭🇰", "HK"
    # 台湾检测
    elif match(["tw", "taiwan", "台", "🇹🇼", "台湾", "臺灣", "台北", "台中", "新北", "taipei"]):
        return "🇹🇼", "TW"
    # 日本检测
    elif match(["jp", "japan", "🇯🇵", "日本", "东京", "大阪", "tokyo", "osaka", "川日", "泉日", "埼玉"]):
        return "🇯🇵", "JP"
    # 新加坡检测
    elif match(["sg", "singapore", "🇸🇬", "新加坡", "狮城", "沪新", "京新", "深新"]):
        return "🇸🇬", "SG"
    # 韩国检测
    elif match(["kr", "korea", "韩", "🇰🇷", "韩国", "韓", "首尔", "春川", "seoul"]):
        return "🇰🇷", "KR"
    # 美国检测
    elif match(["us", "usa", "🇺🇸", "美国", "美利坚", "洛杉矶", "硅谷", "纽约",
                "united states", "america", "los angeles", "new york"]):
        return "🇺🇸", "US"
    # 英国检测
    elif match(["uk", "britain", "🇬🇧", "英国", "伦敦", "united kingdom", "london", "england"]):
        return "🇬🇧", "UK"
    # 德国检测
    elif match(["de", "germany", "🇩🇪", "德国", "法兰克福", "frankfurt", "berlin"]):
        return "🇩🇪", "DE"
    # 法国检测
    elif match(["fr", "france", "🇫🇷", "法国", "巴黎", "paris"]):
        return "🇫🇷", "FR"
    # 加拿大检测
    elif match(["ca", "canada", "🇨🇦", "加拿大", "渥太华", "多伦多", "toronto", "vancouver"]):
        return "🇨🇦", "CA"
    # 澳大利亚检测
    elif match(["au", "australia", "🇦🇺", "澳大利亚", "澳洲", "悉尼", "sydney", "melbourne"]):
        return "🇦🇺", "AU"
    # 荷兰检测
    elif match(["nl", "netherlands", "🇳🇱", "荷兰", "阿姆斯特丹", "amsterdam"]):
        return "🇳🇱", "NL"
    # 俄罗斯检测
    elif match(["ru", "russia", "🇷🇺", "俄罗斯", "莫斯科", "moscow"]):
        return "🇷🇺", "RU"
    # 印度检测（v28.20: 修复 "in" 误匹配，改用更严格边界检查）
    elif match(["india", "🇮🇳", "印度", "孟买", "mumbai", "delhi", "new delhi"]) or re.search(r'\b(india|ind|in-)\b', nl):
        return "🇮🇳", "IN"
    # 巴西检测
    elif match(["br", "brazil", "🇧🇷", "巴西", "圣保罗", "sao paulo"]):
        return "🇧🇷", "BR"
    # 阿根廷检测
    elif match(["ar", "argentina", "🇦🇷", "阿根廷", "buenos aires"]):
        return "🇦🇷", "AR"
    # 泰国检测
    elif match(["th", "thailand", "🇹🇭", "泰国", "曼谷", "bangkok"]):
        return "🇹🇭", "TH"
    # 越南检测
    elif match(["vn", "vietnam", "🇻🇳", "越南", "胡志明", "hanoi"]):
        return "🇻🇳", "VN"
    # 马来西亚检测
    elif match(["my", "malaysia", "🇲🇾", "马来西亚", "吉隆坡", "kuala lumpur"]):
        return "🇲🇾", "MY"
    # 菲律宾检测
    elif match(["ph", "philippines", "菲", "🇵🇭", "菲律宾", "马尼拉", "manila"]):
        return "🇵🇭", "PH"
    # 印尼检测
    elif match(["id", "indonesia", "印尼", "🇮🇩", "雅加达", "jakarta"]):
        return "🇮🇩", "ID"
    # 澳门检测 (v28.16)
    elif match(["mo", "macau", "macao", "🇲🇴", "澳门"]):
        return "🇲🇴", "MO"
    # 蒙古检测 (v28.16)
    elif match(["mn", "mongolia", "🇲🇳", "蒙古", "乌兰巴托", "ulaanbaatar"]):
        return "🇲🇳", "MN"
    # 柬埔寨检测 (v28.16)
    elif match(["kh", "cambodia", "🇰🇭", "柬埔寨", "金边", "phnom penh"]):
        return "🇰🇭", "KH"
    # 老挝检测 (v28.16)
    elif match(["laos", "🇱🇦", "老挝", "万象", "vientiane"]) or re.search(r"\blaos\b", nl):
        return "🇱🇦", "LA"
    # 缅甸检测 (v28.16)
    elif match(["mm", "myanmar", "🇲🇲", "缅甸", "仰光", "yangon"]):
        return "🇲🇲", "MM"
    # 文莱检测 (v28.16)
    elif match(["bn", "brunei", "🇧🇳", "文莱"]):
        return "🇧🇳", "BN"
    # 尼泊尔检测 (v28.16)
    elif match(["np", "nepal", "🇳🇵", "尼泊尔", "加德满都", "kathmandu"]):
        return "🇳🇵", "NP"
    # 斯里兰卡检测 (v28.16)
    elif match(["lk", "sri lanka", "🇱🇰", "斯里兰卡", "科伦坡", "colombo"]):
        return "🇱🇰", "LK"
    # 孟加拉检测 (v28.16)
    elif match(["bd", "bangladesh", "🇧🇩", "孟加拉", "达卡", "dhaka"]):
        return "🇧🇩", "BD"
    # 墨西哥检测
    elif match(["mx", "mexico", "墨", "🇲🇽", "墨西哥"]):
        return "🇲🇽", "MX"
    # 意大利检测
    elif match(["it", "italy", "🇮🇹", "意大利", "米兰", "罗马", "milan", "rome"]):
        return "🇮🇹", "IT"
    # 西班牙检测
    elif match(["es", "spain", "🇪🇸", "西班牙", "马德里", "madrid"]):
        return "🇪🇸", "ES"
    # 瑞士检测
    elif match(["ch", "switzerland", "🇨🇭", "瑞士", "苏黎世", "zurich"]):
        return "🇨🇭", "CH"
    # 奥地利检测
    elif match(["at", "austria", "🇦🇹", "奥地利", "维也纳", "vienna"]):
        return "🇦🇹", "AT"
    # 瑞典检测
    elif match(["se", "sweden", "瑞典", "🇸🇪", "斯德哥尔摩", "stockholm"]):
        return "🇸🇪", "SE"
    # 波兰检测
    elif match(["pl", "poland", "🇵🇱", "波兰", "华沙", "warsaw"]):
        return "🇵🇱", "PL"
    # 土耳其检测
    elif match(["tr", "turkey", "🇹🇷", "土耳其", "伊斯坦布尔", "istanbul"]):
        return "🇹🇷", "TR"
    # 南非检测
    elif match(["za", "south africa", "南非", "🇿🇦", "约翰内斯堡", "johannesburg"]):
        return "🇿🇦", "ZA"
    # 阿联酋检测
    elif match(["ae", "uae", "迪", "🇦🇪", "阿联酋", "迪拜", "dubai", "abu dhabi"]):
        return "🇦🇪", "AE"
    # 以色列检测
    elif match(["il", "israel", "以", "🇮🇱", "以色列", "特拉维夫", "tel aviv"]):
        return "🇮🇱", "IL"
    # 爱尔兰检测
    elif match(["ie", "ireland", "爱尔兰", "🇮🇪", "都柏林", "dublin"]):
        return "🇮🇪", "IE"
    # 葡萄牙检测
    elif match(["pt", "portugal", "葡", "🇵🇹", "葡萄牙", "里斯本", "lisbon"]):
        return "🇵🇹", "PT"
    # 捷克检测
    elif match(["cz", "czech", "捷", "🇨🇿", "捷克", "布拉格", "prague"]):
        return "🇨🇿", "CZ"
    # 罗马尼亚检测
    elif match(["ro", "romania", "罗", "🇷🇴", "罗马尼亚", "布加勒斯特", "bucharest"]):
        return "🇷🇴", "RO"
    # 匈牙利检测
    elif match(["hu", "hungary", "匈", "🇭🇺", "匈牙利", "布达佩斯", "budapest"]):
        return "🇭🇺", "HU"
    # 希腊检测
    elif match(["gr", "greece", "希", "🇬🇷", "希腊", "雅典", "athens"]):
        return "🇬🇷", "GR"
    # 芬兰检测
    elif match(["fi", "finland", "芬", "🇫🇮", "芬兰", "赫尔辛基", "helsinki"]):
        return "🇫🇮", "FI"
    # 丹麦检测
    elif match(["dk", "denmark", "丹", "🇩🇰", "丹麦", "哥本哈根", "copenhagen"]):
        return "🇩🇰", "DK"
    # 挪威检测
    elif match(["no", "norway", "挪", "🇳🇴", "挪威", "奥斯陆", "oslo"]):
        return "🇳🇴", "NO"
    # 比利时检测
    elif match(["be", "belgium", "比", "🇧🇪", "比利时", "布鲁塞尔", "brussels"]):
        return "🇧🇪", "BE"
    # 新西兰检测
    elif match(["nz", "new zealand", "新西兰", "🇳🇿", "奥克兰", "auckland"]):
        return "🇳🇿", "NZ"
    # 智利检测
    elif match(["cl", "chile", "🇨🇱", "智利", "圣地亚哥", "santiago"]):
        return "🇨🇱", "CL"
    # 哥伦比亚检测
    elif match(["co", "colombia", "🇨🇴", "哥伦比亚", "波哥大", "bogota"]):
        return "🇨🇴", "CO"
    # 秘鲁检测
    elif match(["pe", "peru", "🇵🇪", "秘鲁", "利马", "lima"]):
        return "🇵🇪", "PE"
    # 乌克兰检测
    elif match(["ua", "ukraine", "🇺🇦", "乌克兰", "基辅", "kiev", "kyiv"]):
        return "🇺🇦", "UA"
    # 哈萨克斯坦检测
    elif match(["kz", "kazakhstan", "哈", "🇰🇿", "哈萨克斯坦", "阿拉木图", "almaty"]):
        return "🇰🇿", "KZ"

    # 默认处理：无法识别地区，尝试基于 server 推测，否则给个合理的默认
    # 尝试匹配常见的通用模式
    if match(["private", "vpn", "proxy", "network"]):
        return "[WEB]", "NET"  # 网络通用

    # v27 FIX: 移除数字检查限制，对所有节点都尝试从域名后缀反推
    # 优先检查 sni（通常是CDN域名，含更多信息），再检查 server
    hosts_to_check = []
    if sni:
        hosts_to_check.append(sni.lower())
    if server:
        hosts_to_check.append(server.lower())

    for srv in hosts_to_check:
        # 从右向左取最后两个部分做模糊匹配
        parts = srv.split(".")
        for i in range(max(0, len(parts) - 2), len(parts)):
            seg = ".".join(parts[i:])
            # TLD/常见域名后缀 → 国家/地区
            if seg.endswith(".kr") or ".co.kr" in srv:
                return "🇰🇷", "KR"
            if seg.endswith(".sg") or ".com.sg" in srv or ".net.sg" in srv:
                return "🇸🇬", "SG"
            if seg.endswith(".vn") or ".com.vn" in srv:
                return "🇻🇳", "VN"
            if seg.endswith(".th") or ".co.th" in srv:
                return "🇹🇭", "TH"
            if seg.endswith(".my") or ".com.my" in srv:
                return "🇲🇾", "MY"
            if seg.endswith(".id") or ".co.id" in srv or ".or.id" in srv:
                return "🇮🇩", "ID"
            if seg.endswith(".ph") or ".com.ph" in srv:
                return "🇵🇭", "PH"
            if seg.endswith(".jp") or ".co.jp" in srv or ".ne.jp" in srv:
                return "🇯🇵", "JP"
            if seg.endswith(".hk") or ".com.hk" in srv or ".net.hk" in srv:
                return "🇭🇰", "HK"
            if seg.endswith(".tw") or ".com.tw" in srv or ".net.tw" in srv:
                return "🇹🇼", "TW"
            if seg.endswith(".au") or ".com.au" in srv:
                return "🇦🇺", "AU"
            if srv.endswith(".uk") or srv.endswith(".co.uk"):
                return "🇬🇧", "UK"
            if seg.endswith(".de") or ".co.de" in srv:
                return "🇩🇪", "DE"
            if seg.endswith(".fr") or ".co.fr" in srv:
                return "🇫🇷", "FR"
            if seg.endswith(".nl") or ".co.nl" in srv:
                return "🇳🇱", "NL"
            if seg.endswith(".ru") or ".co.ru" in srv:
                return "🇷🇺", "RU"
            if seg.endswith(".us") or ".com.us" in srv:
                return "🇺🇸", "US"
            if seg.endswith(".br") or ".com.br" in srv:
                return "🇧🇷", "BR"
            if seg.endswith(".ca") or ".co.ca" in srv:
                return "🇨🇦", "CA"
            if seg.endswith(".in") or ".co.in" in srv or ".net.in" in srv:
                return "🇮🇳", "IN"
            if seg.endswith(".it") or ".co.it" in srv:
                return "🇮🇹", "IT"
            if seg.endswith(".es") or ".co.es" in srv:
                return "🇪🇸", "ES"
            # v28.16: 补充亚洲区域TLD
            if seg.endswith(".mo") or ".com.mo" in srv:
                return "🇲🇴", "MO"
            if seg.endswith(".mn") or ".com.mn" in srv:
                return "🇲🇳", "MN"
            if seg.endswith(".kh") or ".com.kh" in srv:
                return "🇰🇭", "KH"
            if seg.endswith(".la") or ".com.la" in srv:
                return "🇱🇦", "LA"
            if seg.endswith(".mm") or ".com.mm" in srv:
                return "🇲🇲", "MM"
            if seg.endswith(".bn") or ".com.bn" in srv:
                return "🇧🇳", "BN"
            if seg.endswith(".tl") or ".com.tl" in srv:
                return "🇹🇱", "TL"
            if seg.endswith(".np") or ".com.np" in srv:
                return "🇳🇵", "NP"
            if seg.endswith(".lk") or ".com.lk" in srv:
                return "🇱🇰", "LK"
            if seg.endswith(".bd") or ".com.bd" in srv:
                return "🇧🇩", "BD"
            if seg.endswith(".bt") or ".com.bt" in srv:
                return "🇧🇹", "BT"
            if seg.endswith(".mv") or ".com.mv" in srv:
                return "🇲🇻", "MV"
            if seg.endswith(".tr") or ".com.tr" in srv:
                return "🇹🇷", "TR"
            if seg.endswith(".pl") or ".co.pl" in srv:
                return "🇵🇱", "PL"
            if seg.endswith(".cz") or ".co.cz" in srv:
                return "🇨🇿", "CZ"
            if seg.endswith(".ar") or ".com.ar" in srv:
                return "🇦🇷", "AR"
            # BUGFIX v28.13: 严格限制 .cl 匹配，避免与 .co 混淆
            # 智利 ccTLD: .cl, .co.cl
            if srv.endswith(".cl") and not srv.endswith(".co.cl"):
                return "🇨🇱", "CL"
            # 哥伦比亚 ccTLD: .com.co, .org.co, .net.co
            if srv.endswith(".com.co") or srv.endswith(".org.co") or srv.endswith(".net.co"):
                return "🇨🇴", "CO"
            if seg.endswith(".mx") or ".com.mx" in srv:
                return "🇲🇽", "MX"
            if seg.endswith(".ae") or ".co.ae" in srv:
                return "🇦🇪", "AE"
            if seg.endswith(".il") or ".co.il" in srv:
                return "🇮🇱", "IL"
            if seg.endswith(".ie") or ".co.ie" in srv:
                return "🇮🇪", "IE"
            if seg.endswith(".nz") or ".co.nz" in srv:
                return "🇳🇿", "NZ"
            if seg.endswith(".ch") or ".co.ch" in srv:
                return "🇨🇭", "CH"
            if seg.endswith(".at") or ".co.at" in srv:
                return "🇦🇹", "AT"
            if seg.endswith(".se") or ".co.se" in srv:
                return "🇸🇪", "SE"
            if seg.endswith(".pt") or ".com.pt" in srv:
                return "🇵🇹", "PT"
            if seg.endswith(".ro") or ".co.ro" in srv:
                return "🇷🇴", "RO"
            if seg.endswith(".hu") or ".co.hu" in srv:
                return "🇭🇺", "HU"
            if seg.endswith(".fi") or ".co.fi" in srv:
                return "🇫🇮", "FI"
            if seg.endswith(".dk") or ".co.dk" in srv:
                return "🇩🇰", "DK"
            if seg.endswith(".no") or ".co.no" in srv:
                return "🇳🇴", "NO"
            if seg.endswith(".be") or ".co.be" in srv:
                return "🇧🇪", "BE"
            if seg.endswith(".za") or ".co.za" in srv:
                return "🇿🇦", "ZA"
            if seg.endswith(".kz") or ".co.kz" in srv:
                return "🇰🇿", "KZ"
            if seg.endswith(".ua") or ".com.ua" in srv:
                return "🇺🇦", "UA"
            if seg.endswith(".bg") or ".co.bg" in srv:
                return "🇧🇬", "BG"
            if seg.endswith(".gr") or ".co.gr" in srv:
                return "🇬🇷", "GR"
            # v27: 新增更多国家后缀
            if seg.endswith(".ir") or ".co.ir" in srv:
                return "🇮🇷", "IR"
            if seg.endswith(".pk") or ".com.pk" in srv:
                return "🇵🇰", "PK"
            if seg.endswith(".bd") or ".com.bd" in srv:
                return "🇧🇩", "BD"
            if seg.endswith(".ng") or ".com.ng" in srv:
                return "🇳🇬", "NG"
            if seg.endswith(".eg") or ".com.eg" in srv:
                return "🇪🇬", "EG"
            if seg.endswith(".ke") or ".co.ke" in srv:
                return "🇰🇪", "KE"
            # v28.13: 哥伦比亚检测已移至上方 .cl 检测之后
            if seg.endswith(".pe") or ".com.pe" in srv:
                return "🇵🇪", "PE"
            if seg.endswith(".ve") or ".com.ve" in srv:
                return "🇻🇪", "VE"
            if seg.endswith(".ec") or ".com.ec" in srv:
                return "🇪🇨", "EC"

    # v28.5 FIX: IP 地理位置 fallback
    # BUGFIX v28.39: 使用 _get_limiter() 延迟导入，避免循环依赖
    if is_pure_ip(server):
        try:
            limiter = _get_limiter()
            geo = limiter.get_geo(server)
            if geo:
                cc = geo.get("countryCode", "").upper()
                if cc:
                    flag = _cc_to_flag(cc)
                    return flag, cc
        except (ImportError, AttributeError):
            logging.debug("Limiter not ready, skipping geo lookup")  # limiter 未就绪时跳过
    if sni and not is_pure_ip(sni):
        pass  # SNI 域名已在上面 TLD 匹配中处理过

    return "[WEB]", "NET"
