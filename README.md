# 🚀 Anftlity-Crawler —— 智能订阅聚合工具 v23.0

> 🌟 **极致 · 稳定 · 精准 · 高效** | GitHub Actions 全自动化节点筛选平台  
> 基于 wzdnzd/aggregator + mahdibland/V2RayAggregator 核心逻辑深度重构的下一代方案  
> **v23.0 终极优化版：12种协议支持 + 扩展订阅源 + 放宽测试参数 + 增强并发 + 产出300节点**

---

## 📌 核心特性总览

| 维度 | 功能亮点 | 技术实现 |
|------|----------|---------|
| 🔥 **多源采集** | Telegram+GitHub Fork+固定源 | 正则增强版爬虫 |
| 🇨🇳 **内地优先** | 国内维护源优先加载 | ermaozi/peasoft/aiboboxx 等 |
| 📄 **双格式解析** | TXT 链接 + YAML 配置 | 自动识别并行处理 |
| 🔗 **全协议支持** | 12种协议链接 + YAML节点 | VMess/VLESS/Trojan/SS/SSR/Hysteria2/Hysteria/TUIC/Snell/HTTP/SOCKS5/AnyTLS |
| 🧹 **智能去重** | MD5(协议特征) | 重复率降至 <1% |
| 🔍 **质量过滤** | 排除过期/测试/高倍率 | 借鉴 wzdnzd/aggregator |
| ⚡ **三层检测** | TCP → Speedtest → 输出 | 分层验证架构 |
| 🌏 **区域感知** | HK/TW/JP/SG/KR/US/OT | 地域加权排序 |
| 🛡️ **安全防护** | 域名级限流+重试机制 | SmartRateLimiter |
| 🚀 **零验证直拉** | 跳过 HEAD 检测直接 fetch | 避免 US 服务器超时丢源 |
| 📤 **多格式输出** | YAML + TXT | 客户端全覆盖 |

---

## 🎯 快速部署指南

### 1️⃣ 环境配置
```bash
# Fork 项目后添加环境变量
Settings > Secrets and variables > Actions
```
| 变量名 | 说明 | 获取方式 |
|--------|------|---------|
| `BOT_TOKEN` | Telegram Bot Token | @BotFather 创建 |
| `CHAT_ID` | 通知目标ID | @Userinfobot 查询 |
| `GITHUB_REPOSITORY` | 仓库路径 | 自动填充 |

### 2️⃣ 提交运行
```bash
git add .
git commit -m "🚀 初始化 Anftlity-Crawler v23.0"
git push
# 触发 Workflow → Update Subscription Nodes
```

---

## ⚙️ 性能参数说明

| 参数 | v22.5 | v23.0 | 作用 |
|------|--------|------|------|
| `MAX_WORKERS` | 40 | **60** | 并发线程数 ↑50% |
| `FETCH_WORKERS` | 80 | **100** | 抓取并发 ↑25% |
| `REQUESTS_PER_SECOND` | 5.0 | **5.0** | 请求频率 |
| `TIMEOUT` | 15s | **8s** | 超时缩短，快速跳过 |
| `MAX_RETRIES` | 3 | **1** | 快速失败，减少等待 |
| `MAX_LATENCY` | 5000ms | **10000ms** | TCP延迟阈值放宽 |
| `MIN_PROXY_SPEED` | 0.005 MB/s | **0.0 MB/s** | 速度要求移除 |
| `MAX_PROXY_LATENCY` | 10000ms | **20000ms** | 代理延迟阈值放宽 |
| `MAX_FETCH_NODES` | 3000 | **5000** | 抓取上限 ↑67% |
| `MAX_TCP_TEST_NODES` | 800 | **2000** | TCP测试上限 ↑150% |
| `MAX_PROXY_TEST_NODES` | 200 | **500** | 代理测试上限 ↑150% |
| `MAX_FINAL_NODES` | 150 | **300** | 最终输出上限 ↑100% |
| `MAX_FORK_REPOS` | 30 | **30** | 每个base repo取fork数 |
| `MAX_FORK_URLS` | 1500 | **1500** | Fork URL总数上限 |

