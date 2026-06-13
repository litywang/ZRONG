# sources/config.py - ZRONG 配置统一访问层
# v28.99 Phase A fix: 替换 sys.modules hack，直接从 config.constants 读取
# 解决运行时循环导入问题，sources 模块不再依赖 crawler.py

from typing import Any, Dict, List, Optional
import logging

# 直接从 constants 读取运行时值（crawler.py 加载 sources.yaml 后会更新这些变量）
from config import constants as _const

# ==================== 模块级变量（同步自 constants）====================
# v28.67: 保留模块级变量赋值，init_config() 后更新
# v28.99: init_config() → _refresh_from_constants()
TELEGRAM_CHANNELS: List = []
CANDIDATE_URLS: List = []
MAX_FETCH_NODES: int = 5000
FETCH_WORKERS: int = 150
MAX_TCP_TEST_NODES: int = 500
MAX_LATENCY: int = 800
MAX_PROXY_TEST_NODES: int = 1000
MAX_FINAL_NODES: int = 120
MAX_PROXY_LATENCY: int = 1500
TEST_URL: str = 'https://myip.ipip.net/json'
TARGET_ASIA_RATIO: float = 0.60
ASIA_TCP_RELAX: int = 1800
ASIA_MIN_COUNT: int = 60
BOT_TOKEN: str = ''
CHAT_ID: str = ''
REPO_NAME: str = 'user/repo'
GITHUB_TOKEN: str = ''
GITHUB_BASE_REPOS: List = []
MAX_WORKERS: int = 80
SUB_MIRRORS: List = []
USER_AGENT_POOL: List = []
HEADERS_POOL: List = [{}]
TIMEOUT: int = 12
MAX_FORK_REPOS: int = 60
MAX_FORK_URLS: int = 1500
MAX_CONCURRENT_FETCH: int = 3
MAX_CONCURRENT_TCP: int = 60


def _refresh_from_constants() -> None:
    """从 config.constants 同步最新值到模块级变量"""
    global TELEGRAM_CHANNELS, CANDIDATE_URLS, MAX_FETCH_NODES, FETCH_WORKERS
    global MAX_TCP_TEST_NODES, MAX_LATENCY, MAX_PROXY_TEST_NODES
    global MAX_FINAL_NODES, MAX_PROXY_LATENCY, TEST_URL, TARGET_ASIA_RATIO
    global ASIA_TCP_RELAX, ASIA_MIN_COUNT, BOT_TOKEN, CHAT_ID, REPO_NAME
    global GITHUB_TOKEN, GITHUB_BASE_REPOS, MAX_WORKERS
    global SUB_MIRRORS, USER_AGENT_POOL, HEADERS_POOL, TIMEOUT
    global MAX_FORK_REPOS, MAX_FORK_URLS, MAX_CONCURRENT_FETCH, MAX_CONCURRENT_TCP

    TELEGRAM_CHANNELS = _const.TELEGRAM_CHANNELS
    CANDIDATE_URLS = _const.CANDIDATE_URLS
    MAX_FETCH_NODES = _const.MAX_FETCH_NODES
    FETCH_WORKERS = _const.FETCH_WORKERS
    MAX_TCP_TEST_NODES = _const.MAX_TCP_TEST_NODES
    MAX_LATENCY = _const.MAX_LATENCY
    MAX_PROXY_TEST_NODES = _const.MAX_PROXY_TEST_NODES
    MAX_FINAL_NODES = _const.MAX_FINAL_NODES
    MAX_PROXY_LATENCY = _const.MAX_PROXY_LATENCY
    TEST_URL = _const.TEST_URL
    TARGET_ASIA_RATIO = _const.TARGET_ASIA_RATIO
    ASIA_TCP_RELAX = _const.ASIA_TCP_RELAX
    ASIA_MIN_COUNT = _const.ASIA_MIN_COUNT
    BOT_TOKEN = _const.BOT_TOKEN
    CHAT_ID = _const.CHAT_ID
    REPO_NAME = _const.REPO_NAME
    GITHUB_TOKEN = _const.GITHUB_TOKEN
    GITHUB_BASE_REPOS = _const.GITHUB_BASE_REPOS
    MAX_WORKERS = _const.MAX_WORKERS
    SUB_MIRRORS = _const.SUB_MIRRORS
    USER_AGENT_POOL = _const.USER_AGENT_POOL
    HEADERS_POOL = _const.HEADERS_POOL
    TIMEOUT = _const.TIMEOUT
    MAX_FORK_REPOS = _const.MAX_FORK_REPOS
    MAX_FORK_URLS = _const.MAX_FORK_URLS
    MAX_CONCURRENT_FETCH = _const.MAX_CONCURRENT_FETCH
    MAX_CONCURRENT_TCP = _const.MAX_CONCURRENT_TCP


