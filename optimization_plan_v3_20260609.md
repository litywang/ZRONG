# ZRONG 优化方案 v3（基于同类项目源码学习）

## 一、从 `clash-verge-auto-switch` 学到的关键经验

### 1. Clash Controller API 调用方式
**ZRONG 现状**：用 `subprocess` 启动 Clash 进程，然后解析日志  
**优化方向**：直接调用 Controller API（`/proxies/{name}/delay`）

**关键端点**：
| 端点 | 用途 |
|------|------|
| `GET /version` | 检查 Controller 是否可达 |
| `GET /proxies` | 获取所有代理和组信息 |
| `GET /proxies/{name}/delay?url=...&timeout=...` | **测速单个代理** |
| `PUT /proxies/{group_name}` | 切换选择器组 |

### 2. Controller 自动发现机制
1. 优先用 Unix socket（`external-controller-unix`）
2. 其次用 HTTP（`external-controller`）
3. 从环境变量读取（`CLASH_API_UNIX_SOCKET` / `CLASH_API_URL`）
4. 从配置文件读取（`~/.config/clash/config.yaml`）
5. 都失败 → 尝试启动 Clash Verge（`--launch-if-needed`）

### 3. 延迟测试实现
```python
def measure_delay(controller, proxy_name, url, timeout_ms):
    response = api_request(
        controller,
        "GET",
        f"/proxies/{quote(proxy_name)}/delay",
        query={"url": url, "timeout": str(timeout_ms)}
    )
    if isinstance(response, dict):
        return response.get("delay")  # 返回延迟（毫秒）
    return None
```

---

## 二、修订后的优化方案（更具体、可落地）

### P0：用 Clash Controller API 替代 subprocess 测速
**文件**：`core/clash.py`  
**改动**：
1. 增加 `test_proxy_api()` 方法，调用 `GET /proxies/{name}/delay`
2. 保留原有的 subprocess 方式作为 fallback

**预期效果**：
- 测速速度提升 3-5 倍
- 稳定性提升（不需要解析 Clash 日志格式变化）
- 支持并发测试

### P0：增加 Controller 自动发现
**文件**：`core/clash.py` 的 `ClashManager.__init__()`  
**改动**：自动从环境变量/配置文件发现 Controller 地址

### P1：增加 Dry-Run 模式
**文件**：`crawler.py` 增加 `--dry-run` 参数  
**改动**：测试但不输出结果，方便调试

### P1：增加自动启动 Clash
**文件**：`core/clash.py` 的 `ClashManager.start()`  
**改动**：如果 Controller 不可达，尝试自动启动 Clash Verge

### P2：借鉴 `free-proxy` 增加多格式输出
**文件**：`core/output.py`  
**改动**：增加 V2Ray、Shadowrocket 格式输出

---

## 三、实施优先级

| 优先级 | 改动 | 理由 | 工作量 |
|--------|------|------|--------|
| **P0** | 用 Controller API 替代 subprocess 测速 | 速度提升 3-5 倍 | 2 小时 |
| **P0** | 增加 Controller 自动发现 | 减少配置错误 | 1 小时 |
| **P1** | 增加 Dry-Run 模式 | 方便调试 | 0.5 小时 |
| **P1** | 增加自动启动 Clash | 提升用户体验 | 1 小时 |
| **P2** | 增加多格式输出 | 功能增强 | 2 小时 |

---

## 四、代码示例（P0 改动）

### `core/clash.py` 增加 `test_proxy_api()` 方法

```python
def test_proxy_api(self, proxy_name: str, test_url: str, timeout_ms: int = 8000) -> dict:
    """使用 Controller API 测试单个代理延迟"""
    import urllib.parse
    import subprocess
    
    cmd = [
        "curl", "--silent", "--show-error", "--fail-with-body",
        "--max-time", str(timeout_ms // 1000 + 2),
    ]
    
    if self.controller_unix_socket and Path(self.controller_unix_socket).exists():
        cmd.extend(["--unix-socket", self.controller_unix_socket])
        api_url = f"http://localhost/proxies/{urllib.parse.quote(proxy_name)}/delay"
    else:
        api_url = f"{self.controller_url}/proxies/{urllib.parse.quote(proxy_name)}/delay"
    
    if self.secret:
        cmd.extend(["-H", f"Authorization: Bearer {self.secret}"])
    
    cmd.extend([
        "-X", "GET",
        "--get",
        "--data-urlencode", f"url={test_url}",
        "--data-urlencode", f"timeout={timeout_ms}",
        api_url
    ])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms // 1000 + 5)
    if result.returncode == 0 and result.stdout.strip():
        import json
        data = json.loads(result.stdout)
        delay = data.get("delay")
        if delay is not None:
            return {"success": True, "latency": delay / 1000.0, "speed": 0}
    return {"success": False, "latency": 9999.0, "speed": 0}
```

---

## 五、总结

本方案基于 **`clash-verge-auto-switch` 源码学习**，给出了**更具体、可落地的优化方案**。

**核心优化点**：
1. **P0**：用 Clash Controller API 替代 subprocess 测速（速度提升 3-5 倍）
2. **P0**：增加 Controller 自动发现（减少配置错误）
3. **P1**：增加 Dry-Run 模式（方便调试）
4. **P1**：增加自动启动 Clash（提升用户体验）
5. **P2**：增加多格式输出（功能增强）

**下一步**：实施 P0 改动（预计 3 小时工作量）
