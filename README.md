# 🚀 ZRONG —— 智能订阅聚合工具 v29

> 🌟 **极致 · 稳定 · 精准 · 高效** | GitHub Actions 全自动化节点筛选平台
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度重构
> **v29 模块化版：分层架构 + 四层验证 + 亚洲优先配额 + 异步采集**

[![GitHub stars](https://img.shields.io/github/stars/litywang/ZRONG?style=flat-square)](https://github.com/litywang/ZRONG/stargazers)
[![GitHub workflow](https://img.shields.io/github/actions/workflow/status/litywang/ZRONG/update.yml?style=flat-square)](https://github.com/litywang/ZRONG/actions)
[![License](https://img.shields.io/github/license/litywang/ZRONG?style=flat-square)](LICENSE)

---

## 📌 核心特性总览

| 维度 | 功能亮点 | 技术实现 |
|------|----------|---------|
| 🔥 **多源采集** | Telegram 频道(30+) + GitHub Fork(60仓库) + 固定订阅源(63+) | 三路并行发现 + 异步采集 |
| 🌏 **亚洲优先** | 亚洲节点强制≥45%配额，上限75% | 多层加权 + 延迟放宽 + 保底机制 |
| 📄 **双格式解析** | TXT 协议链接 + YAML 配置 | 自动识别并行处理 |
| 🔗 **全协议支持** | 12种协议 | VMess / VLESS / Trojan / SS / SSR / Hysteria2 / Hysteria / TUIC / Snell / HTTP / SOCKS5 / AnyTLS |
| 🧹 **智能去重** | MD5(协议特征) | 重复率 < 1% |
| ⚡ **四层验证** | TCP Ping → 协议握手 → Clash测速 → TCP补充 | 分层递进，层层收紧 |
| 🌏 **IP地理定位** | GeoLite2 本地库 + ML_OK 批量回退 | 纯IP节点也能正确标记区域 |
| 🔄 **多URL验证** | gstatic + Cloudflare + Apple + captive.apple | 消除单URL不可达误杀 |
| 🔁 **失败重试** | Clash测速失败自动重试 | 减少网络抖动误杀 |
| 🚀 **异步采集** | httpx AsyncClient + 域名级限流 | 采集效率大幅提升 |
| 🧠 **智能历史** | 节点历史可用性追踪 + 源历史动态权重 | 优质源持续加权，劣质源自动降权 |
| 🔍 **质量过滤** | CN域名黑名单 + 非代理端口过滤 + 大陆友好性评分 | 排除直连/中转/低质量节点 |

---

## 🏗️ 架构说明

```
ZRONG/
├── crawler.py              # 主入口，加载配置 + 调度 core.main_flow
├── core/
│   ├── main_flow.py        # 主流程编排（入口函数 main()）
│   ├── stages/             # 流水线阶段（Phase C 重构）
│   │   ├── dedup.py        # 同服务器跨协议去重
│   │   ├── geo_prequery.py # IP 地理预查询
│   │   ├── tcp_test.py     # TCP 队列构建 / 并发测试 / 排序
│   │   ├── speed_test.py   # Clash 代理测速 + TCP 补充保底
│   │   └── output.py       # 配额选择 / clean / 写文件 / Telegram 通知
│   ├── collector.py        # 节点采集（TG/Fork/订阅源 + 去重 + 权重）
│   ├── validator.py        # 节点验证与去重（域名/IP/协议）
│   ├── scorer.py           # 节点评分（大陆友好度 + 协议 + 端口）
│   ├── filter.py           # 质量过滤 + 最终排序
│   ├── clash.py            # ClashManager（下载/配置/测速/出口IP检测）
│   ├── history.py          # 历史记录（节点可用性 + 源动态权重）
│   ├── output.py           # 协议链接格式化（全12种协议）
│   └── namer.py            # 节点命名（emoji区域 + 延迟 + 评分）
├── network/
│   ├── client.py           # httpx同步/异步客户端（连接池 + 重试）
│   ├── tcp.py              # TCP连接验证（丢包率 + 延迟测量）
│   ├── dns.py              # DNS解析（线程安全缓存）
│   ├── geo.py              # GeoIP查询 + 智能限流
│   └── tls.py              # TLS握手验证
├── sources/
│   ├── telegram.py         # Telegram频道爬虫
│   ├── github.py           # GitHub Fork发现
│   ├── subscription.py     # 订阅源抓取（同步/异步）
│   └── config.py           # 配置访问层（运行时从 constants 快照）
├── config/
│   ├── constants.py        # 全局常量定义（Phase A 重构，38个 os.getenv）
│   ├── cn_cidr_data.json   # 中国大陆 CIDR 数据（Phase B 重构，4232条）
│   └── __init__.py         # 规则配置加载（rules.yaml）
├── cn_cidr_data.py         # CIDR 数据懒加载（从 JSON 按需构建 IPv4Network）
└── parsers/
    └── *.py                # 协议解析器（12种协议）
```

---

## 🎯 快速部署指南

### 1️⃣ Fork 并配置

```
1. 点击右上角 Fork 本仓库
2. Settings → Secrets and variables → Actions
3. 添加以下环境变量：
```

| 变量名 | 说明 | 获取方式 |
|--------|------|---------|
| `BOT_TOKEN` | Telegram Bot Token | @BotFather 创建 |
| `CHAT_ID` | 通知目标 ID | @userinfobot 查询 |
| `GITHUB_REPOSITORY` | 仓库路径 | 自动填充，无需手动添加 |

### 2️⃣ 触发运行

```
1. 进入 Actions 页面
2. 选择 "Update Subscription Nodes"
3. 点击 "Run workflow"
```

---

## 📈 运行结果示例

```
==================================================
🚀 ZRONG v29 - 智能订阅聚合
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
==================================================

[TG] 爬取 Telegram 频道（优先）...
[SEARCH] GitHub Fork 发现...
[LOAD] 加载固定订阅源（补充）...
[STAT] 源权重排序完成
[WEB] 使用异步抓取模式...
[SEARCH] 节点质量过滤...
[STAT] 采集统计: TG=34, Fork=1500, 固定=81, 总URL=1615
[OK] 质量过滤：5075 → 4191 个
[OK] 同服务器跨协议去重：4191 → 3425 个
[GEO] 预查询 IP 地理位置...
[SPEED] 第一层：TCP 延迟测试...
[STAT] TCP测试队列：400 亚洲 + 100 非亚洲 = 500 总计
[START] 真实代理测速（分批）...
[PACKAGE] 第1批：202 个节点...
[PASS] 🇭🇰1-145ms | [PASS] 🇯🇵1-89ms | [PASS] 🇸🇬1-210ms
...
最终：150 个节点

📊 统计结果
--------------------------------------------------
• 总订阅：1615 | 原始：5075 | 过滤：4191 | TCP：500 | 最终：150
• 亚洲：90 个 (60%) ← 亚洲优先配额保障
--------------------------------------------------
```

---

## 🌐 客户端使用方法

### 推荐导入地址

```
📄 YAML 配置: https://raw.githubusercontent.com/litywang/ZRONG/main/proxies.yaml
📋 Base64 订阅: https://raw.githubusercontent.com/litywang/ZRONG/main/subscription.txt
🔍 网页查看: https://github.com/litywang/ZRONG/blob/main/proxies.yaml
```

### 支持的客户端

| 客户端 | 导入格式 | 推荐地址 |
|--------|---------|---------|
| Clash | YAML | `proxies.yaml` |
| Clash Meta | YAML | `proxies.yaml` |
| Surge | Base64 TXT | `subscription.txt` |
| Shadowrocket | Base64 TXT | `subscription.txt` |
| Stash | YAML | `proxies.yaml` |
| V2rayN | Base64 TXT | `subscription.txt` |

---

## ⚙️ 性能参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_WORKERS` | 60 | 并发线程数 |
| `FETCH_WORKERS` | 150 | 异步抓取并发数 |
| `USE_ASYNC_FETCH` | 1 | 启用异步抓取 |
| `TIMEOUT` | 12s | 请求超时 |
| `MAX_LATENCY` | 800ms | TCP 延迟阈值（亚洲放宽至1800ms） |
| `MAX_PROXY_LATENCY` | 5000ms | 代理延迟阈值 |
| `MAX_FETCH_NODES` | 5000 | 抓取上限 |
| `MAX_TCP_TEST_NODES` | 500 | TCP 测试上限 |
| `MAX_PROXY_TEST_NODES` | 1000 | 代理测试上限（分批） |
| `MAX_FINAL_NODES` | 150 | 最终输出上限 |
| `TARGET_ASIA_RATIO` | 0.45 | 亚洲节点目标比例 |
| `ASIA_MIN_COUNT` | 60 | 亚洲节点保底数量 |

### 环境变量覆盖

所有参数均可通过 GitHub Actions 环境变量覆盖，无需修改代码：

```yaml
env:
  USE_ASYNC_FETCH: 1
  MAX_FINAL_NODES: 150
  TARGET_ASIA_RATIO: 0.45
```

---

## ❓ FAQ 常见问题

<details>
<summary><b>Q: Telegram 爬取失败怎么办？</b></summary>

1. 检查频道是否为公开状态（非私密/已冻结）
2. 手动访问 https://t.me/s/channel 确认可打开
3. 尝试切换频道列表中的其他活跃频道
</details>

<details>
<summary><b>Q: 节点数量太少如何优化？</b></summary>

1. 放宽 `MAX_PROXY_LATENCY`（如改为 8000）
2. 增加 `MAX_FINAL_NODES`（如改为 200）
3. 添加更多固定订阅源到 `sources.yaml`
4. 增加 Telegram 频道数量
</details>

<details>
<summary><b>Q: 节点区域全显示 🌐 怎么办？</b></summary>

已内置 GeoLite2 本地数据库，纯 IP 节点也能正确识别区域。回退使用 ML_OK 批量查询。
</details>

<details>
<summary><b>Q: 如何避免 503 错误封禁？</b></summary>

1. 已内置 SmartRateLimiter 域名级限流
2. 异步抓取有并发上限控制
3. 降低 `FETCH_WORKERS`
</details>

---

## 📜 更新日志

### v29 (2026-06) - 🔧 Phase A/B/C 模块化流水线重构
- ✅ **Phase A**：crawler.py 常量下沉 → `config/constants.py`（271行→205行），消除全局命名空间
- ✅ **Phase B**：`cn_cidr_data.py` 硬编码列表 → `config/cn_cidr_data.json` 懒加载（4242行→47行，-99%）
- ✅ **Phase C**：`main_flow.py` 单块 → `core/stages/` 流水线（dedup/geo_prequery/tcp_test/speed_test/output）
- ✅ **sources/config.py**：运行时从 `constants` 快照配置，函数式访问器隔离变量名遮蔽问题
- ✅ **全协议格式化**：12种协议链接格式化
- ✅ **GeoLite2本地库**：离线IP地理查询，零API依赖
- ✅ **Asia配额调整**：目标比例 60% → 45%，保底数量不变

### v28 (2026-06) - 🏗️ 模块化重构版
- ✅ **代码模块化重构**：core/ + network/ + sources/ + config/ 分层解耦
- ✅ **四层验证体系**：TCP Ping → 协议握手 → Clash测速 → TCP补充
- ✅ **智能历史系统**：节点可用性追踪 + 源动态权重
- ✅ **亚洲优先配额**：强制≥60%，上限75%，保底60个
- ✅ **ClashManager**：下载/配置/测速/出口IP检测
- ✅ **网络工具包**：httpx同步/异步客户端 + DNS缓存 + TLS握手

### v28.39 (2026-04-27) - 🔧 架构重构版
- ✅ **代码模块化**：parsers/ 协议解析包 + sources/ 抓取包 + utils.py 工具函数
- ✅ **智能去重修复**：generate_unique_id 包含协议类型和路径
- ✅ **节点后缀更新**：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶（哥特体）
- ✅ **延迟导入解耦**：避免循环依赖

### v28.16 (2026-04-24) - 🇭🇰 亚洲优先版
- ✅ **亚洲节点强制≥60%**：配额制分配
- ✅ **亚洲延迟放宽**：TCP/代理测速均放宽1.5倍
- ✅ **扩展亚洲区域检测**：MO/MN/KH/LA/MM/BN/NP/LK/BD 等

### v28.7 (2026-04-21) - 🎯 高可用版
- ✅ **多URL测速验证**：gstatic + Cloudflare + Apple
- ✅ **Clash 失败重试**：减少网络抖动误杀

### v28.6 (2026-04-21) - 🔒 TCP 层收紧版
- ✅ **协议握手验证**：vmess/vless/trojan TLS握手、ss/ssr静默响应
- ✅ **MAX_LATENCY 收紧**：10000ms → 3000ms

### v28.5 (2026-04-21) - 🔧 分批测速修复版
- ✅ **Clash 分批测速**：避免 Mihomo 崩溃
- ✅ **异步抓取层**：httpx AsyncClient

---

## 🔧 本地调试

```bash
# 克隆仓库
git clone https://github.com/litywang/ZRONG.git
cd ZRONG

# 安装依赖
pip install requests pyyaml urllib3 httpx httpx[http2] geoip2 maxminddb

# 直接运行
python crawler.py

# 启用异步抓取
USE_ASYNC_FETCH=1 python crawler.py

# Docker 部署
docker build -t zrong .
docker run -e BOT_TOKEN=x -e CHAT_ID=y zrong
```

---

## 📄 开源许可

**MIT License** - 自由商用及修改，请保留作者署名 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶

> **免责声明**: 本项目为开源技术工具，仅供学习研究网络协议与数据传输技术。请遵守当地法律法规，合理合法使用。

---

<div align="center">
<p><strong>✨ 如果觉得有帮助，请给我 ⭐ Star 鼓励一下!</strong></p>
<p><strong>© 2026 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 All Rights Reserved.</strong></p>
</div>
