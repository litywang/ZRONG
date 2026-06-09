# ZRONG 最终优化方案（基于 7 个同类项目学习）

## 一、从同类项目学到的关键经验

| 项目 | 学到的经验 |
|------|-------------|
| `subconverter` | 外部配置、多格式输出、Gist 上传 |
| `ACL4SSR` | 规则分层、国内 IP 段直连、域名分流外置 |
| `free-proxy` | Clash Meta / V2Ray / Shadowrocket 多格式输出 |
| `clash-verge-auto-switch` | **Clash Controller API 调用**、自动发现、延迟测试 |
| `clash-configuration-generator` | **参考 YAML 系统**、规则合并去重、本地规则补丁、**单元测试** |
| `discovery-service` | **健康检查机制**（每 30 秒检查，失败 3 次禁用） |
| `NameMCSniper` | 代理轮换 + 健康检查（`check-proxies` 命令） |

---

## 二、最终优化方案（5 个版本迭代）

### v28.86（P0：测速优化）
**目标**：用 Clash Controller API 替代 subprocess 测速  
**改动**：
1. `core/clash.py` 增加 `test_proxy_api()` 方法
2. 保留原有 subprocess 方式作为 fallback
3. 增加 Controller 自动发现（`discover_controller()`）

**预期效果**：测速速度提升 3-5 倍，稳定性提升

---

### v28.87（P0：健康检查）
**目标**：增加节点健康检查机制  
**改动**：
1. `core/validator.py` 增加 `health_check()` 函数
2. 每 30 秒检查一次节点状态（借鉴 `discovery-service`）
3. 失败 3 次的节点标记为 `disabled`
4. 每 15 分钟清理一次 `disabled` 节点

**预期效果**：输出节点可用率提升 20-30%

---

### v28.88（P1：规则系统）
**目标**：增加参考 YAML 系统 + 规则合并去重  
**改动**：
1. `config/` 目录增加 `preference.basic.yaml`、`preference.advanced.yaml` 等参考配置
2. `core/filter.py` 增加规则合并去重逻辑
3. 支持 `ruleset-rule-patches`（本地规则补丁）

**预期效果**：配置更灵活，规则更精准

---

### v28.89（P1：测试 + Dry-Run）
**目标**：增加单元测试 + Dry-Run 模式  
**改动**：
1. `tests/` 目录增加 `test_rule_logic.py`、`test_proxy_health_check.py` 等
2. `crawler.py` 增加 `--dry-run` 参数
3. 支持 `--stdout` 只输出到标准输出

**预期效果**：回归测试覆盖核心逻辑，调试更方便

---

### v28.90（P2：多格式输出）
**目标**：增加多格式输出  
**改动**：
1. `core/output.py` 增加 `write_v2ray()`、`write_shadowrocket()` 等函数
2. 支持 Clash Meta / V2Ray / Shadowrocket 三种格式
3. 可选 Gist 自动上传

**预期效果**：支持更多客户端

---

## 三、实施优先级

| 版本 | 改动 | 理由 | 工作量 |
|------|------|------|--------|
| **v28.86** | Clash Controller API 测速 | 速度提升 3-5 倍 | 2 小时 |
| **v28.87** | 健康检查机制 | 可用率提升 20-30% | 3 小时 |
| **v28.88** | 参考 YAML 系统 | 配置更灵活 | 2 小时 |
| **v28.89** | 单元测试 + Dry-Run | 回归测试 + 调试方便 | 2 小时 |
| **v28.90** | 多格式输出 | 支持更多客户端 | 2 小时 |

---

## 四、关键代码实现（v28.86）

### `core/clash.py` 增加 `test_proxy_api()` 方法

```python
def test_proxy_api(self, proxy_name: str, test_url: str, timeout_ms: int = 8000) -> dict:
    """使用 Controller API 测试单个代理延迟（借鉴 clash-verge-auto-switch）"""
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

本方案基于 **7 个同类项目**（含 README 和源码）的学习，给出了**最具体、可落地的优化方案**。

**核心优化点**：
1. **P0**：用 Clash Controller API 替代 subprocess 测速（速度提升 3-5 倍）
2. **P0**：增加健康检查机制（可用率提升 20-30%）
3. **P1**：增加参考 YAML 系统（配置更灵活）
4. **P1**：增加单元测试 + Dry-Run（回归测试 + 调试方便）
5. **P2**：增加多格式输出（支持更多客户端）

**下一步：实施 v28.86 改动（预计 2 小时工作量）**
