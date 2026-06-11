# config/constants.py - ZRONG 全局配置常量
# v28.99: 重构 Phase A — 将所有 os.getenv 常量统一收纳
# 所有模块统一从本文件导入，避免 crawler.py 的全局变量膨胀
import os

# ==================== 环境编码 ====================
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ==================== HTTP 客户端 ====================
TIMEOUT = int(os.getenv("TIMEOUT", "12"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "80"))
FETCH_WORKERS = int(os.getenv("FETCH_WORKERS", "150"))
MAX_CONCURRENT_FETCH = 3
MAX_CONCURRENT_TCP = 60
HEADERS_POOL = [{"User-Agent": "ZRONG/28.x"}]

# ==================== 来源配置 ====================
CANDIDATE_URLS = []
TELEGRAM_CHANNELS = []
GITHUB_BASE_REPOS = []

# ==================== 采集限制 ====================
MAX_FETCH_NODES = int(os.getenv("MAX_FETCH_NODES", "5000"))
MAX_TCP_TEST_NODES = int(os.getenv("MAX_TCP_TEST_NODES", "1200"))
MAX_PROXY_TEST_NODES = int(os.getenv("MAX_PROXY_TEST_NODES", "1000"))
MAX_FINAL_NODES = int(os.getenv("MAX_FINAL_NODES", "150"))

# ==================== 延迟阈值 ====================
MAX_LATENCY = int(os.getenv("MAX_LATENCY", "5000"))
MIN_PROXY_SPEED = float(os.getenv("MIN_PROXY_SPEED", "30"))
MAX_PROXY_LATENCY = int(os.getenv("MAX_PROXY_LATENCY", "5000"))
ASIA_TCP_RELAX = 1800

# ==================== 测速 URL ====================
TEST_URL = "https://myip.ipip.net/json"
MAINLAND_TEST_URLS = [
    "http://beian.miit.gov.cn",
    "http://www.ccgp.gov.cn",
    "http://www.pbccrc.org.cn",
    "http://www.baidu.com",
    "http://www.qq.com",
    "http://www.taobao.com",
    "http://114.114.114.114/resolve?name=www.baidu.com&type=A",
]

# ==================== 大陆友好评分 ====================
MAINLAND_SCORE_THRESHOLD = int(os.getenv("MAINLAND_SCORE_THRESHOLD", "30"))
MAINLAND_PASS_BONUS = int(os.getenv("MAINLAND_PASS_BONUS", "20"))

# ==================== 亚洲配额 ====================
ASIA_PRIORITY_BONUS = int(os.getenv("ASIA_PRIORITY_BONUS", "30"))
TARGET_ASIA_RATIO = float(os.getenv("TARGET_ASIA_RATIO", "0.60"))
ASIA_MIN_COUNT = int(os.getenv("ASIA_MIN_COUNT", "60"))

# ==================== GitHub ====================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "dc87627768298a4f6af8281cad97dfa3")
MAX_FORK_REPOS = int(os.getenv("MAX_FORK_REPOS", "60"))
MAX_FORK_URLS = 1500

# ==================== Telegram ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# ==================== GitHub Actions ====================
REPO_NAME = os.getenv("GITHUB_REPOSITORY", "user/repo")

# ==================== 订阅镜像 ====================
SUB_MIRRORS = [
    "https://gh.llkk.cc/",
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://raw.iqiq.io/",
    "https://gh.api.99988866.xyz/",
    "https://ghps.cc/",
    "https://ghfast.top/",
]

# ==================== 节点命名 ====================
NODE_NAME_PREFIX = "Anftlity"

# ==================== 端口评分 ====================
HIGH_PORT_BONUS_THRESHOLD = 10000
COMMON_PORT_PENALTY = {80: 300, 443: 200, 8080: 100, 8443: 100}

# ==================== User-Agent ====================
USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Android 11; Mobile; rv:84.0) Gecko/84.0 Firefox/84.0",
]

# ==================== CN IP 数据 ====================
# 由 gen_cn_cidr.py 自动生成，存放在 cn_cidr_data.py 中
# 导入时由 crawler.py 从 cn_cidr_data.py 加载
CN_IP_RANGES = []
