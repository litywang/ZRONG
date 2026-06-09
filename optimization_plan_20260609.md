# ZRONG 迭代优化方案（2026-06-09）

## 一、当前状态总结

| 维度 | 现状 | 问题 |
|------|------|------|
| 大陆可用率 | 依赖评分排序，无硬筛 | v28.63 删除了硬筛，可用率依赖 Clash 测速，存在假阳性 |
| 稳定性 | 大量 try-except，信号处理和资源清理已完善 | GitHub Actions 仍偶发 SIGKILL（60分钟超时） |
| 可维护性 | 已重构为 modular 结构 | main_flow.py 仍约500行，部分常量重复定义 |

---

## 二、逐文件问题 & 优化方案

### 📄 `crawler.py`（入口，~100行）

**问题**：
1. 常量重复定义：`ASIA_PRIORITY_BONUS`、`MAX_FINAL_NODES` 等在 `crawler.py` 和 `config/rules.yaml` 都有定义
2. 兼容旧名（v28.x 遗留）：`_load_node_history = load_node_history` 等 8 个兼容别名

**优化方案（v28.86）**：
- 统一常量来源，优先用 `os.getenv`，`config/rules.yaml` 只作为文档参考
- 清理兼容旧名，搜索所有引用确认无外部调用后删除

---

### 📄 `core/main_flow.py`（主流程，~500行）

**问题**：
1. TCP 测试超时 2 秒偏短
2. Clash 测速超时 8 秒偏短
3. 亚洲节点 TCP 测试配额计算复杂
4. `final_sort_key` 逻辑分散

**优化方案**：
- **v28.86**：TCP 测试超时 `timeout=2` → `timeout=3`
- **v28.87**：Clash 测速超时 `timeout=8` → `timeout=10`，增加 `CLASH_TEST_TIMEOUT` 环境变量
- **v28.87**：提取亚洲节点配额计算为独立函数 `calc_asia_quota()`
- **v28.88**：将 `final_sort_key` 完整逻辑迁移到 `core/filter.py`
- **v28.89**：拆分 `main_flow.py` 为 `collect → test → output` 三个函数（每个 < 100 行）

---

### 📄 `core/validator.py`（验证去重）

**问题**：
1. `is_asia` 函数过长（~80 行）
2. `CN_DOMAIN_BLACKLIST_RE` 正则过长难以维护

**优化方案**：
- **v28.86**：拆分 `is_asia` 为 4 个子函数：`_asia_by_name`、`_asia_by_geo`、`_asia_by_sni`、`_asia_by_tld`
- **v28.87**：将 `CN_DOMAIN_BLACKLIST_RE` 迁移到 `config/rules.yaml` 的 `domain_blacklist_regex` 字段

---

### 📄 `core/scorer.py`（评分）

**问题**：
1. new 版评分未被启用（`USE_NEW_SCORING` 默认 `"0"`）
2. legacy 和 new 两版并存，增加维护成本

**优化方案**：
- **v28.86**：确认 `load_rules()` 有缓存，避免每次评分都读磁盘
- **v28.87**：启用 new 版评分，`USE_NEW_SCORING` 默认改为 `"1"`
- **v28.88**：删除 legacy 版，只保留 new 版

---

### 📄 `core/filter.py`（过滤 & 排序）

**问题**：
1. `filter_quality` 中大陆可达性只打 log 不扣分
2. `_geo_score` 重复查询 GeoIP（预查阶段已查过）
3. `final_sort_key` 依赖从节点 name 解析延迟，易失败

**优化方案**：
- **v28.86**：恢复大陆可达性软筛：`mainland_reachable is False` 时 `mf_score -= 30`
- **v28.87**：`_geo_score` 增加缓存，用预查阶段存储的 geo 结果
- **v28.88**：`final_sort_key` 改为从 `p.get("_tcp_latency")` 读取延迟

---

### 📄 `network/geo.py`（GeoIP 查询）

**问题**：
1. `ip-api.com` 限流 `0.5` 秒可能仍触达 45次/分钟边界
2. GeoIP 缓存 TTL 24 小时偏短
3. 本地 GeoIP2 数据库支持默认不启用

**优化方案**：
- **v28.86**：`ip-api.com` 限流从 `0.5` → `1.5` 秒（40次/分钟，留有余量）
- **v28.87**：GeoIP 缓存 TTL 从 86400 → 604800（7天），`maxsize` 从 10000 → 50000
- **v28.88**：增加自动更新 GeoIP2 数据库功能（每周检查，超过 30 天自动下载）

---

### 📄 `network/tcp.py`（TCP 测试）

