# 可转债申购提醒

![GitHub Actions Status](https://github.com/AnElegantCat/Convertible-bond-alert/actions/workflows/cb-alert.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python)

> 一个基于 GitHub Actions 的可转债申购提醒工具。工作日上午 9 点自动扫描东方财富可转债数据，当天有可申购转债时即时推送微信通知，让你不错过任何打新机会。

---

## ⚡ 快速开始

### 第 1 步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名填 `convertible-bond-alert`
3. **设为 Public**（Actions 分钟无限免费，可支撑每日提前入队+忙等窗口；Token 存于加密 Secrets，日志自动打码，不会暴露）
4. 点击 **Create repository**

### 第 2 步：上传代码

将以下文件上传到仓库根目录：

```
.
├── cb_alert.py              # 核心脚本
├── requirements.txt         # 依赖声明
└── .github/workflows/
    ├── cb-alert.yml         # 申购提醒（4:07 CST 入队，9:07 CST 执行）
    └── keep-alive.yml       # 保活（每月 1 号）
```

### 第 3 步：配置 PushPlus Token

1. 进入仓库 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`PUSHPLUS_TOKEN`
4. Secret 填你的 [PushPlus](https://www.pushplus.plus/) Token
5. 点击 **Add secret**

**部署完成！** 每个工作日北京时间 4:07 提前进入 GitHub 队列，忙等到 9:07 精确执行，确保 9:30 开盘前把转债申购推送到微信。

---

## 🧩 功能说明

| 特性 | 说明 |
|------|------|
| 📊 **数据源** | AKShare 调用东方财富 `bond_zh_cov` 接口，稳定可靠，无需额外 API Key |
| 📅 **定时执行** | 工作日 4:07 CST 提前入队 + 忙等窗口精确执行在 9:07 CST，对抗 GitHub 排队延迟，保证 9:30 开盘前送达 |
| 📱 **微信推送** | 通过 PushPlus 推送 HTML 表格消息到微信，带底色边框，信息完整 |
| 🔄 **自动重试** | 数据接口支持 3 次重试，推送支持 2 次重试 |
| ⚠️ **异常告警** | 接口调用失败时自动推送告警，防止沉默失效 |
| 💤 **静默跳过** | 无申购信息时不推送，节省 PushPlus 免费额度 |
| 🔁 **自动保活** | 每月 1 号自动空提交，防止 Actions 因 60 天无活动被禁用 |

---

## 📋 推送消息预览

### 今日有可申购

推送为 HTML 表格排版，含转债名称、申购代码、发行规模、信用评级，表头与隔行带底色、四周有边框，微信里清晰美观：

| 转债名称 | 申购代码 | 发行规模 | 信用评级 |
| --- | --- | --- | --- |
| 华峰转债 | 718200 | 7.49亿 | AA |

```
⏰ 记得在交易时间（9:30-15:00）内顶格申购！
💡 可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。
数据来源：东方财富（AKShare）| 2026-06-23 04:43
```

### 接口异常告警

```
可转债提醒脚本异常

## 可转债数据获取异常

脚本在获取可转债申购数据时出错，请及时检查。
- 错误信息：xxx
- 发生时间：2026-06-12 09:00:15
- 数据源：AKShare（东方财富 bond_zh_cov）
```

---

## 🔧 工作原理

```
GitHub Actions (cron: 工作日 4:07 CST 提前入队)
    │
    ├─ 忙等窗口：循环等待到 9:07 CST ← 把不可控的排队延迟转成固定执行时刻
    │
    ├─ pip install -r requirements.txt ← 安装锁定版本依赖，可复现
    │
    ├─ 调用 AKShare bond_zh_cov()     ← 获取东方财富全量可转债数据
    │   └─ 网络异常自动重试 3 次
    │
    ├─ 筛选申购日期 == 今天            ← 精确匹配当天
    │
    ├─ 有数据？ → 构建 HTML 表格 → PushPlus 推送
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
pip install -r requirements.txt

# 设置 Token 环境变量
export PUSHPLUS_TOKEN="your-token-here"

# 运行脚本
python cb_alert.py

# 运行测试
python -m unittest -v
```
