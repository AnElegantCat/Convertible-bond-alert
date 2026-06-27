# Convertible Bond Alert

![GitHub Actions Status](https://github.com/AnElegantCat/Convertible-bond-alert/actions/workflows/cb-alert.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python)

> 一个基于 GitHub Actions 的可转债申购提醒工具。工作日上午 6 点自动扫描东方财富可转债数据，当天有可申购转债时即时推送微信通知，让你不错过任何打新机会。

---

## ⚡ 快速开始

### 第 1 步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名填 `convertible-bond-alert`
3. **设为 Private**（避免 Token 暴露风险）
4. 点击 **Create repository**

### 第 2 步：上传代码

将以下文件上传到仓库根目录：

```
.
├── cb_alert.py              # 核心脚本
├── requirements.txt         # 依赖声明
└── .github/workflows/
    ├── cb-alert.yml         # 申购提醒（工作日 6:00 CST）
    └── keep-alive.yml       # 保活（每月 1 号）
```

### 第 3 步：配置 PushPlus Token

1. 进入仓库 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`PUSHPLUS_TOKEN`
4. Secret 填你的 [PushPlus](https://www.pushplus.plus/) Token
5. 点击 **Add secret**

> 💡 没有 PushPlus？访问 https://www.pushplus.plus/ 注册并获取免费 Token。

**部署完成！** 每天工作日早上 6:00（北京时间），脚本自动运行，有转债申购即时推送到微信。

---

## 🧩 功能说明

| 特性 | 说明 |
|------|------|
| 📊 **数据源** | AKShare 调用东方财富 `bond_zh_cov` 接口，稳定可靠，无需额外 API Key |
| 📅 **定时执行** | GitHub Actions 工作日 6:00 CST 自动触发，早于开盘 |
| 📱 **微信推送** | 通过 PushPlus 推送 HTML 格式消息到微信，信息完整 |
| 🔄 **自动重试** | 数据接口支持 3 次重试，推送支持 2 次重试 |
| ⚠️ **异常告警** | 接口调用失败时自动推送告警，防止沉默失效 |
| 💤 **静默跳过** | 无申购信息时不推送，节省 PushPlus 免费额度 |
| 🔁 **自动保活** | 每月 1 号自动空提交，防止 Actions 因 60 天无活动被禁用 |

---

## 📋 推送消息预览

### 今日有可申购

推送包含转债名称、申购代码、发行规模、信用评级等信息，HTML 表格格式，一目了然：

```
🔔 可转债申购提醒

🔔 今天可申购！
┌─────────┬─────────┬─────────┬─────────┐
│ 转债名称  │ 申购代码  │ 发行规模  │ 信用评级  │
├─────────┼─────────┼─────────┼─────────┤
│ XX转债   │ 78XXXX  │  5.00亿  │   AA-   │
└─────────┴─────────┴─────────┴─────────┘

⏰ 记得在交易时间（9:30-15:00）内顶格申购！
```

### 接口异常告警

```
⚠️ 可转债数据获取异常

脚本在获取可转债申购数据时出错，请及时检查！
- 错误信息: xxx
- 发生时间: 2026-06-12 06:00:15
- 数据源: AKShare（东方财富 bond_zh_cov）
```

---

## 🔧 工作原理

```
GitHub Actions (cron: 工作日 6:00 CST)
    │
    ├─ pip install --upgrade akshare  ← 每次自动升级依赖
    │
    ├─ 调用 AKShare bond_zh_cov()     ← 获取东方财富全量可转债数据
    │   └─ 网络异常自动重试 3 次
    │
    ├─ 筛选申购日期 == 今天            ← 精确匹配当天
    │
    ├─ 有数据？ → 构建 HTML → PushPlus 推送
    ├─ 无数据？ → 静默结束，不推送
    └─ 异常？  → 推送告警通知
```

---

## 🖥 手动触发

进入仓库 **Actions** 页面 → 左侧选 **Convertible Bond Alert** → 右侧点 **Run workflow**。

---

## 🌐 本地运行

```bash
# 安装依赖
pip install akshare

# 设置 Token 环境变量
export PUSHPLUS_TOKEN="your-token-here"

# 运行脚本
python cb_alert.py
```

---

## 📝 常见问题

**Q: 为什么推送时间不是 8:30？**

A: 为避免 GitHub Actions 调度延迟导致推送晚于开盘，已提前至早上 6:00 CST 执行，确保在 9:30 开盘前收到提醒。

**Q: 推送一直失败怎么办？**

A: 检查 `PUSHPLUS_TOKEN` 是否配置正确，确认 PushPlus 账户处于激活状态。脚本有 2 次重试，失败后建议手动进入 GitHub Actions 查看日志。

**Q: 可以改为其他推送渠道吗？**

A: 当前仅支持 PushPlus。如需接入其他平台（如飞书、钉钉、 Bark），可查看代码中的 `send_pushplus` 函数自行扩展。

---

## 📄 协议

MIT License

