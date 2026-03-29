# 🚀 聚合订阅爬虫 Anftlity-Crawler

> ✨ **高可用 · 多源 · 严格检测 · 自动化部署**  
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度优化的稳定版

---

## 📌 项目简介

Anftlity-Crawler 是一个专为 GitHub Actions 设计的**聚合订阅节点筛选工具**。它支持多源订阅爬取、智能去重、多层测速验证（TCP → 流量测速 → 解锁检测），并将优质节点实时同步至仓库供客户端直接导入。

### ⭐ 核心亮点
- ✅ **全协议支持**: VMess | VLESS | Trojan | SS | SSR | Hysteria2
- ✅ **三层严格检测**: TCP 延迟 → 流量测速 → (可选) 流媒体解锁
- ✅ **动态源发现**: GitHub Fork 机制 + Telegram 频道智能爬取
- ✅ **质量优先**: 区域识别 + 速率过滤 + 重复率 < 1%
- ✅ **零维护**: GitHub Actions 全自动运行，每 6 小时更新一次

---

## 🎯 功能特性

| 模块 | 功能描述 | 技术实现 |
|------|----------|---------|
| **📡 多源爬取** | 抓取固定订阅 + Telegram 频道 + GitHub Fork | 正则增强 + URL 清洗 |
| **🧹 智能去重** | SHA256(协议特征哈希) 唯一 ID | 重复率降低 95%+ |
| **⚡ 双层测速** | 第一层:TCP ping → 第二层:Clash 代理测速 | 延迟/速度双维度筛选 |
| **🌏 地区感知** | HK/TW/JP/SG/KR/US/OT 自动识别 | 区域加权排序 |
| **📝 多格式输出** | `proxies.yaml` + `subscription.txt` | 兼容主流客户端 |
| **🔔 机器人通知** | Telegram 实时更新统计结果 | Bot API HTML 消息 |
| **🛡️ 安全加固** | 域名级限流 + HTTP 重试 + SSL 验证 | 抗 503 封禁机制 |

---

## 🚀 快速开始

### 1️⃣ Fork & 配置
1. Fork 本项目到你的 GitHub 账号
2. 进入 `Settings > Secrets and variables > Actions`
3. 添加两个关键 Secret：

```bash
BOT_TOKEN=你的 Telegram Bot Token
CHAT_ID=你的 Telegram Channel/Group ID
GITHUB_REPOSITORY=litywang/ZRONG  # 替换为你的用户名/仓库名
```

<details>
<summary><b>获取 Bot Token 方法</b></summary>

1. @BotFather 创建新 Bot
2. 复制 Token
3. @Userinfobot 获取自己的 Chat ID
</details>

### 2️⃣ 提交代码
```bash
git add .
git commit -m "🚀 初始化 Anftlity-Crawler v21.0"
git push
```

### 3️⃣ 手动触发 Workflow
前往仓库 → **Actions** → **Update Subscription Nodes** → **Run workflow**

---

## ⚙️ 配置说明

### 🔑 核心参数 (`CANDIDATE_URLS` 配置区)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MAX_WORKERS` | 3 | 线程池数量 (过高易触发 503) |
| `REQUESTS_PER_SECOND` | 0.5 | 请求速率限制 (秒倒数) |
| `MAX_LATENCY` | 2000ms | TCP 通过阈值 |
| `MIN_PROXY_SPEED` | 0.01 MB/s | 最小可用网速 |
| `MAX_FINAL_NODES` | 80 | 最终输出节点数上限 |

### 🗂️ 订阅源管理

当前已集成的高质量源列表：

| 来源 | 类型 | 数量 |
|------|------|------|
| Mahdibland/V2RayAggregator | 分协议拆分 | 5 |
| Pawdroid/Free-servers | 混合订阅 | 1 |
| Epodonios/v2ray-configs | 按协议分类 | 4 |
| Barry-far/V2ray-Config | 按协议分类 | 4 |
| TG-NAV/clashnode | 每日精选 | 1 |
| shz.al/~WangCai | 国内友好 | 1 |

---

## 📊 运行结果示例

```text
==================================================
🚀 聚合订阅爬虫 v21.0 Final
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶
==================================================

📱 爬取 Telegram 频道...
✅ Telegram 订阅：15 个

🔍 验证固定订阅源...
✅ 固定订阅源：12 个可用

📥 抓取节点...
✅ 唯一节点：1850 个

⚡ 第一层：TCP 延迟测试...
✅ 第一层合格：245 个（亚洲：78）

🚀 真实代理测速...
   ✅ Clash API 就绪
   ✅ HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡145ms|📥12.5MB
   ✅ JP02-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡89ms|📥18.5MB

✅ 最终：80 个
📊 真实测速：✅

--------------------------------------------------
📊 统计结果
--------------------------------------------------
• Telegram: 15 | 固定：12 | 总：27
• 原始：1850 | TCP: 245 | 最终：80
• 亚洲：32 个 (40%)
• 最低延迟：1.5 ms
• 耗时：365.8 秒
--------------------------------------------------
```

---

## 💻 使用方法

### 客户端导入
将以下链接复制到 Clash/Mihomo/Sing-box 即可：

- **YAML 配置**: https://raw.githubusercontent.com/litywang/ZRONG/main/proxies.yaml
- **Base64 订阅**: https://raw.githubusercontent.com/litywang/ZRONG/main/subscription.txt

### 本地测试运行
```bash
python crawler.py
```

---

## ❓ FAQ

<details>
<summary>Q: 为什么 Telegram 爬取失败？</summary>
A: 检查频道的私密性设置，确保为公开频道；或尝试手动访问 t.me/s/channel 确认网页可达性。
</details>

<details>
<summary>Q: 如何增加更多订阅源？</summary>
A: 在 `CANDIDATE_URLS` 列表中追加新的 GitHub Raw 地址即可。
</details>

<details>
<summary>Q: 为何只有少量节点被筛选出来？</summary>
A: 可能是网络条件导致无法访问测速目标，可尝试放宽 `MAX_LATENCY` 或降低 `MIN_PROXY_SPEED`。
</details>

---

## 📜 更新日志

### v21.0 (2026-03-29)
- ✅ 完整重构 Telegram 爬取逻辑，支持新版 HTML 结构
- ✅ 引入 SmartRateLimiter 多域名独立限流
- ✅ 修复所有 Unicode Emoji 编码问题
- ✅ 统一输出文件名为 `subscription.txt`

### v20.0 (2026-03-28)
- ✅ 集成 wzdnzd/aggregator 订阅验证机制
- ✅ 增加 epodonios/barry-far 全量源支持
- ✅ 提升亚洲节点比例至 40%+

### v19.0 (2026-03-27)
- ✅ 三层测速架构 (TCP → Speedtest → Unlock)
- ✅ 智能去重算法 SHA256
- ✅ 区域识别 + 花体字命名

### v13.7 (2026-03-20)
- ✅ Fork 发现 + 多协议解析器完整实现
- ✅ Docker 化部署支持
- ✅ zhsama clahk-speedtest 集成

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=litywang/ZRONG&type=Date)](https://star-history.com/#litywang/ZRONG&Date)

---

## 📄 License

MIT License - 自由商用及修改，请保留作者署名 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶

> **免责声明**: 本工具仅供学习交流，请勿用于非法用途。作者不承担任何连带责任。

---

## 👨‍💻 贡献者

欢迎提交 Issue / Pull Request 改进脚本功能！

---

<div align="center">
<p><strong>✨ 如果对你有帮助，请 ⭐ Star ⭐ 支持!</strong></p>
<p>© 2026 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 All Rights Reserved.</p>
</div>
