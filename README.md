# 🚀 ZRONG —— 智能订阅聚合工具 v28.7

> 🌟 **极致 · 稳定 · 精准 · 高效** | GitHub Actions 全自动化节点筛选平台
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度重构
> **v28.7 高可用版：IP地理定位 + 多URL验证 + 协议握手检测 + 异步抓取**

[![GitHub stars](https://img.shields.io/github/stars/litywang/ZRONG?style=flat-square)](https://github.com/litywang/ZRONG/stargazers)
[![GitHub workflow](https://img.shields.io/github/actions/workflow/status/litywang/ZRONG/update.yml?style=flat-square)](https://github.com/litywang/ZRONG/actions)
[![License](https://img.shields.io/github/license/litywang/ZRONG?style=flat-square)](LICENSE)

---

## 📌 核心特性总览

| 维度 | 功能亮点 | 技术实现 |
|------|----------|---------|
| 🔥 **多源采集** | Telegram + GitHub Fork + 固定订阅源(63) | 三路并行发现 + 异步抓取 |
| 🇨🇳 **内地优先** | 国内维护源优先加载 | ermaozi / peasoft 等 |
| 📄 **双格式解析** | TXT 协议链接 + YAML 配置 | 自动识别并行处理 |
| 🔗 **全协议支持** | 12种协议 | VMess / VLESS / Trojan / SS / SSR / Hysteria2 / Hysteria / TUIC / Snell / HTTP / SOCKS5 / AnyTLS |
| 🧹 **智能去重** | MD5(协议特征) | 重复率 < 1% |
| 🔍 **质量过滤** | 排除过期/测试/高倍率节点 | 借鉴 wzdnzd/aggregator |
| ⚡ **四层验证** | TCP Ping → 协议握手 → Clash测速 → TCP补充 | 分层递进，层层收紧 |
| 🌏 **IP地理定位** | ip-api.com 批量查询 | 纯IP节点也能正确标记区域 |
| 🔄 **多URL验证** | gstatic + Cloudflare + Apple | 消除单URL不可达误杀 |
| 🔁 **失败重试** | Clash测速失败自动重试1次 | 减少网络抖动误杀 |
| 🚀 **异步抓取** | httpx AsyncClient | 抓取效率提升 |

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
🚀 ZRONG v28.7 - 高可用版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
==================================================

🔍 GitHub Fork 发现...
   📦 wzdnzd/aggregator: 30 forks
✅ Fork 来源：1500 个

📱 爬取 Telegram 频道（32频道）...
✅ Telegram 订阅：8 个

📥 加载固定订阅源（63个）...
✅ 固定订阅源：63 个

📊 总订阅源：1571 个

📥 异步抓取节点...
   进度: 100/1571 | 节点: 5000
✅ 唯一节点：5000 个

🔍 质量过滤：5000 → 4200 个

🌍 IP 地理位置预查询...
   🌍 IP 地理位置查询：100 个（已缓存 85）

⚡ 第一层：TCP 延迟测试 + 协议握手验证...
✅ 第一层合格：600 个（亚洲：240）

🚀 真实代理测速（分批 600/批，40并发，多URL+重试）...
   ✅ 🇭🇰1-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | ⚡145ms
   ✅ 🇯🇵1-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | ⚡89ms
   ✅ 🇸🇬1-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | ⚡210ms

✅ 最终：150 个节点

📊 统计结果
--------------------------------------------------
• 总订阅：1571 | 原始：5000 | 过滤：4200 | TCP：600 | 最终：150
• 亚洲：68 个 (45%)
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
| `FETCH_WORKERS` | 100 | 抓取并发数 |
| `USE_ASYNC_FETCH` | 1 | 启用异步抓取 |
| `TIMEOUT` | 8s | 请求超时 |
| `MAX_LATENCY` | 3000ms | TCP 延迟阈值（v28.6 收紧） |
| `MAX_PROXY_LATENCY` | 3000ms | 代理延迟阈值 |
| `MAX_FETCH_NODES` | 5000 | 抓取上限 |
| `MAX_TCP_TEST_NODES` | 1200 | TCP 测试上限 |
| `MAX_PROXY_TEST_NODES` | 600 | 代理测试上限（分批） |
| `MAX_FINAL_NODES` | 150 | 最终输出上限 |

### 环境变量覆盖

所有 `MAX_*` 参数和 `USE_ASYNC_FETCH` 均可通过 GitHub Actions 环境变量覆盖，无需修改代码：

```yaml
env:
  USE_ASYNC_FETCH: 1
  MAX_FINAL_NODES: 200
  MAX_PROXY_LATENCY: 3000
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

1. 放宽 `MAX_PROXY_LATENCY`（如改为 5000）
2. 增加 `MAX_FINAL_NODES`（如改为 200）
3. 添加更多固定订阅源到 `sources.yaml`
4. 增加 Telegram 频道数量
</details>

<details>
<summary><b>Q: 节点区域全显示 🌐 怎么办？</b></summary>

v28.6 已加入 IP 地理位置查询（ip-api.com），纯 IP 节点也能正确识别区域。如仍显示 🌐，可能是 IP 查询超时，可检查网络环境。
</details>

<details>
<summary><b>Q: 如何避免 503 错误封禁？</b></summary>

1. 降低请求频率
2. 减少并发数
3. 使用 SmartRateLimiter 独立域名限流
</details>

---

## 📜 更新日志

### v28.7 (2026-04-21) - 🎯 高可用版
- ✅ **多URL测速验证**：gstatic + Cloudflare + Apple，任一成功即通过
- ✅ **Clash 失败重试**：首次失败后等 0.5s 重测，减少网络抖动误杀
- ✅ **测速并发翻倍**：20→40 线程，加快测速速度
- ✅ **Geo 感知排序**：IP 地理位置已知节点优先送入 Clash 测速

### v28.6 (2026-04-21) - 🔒 TCP 层收紧版
- ✅ **协议握手验证**：TCP 不只验端口，验证 vmess/vless/trojan 的 TLS 握手、ss/ssr 的静默响应、http/socks5 的协议握手
- ✅ **MAX_LATENCY 收紧**：10000ms → 3000ms，甩掉高延迟废节点
- ✅ **IP 地理位置查询**：ip-api.com 批量查询，纯 IP 节点也能标记区域

### v28.5 (2026-04-21) - 🔧 分批测速修复版
- ✅ **Clash 分批测速**：600节点/批，Clash 停启循环，避免 Mihomo 崩溃
- ✅ **CANDIDATE_URLS 条件修复**：63 个固定订阅源从 v28.0 起未生效，已修复
- ✅ **异步抓取层**：httpx AsyncClient 抓取，提升效率

### v28.3 (2026-04-21) - 🎯 可用率修复版
- ✅ **恢复 gstatic.com**：国际出口才是代理核心指标
- ✅ **保留 3s 阈值**：剔除极慢不稳定节点

### v28.0 (2026-04-20) - 🔧 性能优化版
- ✅ **sources.yaml 外置配置**：订阅源配置与代码分离
- ✅ **TCP 测试并发提升**：200 并发上限
- ✅ **ws-opts Host 检测**：WebSocket 域名精确识别

### v27.0 (2026-04-15) - 🔧 区域识别修复版
- ✅ **修复 TLD 匹配逻辑**：避免 .co/.cl 等后缀误匹配

### v26.0 (2026-04-10) - 🇨🇳 内地优化版
- ✅ **内地优质源优先**：ermaozi / peasoft / aiboboxx 等

### v25.0 (2026-04-05) - ⚡ Reality 优先版
- ✅ **Reality 节点优先排序**
- ✅ **协议评分加权**

---

## 🔧 本地调试

```bash
# 克隆仓库
git clone https://github.com/litywang/ZRONG.git
cd ZRONG

# 安装依赖
pip install requests pyyaml urllib3 httpx httpx[http2]

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

> **法律声明**: 本工具仅供技术交流学习使用，严禁用于非法活动。作者不承担任何法律责任。

---

<div align="center">
<p><strong>✨ 如果觉得有帮助，请给我 ⭐ Star 鼓励一下!</strong></p>
<p><strong>© 2026 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 All Rights Reserved.</strong></p>
</div>
