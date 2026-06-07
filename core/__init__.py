# core 包：ZRONG 核心业务逻辑
# v28.40 Phase 2 重构：从 crawler.py 提取历史记录与评分函数

from .history import (
    # 源权重
    source_weight,
    # 节点历史记录
    load_node_history,
    save_node_history,
    update_node_history,
    get_node_history_score,
    _node_fingerprint,
    # 源历史记录
    dynamic_source_weight,
    update_source_history,
    load_source_history,
    save_source_history,
    # 运行时记录
    record_history,
    history_stability_score,
)

__all__ = [
    "source_weight",
    "load_node_history",
    "save_node_history",
    "update_node_history",
    "get_node_history_score",
    "_node_fingerprint",
    "dynamic_source_weight",
    "update_source_history",
    "load_source_history",
    "save_source_history",
    "record_history",
    "history_stability_score",
]