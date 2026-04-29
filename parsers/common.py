# parsers/common.py - ProxyNode 转发层（v28.52）
# ProxyNode 定义在 crawler.py（Pydantic v2 BaseModel），此处重导出供所有解析器导入
# 避免循环导入：crawler.py 先通过 parsers/__init__.py 导入解析器，
# 解析器再从 parsers.common 间接引用 ProxyNode（延迟到 crawler 模块加载后）

import sys

_crawler = sys.modules.get('crawler')
if _crawler is not None:
    from crawler import ProxyNode
else:
    import importlib
    _m = importlib.import_module('crawler')
    from crawler import ProxyNode

# generate_unique_id / _safe_port 来自 utils.py，直接重导出
from utils import generate_unique_id, _safe_port

__all__ = ['ProxyNode', 'generate_unique_id', '_safe_port']