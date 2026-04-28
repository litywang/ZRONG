"""分析 sources.yaml 中各源的历史亚洲节点产出率"""
import yaml
import re

with open('sources.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

urls = data.get('candidate_urls', [])
tg_channels = data.get('telegram_channels', [])

logging.debug("=" * 60)
logging.debug("当前源配置分析")
logging.debug("=" * 60)
logging.debug(f"\n固定URL源: {len(urls)} 个")
logging.debug(f"Telegram频道: {len(tg_channels)} 个")
logging.debug(f"GitHub Repos: {len(data.get('github_repos', []))} 个")

# 分析URL源的地区特征
asia_keywords = ['hk', 'tw', 'jp', 'sg', 'kr', 'asia', 'hongkong', 'taiwan', 'japan', 
                 'singapore', 'korea', 'cn', 'china', '中国', '港', '台', '日', '新加坡', '韩']

asia_sources = []
unknown_sources = []

for url in urls:
    url_lower = url.lower()
    if any(kw in url_lower for kw in asia_keywords):
        asia_sources.append(url)
    else:
        unknown_sources.append(url)

logging.debug(f"\n含亚洲关键词的源: {len(asia_sources)} 个")
logging.debug(f"无明显地区特征的源: {len(unknown_sources)} 个")

logging.debug("\n" + "=" * 60)
logging.debug("建议添加的亚洲优质源")
logging.debug("=" * 60)

# 推荐的亚洲节点源
recommended = [
    # 香港/台湾/日本/新加坡专用源
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/hk.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/jp.txt", 
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/sg.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/tw.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/main/sub/splitted/kr.txt",
    
    # 中国大陆优化源
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/quick/4/config.yaml",
    "https://raw.githubusercontent.com/Alvin9999/pac2/master/quick/1/config.yaml",
    "https://raw.githubusercontent.com/wrfree/free/main/README.md",
    
    # 亚洲混合源
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/kxswa/v2rayfree/main/v2ray",
    "https://raw.githubusercontent.com/llywhn/v2ray-subscribe/main/v2ray.txt",
    "https://raw.githubusercontent.com/adiwzx/freenode/main/v2ray.txt",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
]

logging.debug(f"\n推荐源数量: {len(recommended)} 个")
for url in recommended[:10]:
    logging.debug(f"  - {url}")
