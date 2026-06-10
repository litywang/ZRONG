# ZRONG v29 全链路优化方案

> 目标：提高大陆可用率 + 稳定Actions + 可维护 + 自动化自愈
> 策略：每轮优化→自动验证→诊断修复→再优化，减少人工交互

---

## 现状诊断（v29.01）

| 维度 | 现状 | 问题 |
|---|---|---|
| 大陆可用率 | 亚洲配额45%，新评分v29.01生效 | 权重配比需实测验证 |
| Actions稳定性 | 60min上限，健康检查已禁用 | 偶尔SIGKILL，ENABLE_HEALTH_CHECK=0 |
| 测速URL | gstatic/cloudflare/apple | 部分URL在国内可能不可达 |
| 代码质量 | validator.py有未提交修改 | max_workers 20→10待提交 |
| 监控 | 手动检查Actions | 无自动监控/自愈机制 |
| 输出节点 | MAX_FINAL_NODES=150 | 实测可用性未知 |

---

## Phase 1：稳定性基座（立即执行）

### 1.1 提交 validator.py 改动
```
git add core/validator.py && git commit -m "v29.02: 健康检查并发20→10，避免Actions超时"
```

### 1.2 Actions 超时防护
- 在 workflow 中增加 50min 软超时检查（预留10min给commit/push）
- 优化TCP测试并发数：200→150（减少高并发下的连接超时堆积）
- Clash 启动超时 30s→45s（GitHub Actions 网络波动）

### 1.3 健康检查重新启用（条件式）
- 仅在 final节点≤80 时启用（小规模更可靠）
- max_workers=5（保守并发），timeout=10s
- 失败不阻塞主流程

---

## Phase 2：大陆可用率提升（核心）

### 2.1 评分权重微调
基于 v29.01 新评分体系，对比同类型项目后调整：

| 参数 | 当前值 | 建议值 | 理由 |
|---|---|---|---|
| TARGET_ASIA_RATIO | 0.45 | 0.50 | 适度提高亚洲配额 |
| 亚洲TCP优先级 | 80% | 85% | 更多亚洲节点参与测试 |
| TCP_MAX_LATENCY | 4000 | 3500 | 收紧延迟要求，过滤慢节点 |
| MAX_PROXY_LATENCY | 5000 | 4500 | 同上 |
| 非亚洲TCP补充延迟 | 500ms | 400ms | 只保留真正快的非亚节点 |
| scoring_new.asia_tier1 | 60 | 65 | 港日韩新更高优先级 |
| scoring_new.reality_bonus | 20 | 25 | Reality协议抗封锁更强 |
| scoring_new.proto_bonus.vless | 25 | 28 | VLESS+Reality最优组合 |

### 2.2 过滤器优化
- v29.01已收窄排除关键词（移除"免费/公益/临时"）
- SSR协议直接过滤✅（无加密）
- anytls协议过滤✅（Clash不支持）
- 新增：HTTP/SOCKS5节点如无tls也过滤

### 2.3 测速URL优化
- 主池增加国内CDN测速点：`https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js`
- 备用池增加腾讯云：`https://cloud.tencent.com/`
- 204测试顺序：gstatic→cloudflare→apple

---

## Phase 3：自动化监控（Cron）

### 3.1 Actions后监控（每8h+15min）
检查最近一次 Actions 运行结果：
- 成功→检查输出节点数量/亚洲占比/最低延迟
- 失败→诊断错误类型（超时/NameError/ImportError）→尝试修复
- 输出质量下滑→调整参数→触发重跑

### 3.2 质量指标告警
- 输出节点<80：源枯竭，需要扩充订阅源
- 亚洲占比<35%：评分权重需调整
- 最低延迟>500ms：节点质量差，需放宽TCP延迟

### 3.3 自愈机制
- NameError/ImportError：自动补import→commit→push
- Clash崩溃：降级到纯TCP模式
- 超时：减少MAX_TCP_TEST_NODES/MAX_PROXY_TEST_NODES

---

## Phase 4：长期演进（按需）

### 4.1 订阅格式转换
- 接入subconverter生态，输出Surge/Quantumult/SingBox格式
- 研究SubConverter-Extended的Mihomo原生解析

### 4.2 API服务化
- 参考proxy_pool的REST API模式
- GET /api/proxies?limit=50&asia_only=true

### 4.3 智能源权重
- 基于历史成功率动态调整源权重（已有基础）
- 自动淘汰低质量源，发现新源

---

## 执行策略

- **每轮只改2-3个参数**，避免无法归因
- **改完→触发Actions→等结果→分析→再改**
- **不手动交互**，通过Cron自动检查+报告
- **所有改动记录在本文件和commit message中**
