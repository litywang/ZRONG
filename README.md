# 🚀 ZRONG —— 智能订阅聚合工具 v28.3

> 🌟 **极致 · 稳定 · 精准 · 高效** | GitHub Actions 全自动化节点筛选平台
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度重构
> **v28.1 httpx 高性能版：连接池优化 + 12种协议支持 + 全量优质源 + 产出300+节点**

[![GitHub stars](https://img.shields.io/github/stars/litywang/ZRONG?style=flat-square)](https://github.com/litywang/ZRONG/stargazers)
[![GitHub workflow](https://img.shields.io/github/actions/workflow/status/litywang/ZRONG/update.yml?style=flat-square)](https://github.com/litywang/ZRONG/actions)
[![License](https://img.shields.io/github/license/litywang/ZRONG?style=flat-square)](LICENSE)

---

## 📌 核心特性总览

| 维度 | 功能亮点 | 技术实现 |
|------|----------|---------|
| 🔥 **多源采集** | Telegram + GitHub Fork + 固定订阅源 | 三路并行发现 |
| 🇨🇳 **内地优先** | 国内维护源优先加载 | ermaozi / peasoft 等 |
| 📄 **双格式解析** | TXT 协议链接 + YAML 配置 | 自动识别并行处理 |
| 🔗 **全协议支持** | 12种协议 | VMess / VLESS / Trojan / SS / SSR / Hysteria2 / Hysteria / TUIC / Snell / HTTP / SOCKS5 / AnyTLS |
| 🧹 **智能去重** | MD5(协议特征) | 重复率 < 1% |
| 🔍 **质量过滤** | 排除过期/测试/高倍率节点 | 借鉴 wzdnzd/aggregator |
| ⚡ **三层检测** | TCP Ping → Speedtest → 输出 | 分层验证架构 |
| 🌏 **区域感知** | HK / TW / JP / SG / KR / US 等 | 地域加权排序 |
| 🚀 **httpx 高性能** | 连接池 + Keep-Alive | 网络请求效率提升 |

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
🚀 ZRONG v28.1 - httpx 高性能版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
==================================================

🔍 GitHub Fork 发现...
   📦 wzdnzd/aggregator: 30 forks
✅ Fork 来源：1500 个

📱 爬取 Telegram 频道...
✅ Telegram 订阅：8 个

📥 加载固定订阅源...
✅ 固定订阅源：0 个

📊 总订阅源：1508 个

📥 抓取节点...
   进度: 100/1508 | 节点: 5000
✅ 唯一节点：5000 个

⚡ 第一层：TCP 延迟测试...
✅ 第一层合格：800 个（亚洲：320）

🚀 真实代理测速...
   ✅ HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡145ms|📥12.5MB
   ✅ JP02-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡89ms|📥18.5MB

✅ 最终：300 个节点

📊 统计结果
--------------------------------------------------
• 总订阅：1508 | 原始：5000 | TCP：800 | 最终：300
• 亚洲：135 个 (45%)
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
| `TIMEOUT` | 8s | 请求超时 |
| `MAX_LATENCY` | 10000ms | TCP 延迟阈值 |
| `MAX_PROXY_LATENCY` | 20000ms | 代理延迟阈值 |
| `MAX_FETCH_NODES` | 5000 | 抓取上限 |
| `MAX_TCP_TEST_NODES` | 2000 | TCP 测试上限 |
| `MAX_PROXY_TEST_NODES` | 500 | 代理测试上限 |
| `MAX_FINAL_NODES` | 300 | 最终输出上限 |

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

1. 放宽延迟阈值（需自行修改代码）
2. 增加 Telegram 频道数量
3. 添加更多固定订阅源到 `CANDIDATE_URLS`
</details>

<details>
<summary><b>Q: 如何避免 503 错误封禁？</b></summary>

1. 降低请求频率
2. 减少并发数
3. 使用 SmartRateLimiter 独立域名限流
</details>

---

## 📜 更新日志

### v28.3 (2026-04-21) - 🎯 可用率修复版
- ✅ **恢复 gstatic.com**：baidu.com 直连测不出代理效果，国际出口才是核心指标
- ✅ **保留 3s 阈值**：剔除极慢不稳定节点
- ✅ **TCP 补充改用 MAX_FINAL_NODES**：不再硬编码 180，由参数统一控制

### v28.2 (2026-04-21) - 🎯 可用率优化版（回退）
- ⚠️ baidu.com 思路有误，回退

### v28.1 (2026-04-21) - ⚡ httpx 高性能版
- ✅ **httpx 连接池**：替换 requests，连接复用 + Keep-Alive
- ✅ **移除 HTTP/2 依赖**：避免 GitHub Actions 环境缺少 h2 包

### v28.0 (2026-04-20) - 🔧 性能优化版
- ✅ **sources.yaml 外置配置**：订阅源配置与代码分离
- ✅ **TCP 测试并发提升**：200 并发上限
- ✅ **ws-opts Host 检测**：WebSocket 域名精确识别

### v27.0 (2026-04-15) - 🔧 区域识别修复版
- ✅ **修复 TLD 匹配逻辑**：避免 .co/.cl 等后缀误匹配
- ✅ **移除数字检查限制**：扩大节点来源

### v26.0 (2026-04-10) - 🇨🇳 内地优化版
- ✅ **内地优质源优先**：ermaozi / peasoft / aiboboxx 等
- ✅ **TCP 补充阈值放宽**：亚洲 < 400ms，非亚洲 < 200ms

### v25.0 (2026-04-05) - ⚡ Reality 优先版
- ✅ **Reality 节点优先排序**
- ✅ **协议评分加权**

### v23.0 (2026-04-03) - 🚀 终极优化版
- ✅ **扩展订阅源**：新增 16 个高质量订阅源
- ✅ **扩展 Telegram 频道**：总计 50 个
- ✅ **扩展 GitHub Fork**：总计 28 个 base repo
- ✅ **放宽测试阈值**：移除速度要求

---

## 🔧 本地调试

```bash
# 克隆仓库
git clone https://github.com/litywang/ZRONG.git
cd ZRONG

# 安装依赖
pip install requests pyyaml urllib3 httpx

# 直接运行
python crawler.py

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
