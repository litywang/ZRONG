# sources/config.py - 统一配置访问层
# v28.53: 替换 sys.modules hack，提供类型安全的配置访问
# 所有 sources 模块的函数从这里获取 crawler 状态

from typing import Any, Dict, List, Optional, Tuple

_config: Optional[Dict[str, Any]] = None


def init_config() -> None:
    """由 crawler.py main() 调用，注入全局配置"""
    import crawler as cr
    global _config
    _config = {
        # HTTP 客户端
        'session': cr.session,
        'get_http_client': cr.get_http_client,
        'get_async_http_client': cr.get_async_http_client,
        # 限流器
        'limiter': getattr(cr, 'limiter', None),
        # 解析器
        'parse_node': cr.parse_node,
        'ProxyNode': cr.ProxyNode,
        # 配置常量
        'TIMEOUT': getattr(cr, 'TIMEOUT', 12),
        'MAX_WORKERS': getattr(cr, 'MAX_WORKERS', 80),
        'USER_AGENT_POOL': getattr(cr, 'USER_AGENT_POOL', []),
        'HEADERS_POOL': getattr(cr, 'HEADERS_POOL', [{}]),
        'SUB_MIRRORS': getattr(cr, 'SUB_MIRRORS', []),
        'MAX_FETCH_NODES': getattr(cr, 'MAX_FETCH_NODES', 5000),
        'FETCH_WORKERS': getattr(cr, 'FETCH_WORKERS', 150),
        'GITHUB_TOKEN': getattr(cr, 'GITHUB_TOKEN', ''),
        'MAX_FORK_REPOS': getattr(cr, 'MAX_FORK_REPOS', 60),
        'MAX_FORK_URLS': getattr(cr, 'MAX_FORK_URLS', 1500),
        'GITHUB_BASE_REPOS': getattr(cr, 'GITHUB_BASE_REPOS', []),
        # v28.67: 新增配置项
        'TELEGRAM_CHANNELS': getattr(cr, 'TELEGRAM_CHANNELS', []),
        'CANDIDATE_URLS': getattr(cr, 'CANDIDATE_URLS', []),
        'MAX_TCP_TEST_NODES': getattr(cr, 'MAX_TCP_TEST_NODES', 500),
        'MAX_LATENCY': getattr(cr, 'MAX_LATENCY', 800),
        'MAX_PROXY_TEST_NODES': getattr(cr, 'MAX_PROXY_TEST_NODES', 1000),
        'MAX_FINAL_NODES': getattr(cr, 'MAX_FINAL_NODES', 150),
        'MAX_PROXY_LATENCY': getattr(cr, 'MAX_PROXY_LATENCY', 5000),
        'TEST_URL': getattr(cr, 'TEST_URL', 'https://myip.ipip.net/json'),
        'TARGET_ASIA_RATIO': getattr(cr, 'TARGET_ASIA_RATIO', 0.60),
        'ASIA_TCP_RELAX': getattr(cr, 'ASIA_TCP_RELAX', 1800),
        'ASIA_MIN_COUNT': getattr(cr, 'ASIA_MIN_COUNT', 60),
        'BOT_TOKEN': getattr(cr, 'BOT_TOKEN', ''),
        'CHAT_ID': getattr(cr, 'CHAT_ID', ''),
        'REPO_NAME': getattr(cr, 'REPO_NAME', 'user/repo'),
        # 动态权重
        '_dynamic_source_weight': getattr(cr, '_dynamic_source_weight', None),
        'is_asia': getattr(cr, 'is_asia', None),
        # 异步客户端
        '_async_http_client': getattr(cr, '_async_http_client', None),
    }
    # v28.67: 更新模块级变量
    _update_module_vars()


def _check() -> Dict[str, Any]:
    if _config is None:
        raise RuntimeError(
            "sources.config 尚未初始化。请在 crawler.py main() 开始时调用 sources.config.init_config()"
        )
    return _config


def session():
    return _check()['session']


def get_http_client():
    return _check()['get_http_client']()


def get_async_http_client():
    return _check()['get_async_http_client']()


def limiter():
    return _check()['limiter']


def parse_node():
    return _check()['parse_node']


def ProxyNode():
    return _check()['ProxyNode']


def config() -> Dict[str, Any]:
    """返回完整配置 dict（用于批量访问）"""
    return _check()


def GITHUB_TOKEN() -> str:
    c = _check()
    return c.get('GITHUB_TOKEN', '')


def MAX_WORKERS() -> int:
    return _check().get('MAX_WORKERS', 80)


def SUB_MIRRORS() -> List[str]:
    return _check().get('SUB_MIRRORS', [])


def HEADERS_POOL() -> List[Dict]:
    return _check().get('HEADERS_POOL', [{}])


def TIMEOUT() -> int:
    return _check().get('TIMEOUT', 12)


