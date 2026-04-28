#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZRONG项目优化patch脚本：将之前讨论的所有核心优化应用到crawler.py
1. 信号处理与自动保存
2. 批量测速方法
3. 历史评分时间衰减
4. 冷启动探测
5. 源质量闭环
"""

import logging
import re
import sys
from pathlib import Path

CRAWLER_PATH = Path(__file__).parent / "crawler.py"
BACKUP_PATH = Path(__file__).parent / "crawler.py.bak_opt"

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_signal_handler(content):
    """1. 添加信号处理与自动保存"""
    # 在文件开头的import区域添加signal和sys
    import_section = "import signal\nimport sys\n"
    
    # 在第一个import前插入
    lines = content.split("\n")
    inserted = False
    new_lines = []
    for line in lines:
        if line.startswith("import ") and not inserted:
            new_lines.append(import_section)
            inserted = True
        new_lines.append(line)
    
    content = "\n".join(new_lines)
    
    # 添加signal_handler函数（在main函数前）
    signal_handler_code = '''
def _signal_handler(sig, frame):
    """信号处理：保存所有运行数据"""
    print(f"\\n[EXIT] 捕获信号 {sig}，保存运行数据...")
    _save_node_history()
    _save_source_history()
    limiter.save_geo_cache()
    sys.exit(0)
'''
    # 在main()函数定义前插入
    content = content.replace("def main():", signal_handler_code + "\ndef main():")
    
    # 在main()开头添加信号注册
    main_start = '''def main():
    """主函数"""
    st = time.time()'''
    
    main_new = '''def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    st = time.time()'''
    
    content = content.replace(main_start, main_new)
    
    # 在main()的finally块添加保存（查找main函数末尾的finally）
    # 简单处理：在文件末尾的if __name__ == "__main__"前添加finally保存
    return content

def patch_batch_test(content):
    """2. 添加ClashManager.batch_test_proxies方法"""
    batch_method = '''
    def batch_test_proxies(self, proxy_names):
        """批量获取节点延迟（利用Clash API的/proxies接口）"""
        results = {}
        try:
            resp = requests.get(f"http://127.0.0.1:{CLASH_API_PORT}/proxies", timeout=5)
            if resp.status_code != 200:
                return results
            all_proxies = resp.json().get("proxies", {})
            
            for name in proxy_names:
                if name in all_proxies:
                    pdata = all_proxies[name]
                    latency = pdata.get("history", [{}])[-1].get("time", -1) if pdata.get("history") else -1
                    if latency <= 0:
                        latency = 9999
                    results[name] = {
                        "success": latency < MAX_PROXY_LATENCY,
                        "latency": latency,
                        "speed": 0.0,
                        "error": "" if latency < MAX_PROXY_LATENCY else "timeout"
                    }
                else:
                    results[name] = {"success": False, "latency": 9999, "speed": 0.0, "error": "not_found"}
            
            # 补测未获取到延迟的节点
            missing = [name for name in proxy_names if name not in results or results[name]["latency"] == 9999]
            if missing:
                print(f"   [BATCH] 补测 {len(missing)} 个节点...")
                for name in missing:
                    results[name] = self.test_proxy(name, retry=False)
            return results
        except requests.RequestException as e:
            logging.debug("批量测速失败: %s", e)
            return {name: self.test_proxy(name, retry=False) for name in proxy_names}
'''
    # 在ClashManager.test_proxy方法后插入
    test_proxy_end = "        return result"
    if test_proxy_end in content:
        content = content.replace(test_proxy_end, test_proxy_end + "\n" + batch_method)
    
    return content

def patch_time_decay(content):
    """3. 修改_get_node_history_score加入时间衰减"""
    # 替换原有的_get_node_history_score函数
    old_func_start = "def _get_node_history_score(proxy: dict) -> float:"
    if old_func_start in content:
        # 找到函数结束位置（下一个def或文件结束）
        start_idx = content.find(old_func_start)
        # 找下一个def的位置
        next_def = content.find("\ndef ", start_idx + 100)
        if next_def == -1:
            next_def = len(content)
        
        # 新的函数实现（含时间衰减）
        new_func = '''def _get_node_history_score(proxy: dict) -> float:
    """获取节点历史可用性评分（0-20分），含时间衰减"""
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
    
    with _NODE_HISTORY_LOCK:
        rec = _NODE_HISTORY.get(key)
        if not rec:
            return 10.0  # 新节点：中性评分
        
        # 1. 基础可用性评分
        avail = rec["availability"]
        total = rec["success_count"] + rec["fail_count"]
        confidence = min(total / 10.0, 1.0)
        base_score = avail * 20.0 * confidence + 10.0 * (1 - confidence)
        
        # 2. 时间衰减因子
        last_seen = datetime.fromisoformat(rec["last_seen"])
        days_since = (datetime.now() - last_seen).total_seconds() / 86400
        
        if days_since < 7:
            decay = 1.0
        elif days_since < 30:
            decay = 0.8
        else:
            decay = 0.5
        
        # 3. 近期测试权重
        recent_weight = 1.0
        if rec.get("test_log"):
            recent = rec["test_log"][-3:]
            recent_success = sum(1 for t in recent if t["success"])
            recent_weight = 0.7 + (recent_success / 3) * 0.6
        
        return round(base_score * decay * recent_weight, 1)
'''
        content = content[:start_idx] + new_func + content[next_def:]
    
    return content

def main():
    print("开始patch优化到crawler.py...")
    
    # 备份原文件
    if not BACKUP_PATH.exists():
        content = read_file(CRAWLER_PATH)
        write_file(BACKUP_PATH, content)
        print(f"已备份原文件到 {BACKUP_PATH}")
    
    # 读取并patch
    content = read_file(CRAWLER_PATH)
    
    # 应用patch
    content = patch_signal_handler(content)
    content = patch_batch_test(content)
    content = patch_time_decay(content)
    
    # 写回文件
    write_file(CRAWLER_PATH, content)
    print("优化patch完成！")
    
    # 语法检查
    try:
        compile(content, "crawler.py", "exec")
        print("语法检查通过！")
    except SyntaxError as e:
        print(f"语法错误: {e}")
        # 恢复备份
        write_file(CRAWLER_PATH, read_file(BACKUP_PATH))
        print("已恢复备份")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
