# core 包：ZRONG 核心业务逻辑
# v28.40 Phase 2 重构：从 crawler.py 提取历史记录与评分函数
# v28.63: 补全导出，让 from core import ... 正常工作
# v28.91: 导出健康检查函数

from .history import (
    source_weight,
    load_node_history,
    save_node_history,
    update_node_history,
    get_node_history_score,
    _node_fingerprint,
    dynamic_source_weight,
    update_source_history,
    load_source_history,
    save_source_history,
    record_history,
    history_stability_score,
)

from .clash import ClashManager
from .namer import NodeNamer
from .output import format_proxy_to_link
from .config import check_network_baseline, ensure_clash_dir, create_session, tcp_ping, CLASH_PORT, CLASH_API_PORT, CLASH_VERSION, CLASH_PATH, CONFIG_FILE, LOG_FILE
from .filter import filter_quality
from .history import _signal_handler
from .validator import (
    generate_unique_id,
    is_cn_proxy_domain,
    is_china_mainland,
    is_asia,
    validate_node,
    health_check,
    batch_health_check,
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
    "ClashManager",
    "NodeNamer",
    "format_proxy_to_link",
    "check_network_baseline",
    "ensure_clash_dir",
    "create_session",
    "tcp_ping",
    "filter_quality",
    "_signal_handler",
    "CLASH_PORT",
    "CLASH_API_PORT",
    "CLASH_VERSION",
    "CLASH_PATH",
    "CONFIG_FILE",
    "LOG_FILE",
    "generate_unique_id",
    "is_cn_proxy_domain",
    "is_china_mainland",
    "is_asia",
    "validate_node",
    "health_check",
    "batch_health_check",
]