def MAX_FETCH_NODES() -> int:
    return _check().get('MAX_FETCH_NODES', 5000)


def FETCH_WORKERS() -> int:
    return _check().get('FETCH_WORKERS', 150)


def MAX_FORK_REPOS() -> int:
    return _check().get('MAX_FORK_REPOS', 60)


def MAX_FORK_URLS() -> int:
    return _check().get('MAX_FORK_URLS', 1500)


def GITHUB_BASE_REPOS() -> List[str]:
    return _check().get('GITHUB_BASE_REPOS', [])


def USER_AGENT_POOL() -> List[str]:
    return _check().get('USER_AGENT_POOL', [])


def MAX_FINAL_NODES() -> int:
    return _check().get('MAX_FINAL_NODES', 200)


def MAX_PROXY_LATENCY() -> int:
    return _check().get('MAX_PROXY_LATENCY', 5000)


def TEST_URL() -> str:
    return _check().get('TEST_URL', 'https://myip.ipip.net/json')


def TARGET_ASIA_RATIO() -> float:
    return _check().get('TARGET_ASIA_RATIO', 0.60)


def ASIA_TCP_RELAX() -> int:
    return _check().get('ASIA_TCP_RELAX', 1800)


def ASIA_MIN_COUNT() -> int:
    return _check().get('ASIA_MIN_COUNT', 60)


def BOT_TOKEN() -> str:
    return _check().get('BOT_TOKEN', '')


def CHAT_ID() -> str:
    return _check().get('CHAT_ID', '')


def REPO_NAME() -> str:
    return _check().get('REPO_NAME', 'user/repo')


def dynamic_source_weight(url: str) -> float:
    c = _check()
    fn = c.get('_dynamic_source_weight')
    if fn:
        return fn(url)
    return 3.0


def is_asia(node: dict) -> bool:
    c = _check()
    fn = c.get('is_asia')
    if fn:
        return fn(node)
    return False


def async_http_client():
    return _check().get('_async_http_client')


# v28.67: 模块级变量，由 init_config() 设置
TELEGRAM_CHANNELS = []
CANDIDATE_URLS = []
MAX_FETCH_NODES = 5000
FETCH_WORKERS = 150
MAX_TCP_TEST_NODES = 500
MAX_LATENCY = 800
MAX_PROXY_TEST_NODES = 1000
MAX_FINAL_NODES = 150
MAX_PROXY_LATENCY = 5000
TEST_URL = 'https://myip.ipip.net/json'
TARGET_ASIA_RATIO = 0.60
ASIA_TCP_RELAX = 1800
ASIA_MIN_COUNT = 60
BOT_TOKEN = ''
CHAT_ID = ''
REPO_NAME = 'user/repo'


def _update_module_vars():
    """从 _config 更新模块级变量"""
    if _config is None:
        return
    global TELEGRAM_CHANNELS, CANDIDATE_URLS, MAX_FETCH_NODES, FETCH_WORKERS, MAX_TCP_TEST_NODES, MAX_LATENCY, MAX_PROXY_TEST_NODES
    global MAX_FINAL_NODES, MAX_PROXY_LATENCY, TEST_URL, TARGET_ASIA_RATIO
    global ASIA_TCP_RELAX, ASIA_MIN_COUNT, BOT_TOKEN, CHAT_ID, REPO_NAME
    TELEGRAM_CHANNELS = _config.get('TELEGRAM_CHANNELS', [])
    CANDIDATE_URLS = _config.get('CANDIDATE_URLS', [])
    MAX_FETCH_NODES = _config.get('MAX_FETCH_NODES', 5000)
    FETCH_WORKERS = _config.get('FETCH_WORKERS', 150)
    MAX_TCP_TEST_NODES = _config.get('MAX_TCP_TEST_NODES', 500)
    MAX_LATENCY = _config.get('MAX_LATENCY', 800)
    MAX_PROXY_TEST_NODES = _config.get('MAX_PROXY_TEST_NODES', 1000)
    MAX_FINAL_NODES = _config.get('MAX_FINAL_NODES', 150)
    MAX_PROXY_LATENCY = _config.get('MAX_PROXY_LATENCY', 5000)
    TEST_URL = _config.get('TEST_URL', 'https://myip.ipip.net/json')
    TARGET_ASIA_RATIO = _config.get('TARGET_ASIA_RATIO', 0.60)
    ASIA_TCP_RELAX = _config.get('ASIA_TCP_RELAX', 1800)
    ASIA_MIN_COUNT = _config.get('ASIA_MIN_COUNT', 60)
    BOT_TOKEN = _config.get('BOT_TOKEN', '')
    CHAT_ID = _config.get('CHAT_ID', '')
    REPO_NAME = _config.get('REPO_NAME', 'user/repo')
