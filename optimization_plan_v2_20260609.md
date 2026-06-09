# ZRONG 优化方案 v2（借鉴同类项目）

## 一、同类项目经验借鉴

### 从 subconverter 学到
- 多格式输出（15+ 种）→ ZRONG 仅 YAML+TXT，需增加
- 外部配置支持（`&config=`）→ ZRONG 已做（rules.yaml），保持
- 自动上传 Gist → ZRONG 仅 Telegram 推送，需增加

### 从 ACL4SSR 学到
- 规则分层（banAD/nobanAD/gfwlist）→ ZRONG 仅一套规则，需增加
- 国内 IP 段直连（`ChinaCompanyIp.list`）→ ZRONG 已有 `CN_IP_RANGES`，保持
- 域名分流外置（`ChinaDomain.list`）→ ZRONG 硬编码 60+ 域名，需外置

---

## 二、切实可行的优化方案（分 3 个版本）

### 版本一：可用性提升（P0/P1，1-2 天）

#### 1. 修复大陆可达性软筛（P0）
**问题**：v28.63 删除硬筛后，软筛（扣分）也被注释，大陆不可达节点混在输出中。

**方案**：
```python
# core/scorer.py mainland_friendly_score() 中增加：
if p.get("mainland_reachable") is True:
    score += 30
elif p.get("mainland_reachable") is False:
    score -= 30
```

#### 2. Clash 配置模板外置（P0）
**方案**：将 `main_flow.py` 中硬编码的 `rules` 提取到 `config/clash_template.yaml`。

#### 3. 增加 Gist 自动上传（P1）
**方案**：在 `core/output.py` 中增加 `upload_to_gist()`，参考 subconverter。

---

### 版本二：稳定性增强（P1，3-5 天）

#### 4. 修复 Actions 超时（SIGKILL）
**问题**：60 分钟超时，前 43 批 Clash 测速合格 = 0。

**方案**：
- 增加 Clash 测速合格阈值（延迟稍高但速度合格也保留）
- 增加批次跳过逻辑（连续 3 批无合格节点则跳过）

#### 5. GeoIP2 本地数据库支持（P2）
**方案**：在 `network/geo.py` 中增加自动下载 GeoIP2 数据库逻辑。

---

### 版本三：可维护性增强（P2/P3，5-7 天）

#### 6. 拆分 main_flow.py（P2）
**方案**：拆分为 `core/collect.py` + `core/test.py` + `core/output.py`，每个 < 100 行。

#### 7. 规则分层（P3）
**方案**：在 `config/rules.yaml` 中增加 `rule_tiers` 配置（banAD/nobanAD/gfwlist）。

#### 8. 多格式输出（P3）
**方案**：增加 Surge/Quantumult X/Loon 格式输出，参考 subconverter。

---

## 三、实施优先级

| 优先级 | 改动 | 理由 |
|--------|------|------|
| **P0** | 修复大陆可达性软筛 | 1 行代码，直接提升可用率 |
| **P0** | Clash 配置模板外置 | 降低复杂度，便于自定义 |
| **P1** | 修复 Actions 超时 | SIGKILL 导致输出不完整 |
| **P1** | 增加 Gist 上传 | 方便用户获取订阅 |
| **P2** | GeoIP2 本地数据库 | 降低外部 API 依赖 |
| **P2** | 拆分 main_flow.py | 提升可维护性 |
| **P3** | 规则分层 | 功能增强 |
| **P3** | 多格式输出 | 功能增强 |

---

## 四、建议实施顺序

1. **今天**：修复大陆可达性软筛（P0）
2. **明天**：Clash 配置模板外置（P0）
3. **后天**：修复 Actions 超时（P1）
4. **本周内**：增加 Gist 上传（P1）

---

## 五、风险 & 回退策略

| 改动 | 风险 | 回退策略 |
|------|------|----------|
| 修复软筛 | 输出节点列表变化 | 设置 `MAINLAND_PASS_BONUS=0` 关闭加分 |
| Clash 模板外置 | 模板格式错误导致输出异常 | 保留原硬编码为 fallback |
| 修复 Actions 超时 | 跳过逻辑导致输出节点减少 | 调整 `consecutive_empty` 阈值 |
| 增加 Gist 上传 | Gist API 限流 | 捕获异常，失败后降级为仅本地输出 |
| GeoIP2 本地数据库 | 数据库文件损坏 | 降级为 ip-api.com |
| 拆分 main_flow.py | 引入新 bug | 拆分前创建备份，拆分后跑 Actions 验证 |

---

## 六、总结

本方案**优先解决可用率和稳定性问题**（P0/P1），再考虑可维护性和功能增强（P2/P3）。每个改动都**借鉴了同类项目的成熟经验**，且有明确的回退策略。

**核心思路**：
1. 修复现有 bug（软筛失效）→ 立即提升可用率
2. 配置外置（Clash 模板）→ 提升可维护性
3. 修复稳定性问题（Actions 超时）→ 确保输出完整
4. 功能增强（Gist 上传/多格式输出）→ 提升用户体验