**问题**：
1. `_tcp_ping` 默认超时 2.5 秒偏短
2. IPv6 socket 创建逻辑误判 IPv4-mapped IPv6

**优化方案**：
- **v28.86**：`_tcp_ping` 超时 `2.5` → `3.0`，`tcp_verify` `1.5` → `2.0`，增加环境变量可配置
- **v28.87**：`_create_socket` 改用 `ipaddress.ip_address(host).version` 判断 IPv4/IPv6

---

### 📄 `network/tls.py`（TLS 握手）

**问题**：
1. `is_reality_friendly` 关键词列表过短（7个）

**优化方案**：
- **v28.87**：增加更多 Reality 关键词，并从 `reality-opts` 字段判断（更可靠）

---

### 📄 `core/collector.py`（采集）

**问题**：
1. Telegram 爬取只爬第 1 页（20 条消息）
2. 同步抓取 `fetch_workers=150` 偏高，可能触发 API 限流

**优化方案**：
- **v28.86**：Telegram 爬取 `pages=1` → `pages=2`
- **v28.87**：同步抓取 `fetch_workers` 默认 150 → 80
- **v28.88**：异步抓取模式完整测试后设为默认

---

### 📄 `config/rules.yaml`（规则配置）

**问题**：
1. `scoring_legacy` 和 `scoring_new` 并存
2. `regions.premium` 关键词和 `core/scorer.py` 中重复

**优化方案**：
- **v28.86**：增加 `domain_blacklist_regex` 字段
- **v28.87**：统一 `regions.premium` 为唯一来源
- **v28.88**：删除 `scoring_legacy` 块

---

## 三、版本迭代计划

| 版本 | 主要内容 | 涉及文件 |
|------|----------|----------|
| **v28.86** | TCP/TLS 超时调整；`ip-api.com` 限流优化；TG 爬取页数增加；YAML 增加 `domain_blacklist_regex` | `core/main_flow.py`, `network/geo.py`, `network/tcp.py`, `core/collector.py`, `config/rules.yaml` |
| **v28.87** | 启用 new 版评分；`is_asia` 拆分；YAML 迁移；`final_sort_key` 延迟解析优化；`fetch_workers` 下调 | `core/scorer.py`, `core/validator.py`, `core/filter.py`, `config/rules.yaml`, `core/collector.py` |
| **v28.88** | `main_flow.py` 拆分；GeoIP2 自动更新；删除 legacy 评分；统一常量 | `core/main_flow.py`, `network/geo.py`, `core/scorer.py`, `crawler.py` |
| **v28.89** | `final_sort_key` 迁移到 `core/filter.py`；IPv6 判断修复；Clash 超时可调 | `core/filter.py`, `network/tcp.py`, `core/main_flow.py` |
| **v28.90** | 异步抓取设为默认；`ENABLE_MAINLAND_TEST` 默认启用；文档更新 | `core/collector.py`, `core/main_flow.py`, `README.md` |

---

## 四、优先行动建议

**立即做（v28.86）**：
1. 调整 TCP 测试超时 `timeout=2` → `timeout=3`
2. `ip-api.com` 限流 `0.5` → `1.5`
3. Telegram 爬取 `pages=1` → `pages=2`

**短期（v28.87-v28.88）**：
- 启用 new 版评分
- 拆分 `main_flow.py`
- GeoIP2 自动更新

**中期（v28.89-v28.90）**：
- 完善大陆可达性测试
- 异步抓取设为默认

---

## 五、风险 & 回退策略

| 改动 | 风险 | 回退策略 |
|------|------|----------|
| TCP 超时增加 | Actions 总耗时增加 | 改回 `timeout=2`，或增加 `TCP_WORKERS` |
| 启用 new 版评分 | 输出节点列表变化 | 设置 `USE_NEW_SCORING=0` 回退 |
| `main_flow.py` 拆分 | 引入新 bug | 拆分前创建备份，拆分后跑 Actions 验证 |
| `ip-api.com` 限流放宽 | 仍可能 429 | 捕获 429 后指数退避重试（已有逻辑） |

---

## 六、总结

本方案以「**提升大陆可用率 + 保持稳定性 + 增强可维护性**」为目标，分 5 个版本（v28.86-v28.90）逐步实施。每个版本只改 3-5 个文件，小步迭代，可回退，风险可控。

**核心思路**：
1. 参数调优（超时、并发、限流）→ 立即提升可用率
2. 启用 new 版评分 → 提升亚洲节点质量
3. 代码拆分重构 → 提升可维护性
4. GeoIP2 本地化 + 异步抓取 → 降低对外部 API 依赖，提升稳定性