def init_config() -> None:
    """初始化配置（main() 调用一次，同步 constants 最新值）"""
    _refresh_from_constants()
    logging.debug(
        f"[sources.config] init: {len(CANDIDATE_URLS)} urls, "
        f"{len(TELEGRAM_CHANNELS)} tg channels, MAX_FINAL_NODES={MAX_FINAL_NODES}"
    )


# ==================== 访问器函数 =====================
def session_fn():
    from core.config import session as _s
    return _s

def get_http_client_fn():
    from network.client import get_http_client as _c
    return _c()

def get_async_http_client_fn():
    from network.client import get_async_http_client as _c
    return _c()

def limiter_fn():
    from network.geo import limiter as _l
    return _l

def parse_node_fn():
    from parsers import parse_node as _p
    return _p

def ProxyNode_fn():
    from parsers.proxynode import ProxyNode as _P
    return _P

def config_fn() -> Dict[str, Any]:
    """返回配置字典（供调试使用）"""
    _refresh_from_constants()
    return {k: getattr(_const, k, None) for k in dir(_const) if not k.startswith('_')}

def dynamic_source_weight_fn(url: str) -> float:
    from core.history import dynamic_source_weight as _dsw
    return _dsw(url)

def is_asia_fn(node: dict) -> bool:
    from core.validator import is_asia as _ia
    return _ia(node)


def dynamic_source_weight_cls():
    """返回函数本身（不是调用结果），供 subscription.py 使用"""
    from core.history import dynamic_source_weight as _dsw
    return _dsw


def is_asia_cls():
    """返回函数本身（不是调用结果），供 subscription.py 使用"""
    from core.validator import is_asia as _ia
    return _ia

def async_http_client_fn():
    from network.client import get_async_http_client as _c
    return _c()


# ==================== 函数式访问器（_fn 后缀，subscription/telegram 依赖）====================
# 规则：变量名与函数名不可同名（Python 模块级变量遮蔽函数），
# 所以所有函数统一加 _fn 后缀，避免 subscription.py / telegram.py 调用时报 TypeError
def GITHUB_TOKEN_fn() -> str:
    return _const.GITHUB_TOKEN

def MAX_WORKERS_fn() -> int:
    return _const.MAX_WORKERS

def SUB_MIRRORS_fn() -> List:
    return _const.SUB_MIRRORS

def HEADERS_POOL_fn() -> List[Dict]:
    return _const.HEADERS_POOL

def TIMEOUT_fn() -> int:
    return _const.TIMEOUT

def MAX_FETCH_NODES_fn() -> int:
    return _const.MAX_FETCH_NODES

def FETCH_WORKERS_fn() -> int:
    return _const.FETCH_WORKERS

def MAX_FORK_REPOS_fn() -> int:
    return _const.MAX_FORK_REPOS

def MAX_FORK_URLS_fn() -> int:
    return _const.MAX_FORK_URLS

def GITHUB_BASE_REPOS_fn() -> List[str]:
    return _const.GITHUB_BASE_REPOS

def USER_AGENT_POOL_fn() -> List[str]:
    return _const.USER_AGENT_POOL

def MAX_FINAL_NODES_fn() -> int:
    return _const.MAX_FINAL_NODES

def MAX_PROXY_LATENCY_fn() -> int:
    return _const.MAX_PROXY_LATENCY

def TEST_URL_fn() -> str:
    return _const.TEST_URL

def TARGET_ASIA_RATIO_fn() -> float:
    return _const.TARGET_ASIA_RATIO

def ASIA_TCP_RELAX_fn() -> int:
    return _const.ASIA_TCP_RELAX

def ASIA_MIN_COUNT_fn() -> int:
    return _const.ASIA_MIN_COUNT

def BOT_TOKEN_fn() -> str:
    return _const.BOT_TOKEN

def CHAT_ID_fn() -> str:
    return _const.CHAT_ID

def REPO_NAME_fn() -> str:
    return _const.REPO_NAME

def MAX_CONCURRENT_FETCH_fn() -> int:
    return _const.MAX_CONCURRENT_FETCH

def MAX_CONCURRENT_TCP_fn() -> int:
    return _const.MAX_CONCURRENT_TCP


# ===== URL 健康检查（v30.0） =====
_URL_HEALTH_CACHE: dict = {}  # url -> (ok, timestamp)


def is_url_healthy(url: str, timeout: float = 3.0) -> bool:
    """快速检查 URL 是否可达（HEAD 请求，3s 超时）
    
    使用内存缓存（5 分钟有效期），避免重复探测。
    主要用于在批量抓取前过滤明显不可达的 URL。
    """
    import time as _t
    now = _t.time()
    cached = _URL_HEALTH_CACHE.get(url)
    if cached and (now - cached[1]) < 300:  # 5分钟缓存
        return cached[0]
    
    try:
        sess = session_fn()
        resp = sess.head(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        ok = resp.status_code in (200, 301, 302, 304)
    except Exception:
        ok = False
    
    _URL_HEALTH_CACHE[url] = (ok, now)
    return ok
