# 🚀 ZRONG —— 智能订阅聚合工具 v28.16

> 🌟 **极致 · 稳定 · 精准 · 高效** | GitHub Actions 全自动化节点筛选平台
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度重构
> **v28.16 亚洲优先版：IP地理定位 + 多URL验证 + 协议握手检测 + 异步抓取 + 亚洲节点≥60%**

[![GitHub stars](https://img.shields.io/github/stars/litywang/ZRONG?style=flat-square)](https://github.com/litywang/ZRONG/stargazers)
[![GitHub workflow](https://img.shields.io/github/actions/workflow/status/litywang/ZRONG/update.yml?style=flat-square)](https://github.com/litywang/ZRONG/actions)
[![License](https://img.shields.io/github/license/litywang/ZRONG?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue?style=flat-square)](https://www.python.org/)
[![Asia Priority](https://img.shields.io/badge/Asia%20Priority-%E2%89%A560%25-success?style=flat-square)]()

---

## 📌 核心特性总览

| 维度 | 功能亮点 | 技术实现 |
|------|----------|---------|
| 🔥 **多源采集** | Telegram + GitHub Fork + 固定订阅源(63+) | 三路并行发现 + 异步抓取 |
| 🇨🇳 **内地优先** | 国内维护源优先加载 | ermaozi / peasoft / aiboboxx 等 |
| 🇭🇰 **亚洲优先** | 亚洲节点强制≥60%配额 | 多层加权 + 延迟放宽 + 保底机制 |
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
```

---

## 🔧 技术架构

```
┌─────────────────────────────────────────┐
│           ZRONG v28.16 架构图            │
├─────────────────────────────────────────┤
│  输入层                                  │
│  ├── Telegram 频道 (32+)                 │
│  ├── GitHub Fork 发现 (60 repos)         │
│  └── 固定订阅源 (63 URLs)                │
├─────────────────────────────────────────┤
│  处理层                                  │
│  ├── 异步抓取 (httpx + HTTP/2)           │
│  ├── 协议解析 (12种协议)                  │
│  ├── 智能去重 (MD5)                      │
│  └── IP地理定位 (ip-api.com)             │
├─────────────────────────────────────────┤
│  验证层                                  │
│  ├── TCP Ping 测试                       │
│  ├── 协议握手检测                        │
│  ├── Clash 测速 (gstatic/CF/Apple)       │
│  └── TCP 补充测试                        │
├─────────────────────────────────────────┤
│  输出层                                  │
│  ├── subscription.txt (Base64)           │
│  └── proxies.yaml (Clash)                │
└─────────────────────────────────────────┘
```

---

## 📋 更新日志

### v28.16 (2026-04-23)
- 【关键BUG修复】亚洲前置排序后又被sort覆盖
- 【配额制节点选择】分亚洲/非亚洲两组排序，按60%配额合并
- 【is_asia增强】新增IP地理位置+SNI+域名TLD三级检测
- 【TCP测试优化】亚洲节点优先进入测试队列
- 【延迟放宽】亚洲TCP补充1500ms，非亚洲800ms
- 【权重提升】ASIA_PRIORITY_BONUS 50→80

---

## 🤝 贡献指南

欢迎提交 Issue 和 PR！请确保：
1. 代码通过 `bandit` 安全检查
2. 异步路径优先使用 `httpx`
3. 新增源优先放入 `sources.yaml`

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

**Made with ❤️ by 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶**
