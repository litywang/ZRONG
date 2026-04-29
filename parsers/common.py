# parsers/common.py - 重导出层（v28.52）
# ProxyNode / generate_unique_id / _safe_port 统一从此文件导入
# ProxyNode 定义移至 proxynode.py，解除循环导入
# generate_unique_id / _safe_port 来自 utils.py

from .proxynode import ProxyNode
from utils import generate_unique_id, _safe_port

__all__ = ['ProxyNode', 'generate_unique_id', '_safe_port']