> 💡 **v23.0 核心优化**:
> - **扩展订阅源**：新增 16 个高质量订阅源（adiwzx/xingsin/vxiaodong/changfengoss 等）
> - **扩展 Telegram 频道**：新增 20 个活跃频道（V2rayNG_Latest/v2ray_ssr/proxylist 等）
> - **扩展 GitHub Fork 发现**：新增 13 个仓库（adiwzx/freefq/Pawdroid 等）
> - **放宽测试阈值**：移除速度要求，延迟阈值翻倍，让更多节点通过
> - **提升并发**：MAX_WORKERS 40→60，FETCH_WORKERS 80→100

---

## 📊 核心优化成果

| 指标 | v22.0 | v22.5 | **v23.0** | 提升 |
|------|-------|-------|-----------|------|
| 支持协议数 | 7种 | 12种 | **12种** | — |
| 订阅源数量 | 18个 | 25个 | **41个** | ↑ 64% |
| Telegram 频道 | 15个 | 30个 | **50个** | ↑ 67% |
| GitHub Fork 仓库 | 8个 | 15个 | **28个** | ↑ 87% |
| 最终节点上限 | 80 | 150 | **300** | ↑ 275% |
| 代理测试上限 | 80 | 200 | **500** | ↑ 525% |
| 速度要求 | 0.01 MB/s | 0.005 MB/s | **无限制** | 最宽松 |
| 延迟阈值 | 2000ms | 5000ms | **10000ms** | ↑ 400% |

---

## 🔬 技术架构详解

### 智能订阅源发现系统
```python
# 支持三大数据源并行采集
TELEGRAM_CHANNELS = [
    "v2ray_free", "freev2rayng", "v2rayng_free", "sub_free",
    "vmessfree", "vlessfree", "trojanfree", "ssfree",
    "proxiesdaily", "clashnode", "freeclash", "freeproxy",
    "v2ray_share", "v2raydaily", "clashmeta", "proxies_free",
    "mr_v2ray", "wxdy666", "dns68", "jiedianbodnn",
    "AlphaV2ray", "V2rayN", "proxies_share", "freev2ray",
    "clashvpn", "v2rayngvpn", "freeVPNjd", "hysteria2_free",
    "tuic_free", "ssr_free", "http_proxy", "socks5_free",
    # v23.0 新增
    "V2rayNG_Latest", "v2ray_ssr", "proxylist", "freenode",
    "clash_free", "vpngate", "proxy_daily", "free_proxy_list",
    "shadowsocks_free", "trojan_free", "vless_free", "vmess_free",
    "hysteria_free", "tuic_nodes", "warp_free", "wireguard_free",
    "snell_free", "anytls_free", "proxy_hub", "node_share"
]

GITHUB_BASE_REPOS = [
    "wzdnzd/aggregator",
    "mahdibland/V2RayAggregator",
    "PuddinCat/BestClash",
    "MrMohebi/xray-proxy-grabber-telegram",
    # v23.0 新增
    "adiwzx/freev2ray", "freefq/free", "Pawdroid/Free-servers",
    "Epodonios/v2ray-configs", "barry-far/V2ray-Config",
    "ermaozi/get_subscribe", "peasoft/NoMoreWalls",
    "aiboboxx/v2rayfree", "mfuu/v2ray", "kxswa/v2rayfree"
]
```

### 双格式自动识别解析
```
订阅源 URL → fetch 内容
               ├─ YAML 格式 (含 proxies:/Proxy:) → yaml.safe_load → 提取 proxies 列表
               ├─ Base64 编码 → 自动解码 → 逐行解析协议链接
               └─ 纯文本 → 逐行解析协议链接
                              ├─ vmess:// → VMess 节点
                              ├─ vless:// → VLESS 节点
                              ├─ trojan:// → Trojan 节点
                              ├─ ss:// → Shadowsocks 节点
                              ├─ ssr:// → ShadowsocksR 节点
                              ├─ hysteria2:// / hy2:// → Hysteria2 节点
                              ├─ hysteria:// → Hysteria 节点
                              ├─ tuic:// → TUIC 节点
                              ├─ snell:// → Snell 节点
                              ├─ http:// / https:// → HTTP 节点
                              ├─ socks5:// → SOCKS5 节点
                              └─ anytls:// → AnyTLS 节点
```

### 三层检测机制
```
全部节点 → 第一层:TCP Ping (100并发) → 第二层:Clash 真实测速 → 输出最终节点
              ↓                           ↓
          延迟<10s                    延迟<20s（无速度要求）
```

