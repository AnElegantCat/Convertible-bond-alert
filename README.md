# Convertible Bond Alert 🔔

可转债申购提醒 — 每个工作日自动检查申购信息，推送到微信。

## 功能

- 查询当天及未来 14 天的可转债申购信息
- 当天有可申购转债时，推送详细申购信息（名称、代码、规模、价格）到微信
- 无新转债时自动跳过推送（节省 PushPlus 额度）
- 推送失败自动重试，最多重试 2 次
- 接口异常时推送告警通知，及时发现问题

## 快速部署（3 步搞定）

### 第 1 步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名填 `convertible-bond-alert`
3. **勾选 Add a README file**
4. 设为 **Private**（推荐，避免 Token 暴露风险）
5. 点击 Create repository

### 第 2 步：上传代码

将以下文件上传到仓库根目录：

```
.
├── cb_alert.py
└── .github/workflows/cb-alert.yml
```

### 第 3 步：配置 Secret

1. 进入仓库 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`PUSHPLUS_TOKEN`
4. Secret 填你的 PushPlus Token
5. 点击 **Add secret**

### 完成！

每天工作日早上 8:30（北京时间），GitHub Actions 会自动运行，有可转债申购就推送到你的微信。

## 手动触发

进入仓库 **Actions** 页面 → 左侧选 "Convertible Bond Alert" → 右侧点 **Run workflow**。

## 推送消息预览

- 🔴 **今天有可申购**：红色醒目标题，显示转债名称、申购代码、发行规模、发行价
- ⚠️ **接口异常**：橙色告警通知，包含错误信息和修复建议
- ✅ **无数据**：自动跳过推送，不浪费额度

## 工作原理

```
GitHub Actions (cron 每天 8:30 CST)
    → 运行 Python 脚本
    → 通过 AKShare 调用巨潮资讯（cninfo）获取可转债发行数据
    → 筛选当天有网上申购日期的转债
    → 通过 PushPlus API 推送 HTML 消息到微信
```

## 数据来源

巨潮资讯（cninfo）— 证监会指定信息披露网站，权威可靠。
通过 [AKShare](https://github.com/akfamily/akshare) 开源库调用，无需 API Token。
