# core 包：ZRONG 核心业务逻辑
# v28.40 Phase 2 重构：从 crawler.py 提取历史记录与评分函数

from .history import (
    # 源权重（兼容别名，实际指向 _dynamic_source_weight）
    _source_weight,
    # 节点历史记录
    _load_node_history,
    _save_node_history,
    _update_node_history,
    _get_node_history_score,
    _node_fingerprint,
    # 源历史记录
    _dynamic_source_weight,
    _update_source_history,
    _load_source_history,
    _save_source_history,
    # 运行时记录
    record_history,
    history_stability_score,
)

__all__ = [
    "_source_weight",
    "_load_node_history",
    "_save_node_history",
    "_update_node_history",
    "_get_node_history_score",
    "_node_fingerprint",
    "_dynamic_source_weight",
    "_update_source_history",
    "_load_source_history",
    "_save_source_history",
    "record_history",
    "history_stability_score",
]