### 零验证直拉策略
```
旧方案：URL → HEAD 验证(5s超时) → 失败则丢弃 ❌ US 服务器大量超时
新方案：URL → 直接 fetch → 有内容就解析，无内容自然淘汰 ✅ 零丢源
```

---

## 📈 运行结果示例

```text
==================================================
🚀 聚合订阅爬虫 v23.0 - 终极优化版
作者：𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 | Version: 23.0
==================================================

🔍 GitHub Fork 发现... (跳过验证，直接拉取)
   📦 wzdnzd/aggregator: 30 forks
   📦 mahdibland/V2RayAggregator: 30 forks
   🔗 构建 1500 个候选 URL（跳过验证，直接拉取）...
✅ GitHub Fork 共发现 1500 个候选来源

📱 爬取 Telegram 频道... (并行100线程)
✅ Telegram 订阅：50 个

📥 加载固定订阅源... (跳过验证，直接拉取)
✅ 固定订阅源：41 个

📥 抓取节点... (TXT + YAML 双格式并行)
   进度: 100/1591 | 节点: 5000 (YAML源: 80, TXT源: 60)
✅ 唯一节点：5000 个

⚡ 第一层：TCP 延迟测试... (100并发)
✅ 第一层合格：800 个（亚洲：320，占40%）

🚀 真实代理测速...
   ✅ HK01-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡145ms|📥12.5MB
   ✅ JP02-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡89ms|📥18.5MB
   ✅ SG03-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶|⚡210ms|📥8.2MB

✅ 最终：300 个节点

--------------------------------------------------
📊 统计结果
--------------------------------------------------
• Fork: 1500 | Telegram: 50 | 固定：41 | 总订阅：1591
• 原始：5000 | TCP: 800 | 最终：300
• 亚洲：135 个 (45%)
• 耗时：~25 分钟
--------------------------------------------------
```

---

## 🌐 客户端使用方法

### 推荐导入地址
```
YAML 配置: https://raw.githubusercontent.com/litywang/ZRONG/main/proxies.yaml
Base64 订阅: https://raw.githubusercontent.com/litywang/ZRONG/main/subscription.txt
网页查看：https://github.com/litywang/ZRONG/blob/main/proxies.yaml
```

### 本地调试命令
```bash
# 克隆仓库
git clone https://github.com/litywang/ZRONG.git

# 安装依赖
pip install requests pyyaml urllib3

# 直接运行
python crawler.py

# Docker 部署
docker build -t anftlity-crawler .
docker run -e BOT_TOKEN=x -e CHAT_ID=y anftlity-crawler
```

---

## ❓ FAQ 常见问题

<details>
<summary><b>Q: Telegram 爬取失败怎么办？</b></summary>
A: 
1. 检查频道是否为公开状态（非私密/已冻结）
2. 手动访问 https://t.me/s/channel 确认可打开
3. 尝试切换频道列表中的其他活跃频道
4. 查看 logs 日志定位具体失败频道
</details>

<details>
<summary><b>Q: 节点数量太少如何优化？</b></summary>
A: 
v23.0 已大幅放宽所有参数：
1. 速度要求已移除（MIN_PROXY_SPEED=0.0）
2. 延迟阈值已放宽至 10000ms
3. 最终节点上限已提升至 300
4. 如仍不足，可继续增加 CANDIDATE_URLS 中的订阅源
</details>

<details>
<summary><b>Q: 固定订阅源拉不到节点？</b></summary>
A: 
v23.0 采用零验证直拉策略，不再需要 HEAD 验证。
如果仍然拉不到，可能是：
1. 源站本身已失效 — 访问 URL 确认内容存在
2. GitHub Actions 服务器网络问题 — 查看 Action 日志
3. 源格式为 YAML 但 proxies 字段为空 — 属于正常情况
</details>

<details>
<summary><b>Q: 如何避免 503 错误封禁？</b></summary>
A: 
1. 降低请求频率：`REQUESTS_PER_SECOND=0.3`
2. 减少并发：`MAX_WORKERS=3`
3. 使用代理池：`SmartRateLimiter` 多域名独立限流
</details>

---

## 📜 更新日志

