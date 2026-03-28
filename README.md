# 🚀 Clash 节点自动更新

## 功能特点
- ✅ 真实代理测速（通过 Mihomo 内核）
- ✅ 支持 VMess / VLESS / Trojan
- ✅ 亚洲节点优先
- ✅ 自动定时更新（每 4 小时）
- ✅ Telegram 推送通知

## 订阅链接

### Clash.Meta 配置
https://raw.githubusercontent.com/litywang/ZRONG/main/proxies.yaml

### Base64 订阅
https://raw.githubusercontent.com/litywang/ZRONG/main/subscription_base64.txt

## 客户端推荐
| 平台 | 客户端 |
|------|--------|
| Windows | Clash Verge Rev |
| Android | Clash Meta for Android |
| iOS | Shadowrocket / Stash |

## 手动触发更新
1. 进入 Actions 标签页
2. 选择 "Update Clash Nodes"
3. 点击 "Run workflow"

## 配置 Telegram 通知
1. Fork 本仓库
2. Settings → Secrets and variables → Actions
3. 添加 `BOT_TOKEN` 和 `CHAT_ID`
🔧 部署步骤
步骤 1：Fork/创建仓库
1. GitHub 创建新仓库（或 Fork）
2. 仓库设置为 Public（RAW 链接才可访问）
步骤 2：上传文件
# 本地创建文件后推送
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/litywang/ZRONG.git
git push -u origin main
步骤 3：配置 Secrets
仓库 → Settings → Secrets and variables → Actions → New repository secret


