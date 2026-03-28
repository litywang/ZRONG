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

添加：
- BOT_TOKEN: Telegram Bot Token
- CHAT_ID: Telegram 聊天 ID
步骤 4：验证运行
1. 进入 Actions 标签页
2. 手动触发一次工作流
3. 检查运行日志
4. 验证 proxies.yaml 已生成
⚠️ 注意事项
项目	说明
运行时间	每次约 15-25 分钟
更新频率	建议 3-4 小时一次（免费节点时效短）
仓库大小	定期清理历史提交，避免超限
Actions 限制	每月 2000 分钟（免费账户）
RAW 链接延迟	更新后等待 1-2 分钟生效
📊 预期运行日志
==================================================
🚀 Clash 节点筛选器 - GitHub Actions 自动版
==================================================

🔍 验证订阅源...
✅ https://raw.githubusercontent.com/barry-far/V2ray-...
✅ 找到 8 个可用订阅源

📥 抓取节点...
✅ 解析完成：850 个唯一节点

⚡ 第一阶段：TCP 延迟测试...
   已测试 50/200 个节点
   已测试 100/200 个节点
✅ TCP 合格：65 个

🚀 第二阶段：真实代理测速...
✅ 测试配置已生成
📥 下载 Mihomo 内核...
✅ 内核下载成功
🚀 启动 Clash 内核...
✅ Clash 内核启动成功
📊 开始测速...

   ✅ VMess-hk-xxx|⚡150ms|📥1.2MB
   ✅ VLESS-jp-xxx|⚡89ms|📥2.1MB
   进度：10/80 | 合格：8

✅ 最终可用：45 个

==================================================
📊 统计信息
==================================================
• 原始节点：850 个
• TCP 合格：65 个
• 最终可用：45 个
• 亚洲节点：28 个
• 最低延迟：45.2 ms
• 平均延迟：156.8 ms
• 总耗时：892.3 秒
==================================================

✅ Telegram 推送成功
🎉 完成！
🧹 临时文件已清理
🔧 常见问题
问题
解决方案
Actions 不运行
检查仓库是否 Public，Actions 是否启用
RAW 链接 404
等待 1-2 分钟，检查分支名（main/master）
节点全部失效
增加更新频率，免费节点时效短
运行超时
减少 MAX_PROXY_TEST_NODES 数量
Telegram 不推送
检查 BOT_TOKEN 和 CHAT_ID 是否正确