### v23.0 (2026-04-03) - 🚀 终极优化版
- ✅ **扩展订阅源**：新增 16 个高质量订阅源（adiwzx/xingsin/vxiaodong/changfengoss 等）
- ✅ **扩展 Telegram 频道**：新增 20 个活跃频道，总计 50 个
- ✅ **扩展 GitHub Fork 发现**：新增 13 个仓库，总计 28 个 base repo
- ✅ **放宽测试阈值**：移除速度要求，延迟阈值 5000→10000ms，代理延迟 10000→20000ms
- ✅ **提升并发**：MAX_WORKERS 40→60，FETCH_WORKERS 80→100
- ✅ **提升上限**：MAX_FETCH_NODES 3000→5000，MAX_TCP_TEST 800→2000，MAX_PROXY_TEST 200→500，MAX_FINAL 150→300
- ✅ **缩短超时**：TIMEOUT 15s→8s，MAX_RETRIES 3→1，快速跳过无响应源

### v22.5 (2026-04-02) - 🔧 多协议增强版
- ✅ **新增协议支持**：SSR / Snell / HTTP / SOCKS5 / AnyTLS 解析
- ✅ **简洁节点命名**：`HK1-𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶` 格式，无后缀
- ✅ **增强区域检测**：40+ 国家/地区识别，减少 OT 匹配

### v22.4 (2026-04-01) - ⚡ 性能极速版
- ✅ **大幅精简源**：GitHub 仓库 18→9，固定订阅 23→10，Telegram 32→12
- ✅ **高并发优化**：MAX_WORKERS 15→30，FETCH_WORKERS 50，TCP 并发 100
- ✅ **严格阈值**：MIN_PROXY_SPEED 0.01→0.05，MAX_LATENCY 2000→1500ms
- ✅ **目标耗时**：从 2h+ 优化至 < 30 分钟

### v22.3 (2026-04-01) - 🇨🇳 内地优化版
- ✅ **内地优质源优先**：ermaozi/peasoft/aiboboxx/mfuu/kxswa 等国内维护源优先加载
- ✅ **节点质量过滤**：排除过期/测试/高倍率/内地直连节点（借鉴 wzdnzd/aggregator）
- ✅ **更多 Telegram 频道**：新增 v2ray_free/freev2rayng 等 16 个内地频道
- ✅ **GitHub Fork 扩展**：新增 6 个国内优质仓库作为 Fork 发现源

### v22.2 (2026-03-31) - 🔧 全协议增强版
- ✅ **YAML 订阅源解析**：自动识别 proxies.yaml / clash.yaml，用 yaml.safe_load 提取
- ✅ **新增协议**：Hysteria2 (hy2://) / Hysteria (v1) / TUIC 三种协议链接解析
- ✅ **零验证直拉**：固定订阅源 + Fork 发现均跳过 HEAD 验证，US 服务器不再丢源
- ✅ **协议覆盖**：VMess / VLESS / Trojan / SS / Hysteria2 / Hysteria / TUIC + YAML 全类型

### v22.0 (2026-03-29) - 终极优化版
- ✅ **Telegram 爬取增强**：支持新版 HTML 结构，正则匹配能力提升
- ✅ **订阅源扩展**：新增 llywhn/v2ray-subscribe + MrMohebi/Fork
- ✅ **算法优化**：SHA256 去重 + 区域加权排序
- ✅ **性能提升**：SmartRateLimiter 独立域名限速

---

## 🌟 社区贡献

| 项目类型 | 描述 | 状态 |
|----------|------|------|
| 🐛 Bug 报告 | 提交详细错误信息 + 日志 | 欢迎提交 |
| 💡 功能建议 | 提出新想法或优化建议 | 积极采纳 |
| 📝 翻译协作 | 多语言文档维护 | 进行中 |
| 🔧 PR 提交 | 代码改进或新特性开发 | 开放合作 |

---

## 📄 开源许可

**MIT License** - 自由商用及修改，请保留作者署名 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶

> **法律声明**: 本工具仅供技术交流学习使用，严禁用于非法活动。作者不承担任何法律责任，使用者需自行承担风险。

---

<div align="center">
<p><strong>✨ 如果觉得有帮助，请给我 ⭐ Star⭐ 鼓励一下!</strong></p>
<p><strong>© 2026 𝔄𝔫𝔣𝔱𝔩𝔦𝔱𝔶 All Rights Reserved.</strong></p>
</div>
