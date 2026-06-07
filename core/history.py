#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/history.py - 节点与源的智能历史记录系统

从 crawler.py v28.53/v28.54 提取，负责：
- 节点历史可用性追踪（node_history.json）
- 源历史权重系统（source_history.json）
- 动态源权重计算
- 节点历史可用性评分
"""

import json
import hashlib
import logging
import threading
from datetime import datetime
from pathlib import Path

# ===== 历史稳定性记录 ======
_HISTORY_SCORES = {}
_HISTORY_SCORES_LOCK = threading.Lock()

# v28.53: 节点历史可用性追踪（node_history.json）
NODE_HISTORY_FILE = Path("node_history.json")
_NODE_HISTORY = {}
_NODE_HISTORY_LOCK = threading.Lock()

# v28.54: 智能源权重系统（source_history.json）
SOURCE_HISTORY_FILE = Path("source_history.json")
_SOURCE_HISTORY = {}
_SOURCE_HISTORY_LOCK = threading.Lock()


# ========== 加载/保存 ==========

def load_node_history():
    """加载节点历史记录。"""
    global _NODE_HISTORY
    if NODE_HISTORY_FILE.exists():
        try:
            with open(NODE_HISTORY_FILE, "r", encoding="utf-8") as f:
                _NODE_HISTORY = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            _NODE_HISTORY = {}
    else:
        _NODE_HISTORY = {}


def load_source_history():
    """加载源历史记录。"""
    global _SOURCE_HISTORY
    if SOURCE_HISTORY_FILE.exists():
        try:
            with open(SOURCE_HISTORY_FILE, "r", encoding="utf-8") as f:
                _SOURCE_HISTORY = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            _SOURCE_HISTORY = {}
    else:
        _SOURCE_HISTORY = {}


def save_source_history():
    """保存源历史记录。"""
    try:
        with open(SOURCE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_SOURCE_HISTORY, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        logging.debug("Save source history failed", exc_info=True)


def save_node_history():
    """保存节点历史记录。"""
    try:
        with open(NODE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_NODE_HISTORY, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError):
        logging.debug("Save node history failed", exc_info=True)


# ========== 源历史 ==========

def source_weight(url: str) -> int:
    """v28.23: 根据URL特征推断源权重（1-10），国内友好源得分更高。
    高权重源中解析出的节点在最终排序中获得额外加分。
    """
    u = url.lower()
    # 国内友好源（历史数据表明亚洲节点占比高）
    domestic_keywords = [
        "ermaozi", "peasoft", "aiboboxx", "mfuu", "freefq", "kxswa",
        "llywhn", "adiwzx", "changfengoss", "mymysub", "yeahwu",
        "mksshare", "bulianglin", "yiiss", "free18", "shaoyouvip",
        "yonggekkk", "vxiaodong", "wxloststar",
    ]
    for kw in domestic_keywords:
        if kw in u:
            return 8
    # 大聚合源（量大但亚洲占比一般）
    aggregator_keywords = ["mahdibland", "epodonios", "barry-far"]
    for kw in aggregator_keywords:
        if kw in u:
            return 5
    # 协议专项源（vless/hysteria2 对大陆更友好）
    if "vless" in u or "hysteria2" in u:
        return 7
    if "trojan" in u:
        return 6
    # 默认权重
    return 3


def update_source_history(url: str, success: bool, node_count: int = 0, asia_count: int = 0):
    """更新单个源的历史记录。
    
    Args:
        url: 订阅源 URL
        success: 本次抓取是否成功
        node_count: 本次抓取的节点数
        asia_count: 本次抓取的亚洲节点数
    """
    now = datetime.now().isoformat()
    with _SOURCE_HISTORY_LOCK:
        if url not in _SOURCE_HISTORY:
            _SOURCE_HISTORY[url] = {
                "first_seen": now,
                "last_seen": now,
                "success_count": 0,
                "fail_count": 0,
                "total_nodes": 0,
                "total_asia_nodes": 0,
                "fetch_count": 0,
                "history": [],  # 最近10次记录
            }
        rec = _SOURCE_HISTORY[url]
        rec["last_seen"] = now
        rec["fetch_count"] += 1
        if success:
            rec["success_count"] += 1
        else:
            rec["fail_count"] += 1
        if node_count > 0:
            rec["total_nodes"] += node_count
            rec["total_asia_nodes"] += asia_count
            # 保留最近10次记录
            rec["history"].append({
                "time": now,
                "nodes": node_count,
                "asia_nodes": asia_count,
            })
            if len(rec["history"]) > 10:
                rec["history"] = rec["history"][-10:]


def dynamic_source_weight(url: str) -> float:
    """计算动态源权重（1-20分）。
    
    融合静态规则 + 历史表现动态计算：
    - 静态规则：URL 关键词硬编码（1-10分）
    - 动态因子：成功率、亚洲比例、新鲜度、趋势
    
    公式：static * (0.4 + success_rate * 1.2) * (0.8 + asia_rate * 0.4) * recency * trend
    """
    # 1. 静态基础分（1-10）
    static = float(source_weight(url))
    
    with _SOURCE_HISTORY_LOCK:
        rec = _SOURCE_HISTORY.get(url)
        if not rec:
            # 无历史数据：返回静态分 * 中性因子（1.0）
            return round(static * 1.0, 1)
        
        # 2. 成功率因子（0.4 - 1.6）
        total_fetches = rec["success_count"] + rec["fail_count"]
        success_rate = rec["success_count"] / total_fetches if total_fetches > 0 else 0.5
        success_factor = 0.4 + success_rate * 1.2
        
        # 3. 亚洲比例因子（0.8 - 1.2）
        total_nodes = rec["total_nodes"]
        asia_rate = rec["total_asia_nodes"] / total_nodes if total_nodes > 0 else 0.3
        asia_factor = 0.8 + asia_rate * 0.4
        
        # 4. 新鲜度因子（0.4 - 1.3）
        last_seen = datetime.fromisoformat(rec["last_seen"])
        days_since = (datetime.now() - last_seen).total_seconds() / 86400
        if days_since < 1:
            recency = 1.3
        elif days_since < 7:
            recency = 1.0
        elif days_since < 30:
            recency = 0.7
        else:
            recency = 0.4
        
        # 5. 趋势因子（0.7 - 1.9）
        history = rec.get("history", [])
        if len(history) >= 3:
            recent = sum(h["nodes"] for h in history[-3:]) / 3.0
            older = sum(h["nodes"] for h in history[:-3]) / max(len(history) - 3, 1)
            if older > 0:
                trend = 0.7 + min(recent / older, 1.2) * 1.0
            else:
                trend = 1.0
        else:
            trend = 1.0
        
        # 综合计算
        weight = static * success_factor * asia_factor * recency * trend
        # 限制在 1-20 范围
        weight = max(1.0, min(20.0, weight))
        return round(weight, 1)


# ========== 节点历史 ==========

def _node_fingerprint(proxy: dict) -> str:
    """计算节点指纹（MD5），用于历史记录唯一键。"""
    uid = proxy.get("uuid", "")
    pwd = proxy.get("password", "")
    auth = uid or pwd or ""
    host = proxy.get("sni", "") or proxy.get("servername", "") or proxy.get("server", "")
    path = ""
    ws_opts = proxy.get("ws-opts", {})
    if isinstance(ws_opts, dict):
        path = ws_opts.get("path", "")
    key = hashlib.md5(
        f"{proxy.get('type', '')}|{proxy.get('server', '')}|{proxy.get('port', 0)}|{auth}|{path}|{host}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return key


def update_node_history(proxy: dict, success: bool):
    """更新单个节点的历史记录。
    
    Args:
        proxy: 节点配置字典
        success: 本次测试是否成功
    """
    key = _node_fingerprint(proxy)
    now = datetime.now().isoformat()
    with _NODE_HISTORY_LOCK:
        if key not in _NODE_HISTORY:
            _NODE_HISTORY[key] = {
                "first_seen": now,
                "last_seen": now,
                "success_count": 0,
                "fail_count": 0,
                "availability": 0.0,
            }
        rec = _NODE_HISTORY[key]
        rec["last_seen"] = now
        if success:
            rec["success_count"] += 1
        else:
            rec["fail_count"] += 1
        total = rec["success_count"] + rec["fail_count"]
        rec["availability"] = round(rec["success_count"] / total, 3) if total > 0 else 0.0


def get_node_history_score(proxy: dict) -> float:
    """获取节点历史可用性评分（0-20分）。
    
    高可用性节点获得额外加分，新节点中性评分。
    """
    key = _node_fingerprint(proxy)
    with _NODE_HISTORY_LOCK:
        rec = _NODE_HISTORY.get(key)
        if not rec:
            return 10.0  # 新节点：中性评分
        avail = rec["availability"]
        total = rec["success_count"] + rec["fail_count"]
        # 可用性评分：根据历史可用率加权
        # 样本量越大，评分越可信
        confidence = min(total / 10.0, 1.0)  # 10次以上达到最大置信度
        score = avail * 20.0 * confidence + 10.0 * (1 - confidence)
        return round(score, 1)


# ========== 历史稳定性评分（_HISTORY_SCORES）==========


def record_history(server_ip, port, latency):
    """记录 TCP 延迟到历史（线程安全）。"""
    key = (server_ip, port)
    with _HISTORY_SCORES_LOCK:
        if key not in _HISTORY_SCORES:
            _HISTORY_SCORES[key] = []
        _HISTORY_SCORES[key].append(latency)
        if len(_HISTORY_SCORES[key]) > 10:
            _HISTORY_SCORES[key] = _HISTORY_SCORES[key][-10:]


def history_stability_score(server_ip, port):
    """计算节点历史稳定性评分（0-500+）。"""
    key = (server_ip, port)
    with _HISTORY_SCORES_LOCK:
        if key not in _HISTORY_SCORES or not _HISTORY_SCORES[key]:
            return 0
        scores = list(_HISTORY_SCORES[key])
    n = len(scores)
    success_rate = sum(1 for s in scores if s < 9999) / n
    avg = sum(scores) / n
    variance = sum((s - avg) ** 2 for s in scores) / n
    std = variance ** 0.5
    return max(0, int(success_rate * 500 - min(std * 2, 200)))


# ========== 兼容性别名（供 crawler.py 平滑迁移） ==========

# 全局变量访问（供 crawler.py 的全局变量引用兼容）
def get_node_history():
    """获取节点历史字典（只读访问）。"""
    return _NODE_HISTORY

def get_source_history():
    """获取源历史字典（只读访问）。"""
    return _SOURCE_HISTORY

def get_history_scores():
    """获取历史稳定性评分字典（只读访问）。"""
    return _HISTORY_SCORES
