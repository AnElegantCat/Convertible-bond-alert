# 可转债申购提醒 🔔

每天工作日 8:30 自动检查可转债申购信息，通过 PushPlus 推送到微信。

## 功能

- 查询当天及未来 7 天的可转债申购信息
- 有新转债时推送详细申购信息（名称、代码、规模、价格）
- 无新转债时跳过推送（节省 PushPlus 额度）
- 支持重试机制，推送失败最多重试 2 次

## 快速部署（3 步搞定）

### 第 1 步：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名填 `cb-new-issue-alert`（或任意你喜欢的名字）
3. **勾选 Add a README file**
4. 设为 **Private**（推荐，避免 Token 暴露风险）
5. 点击 Create repository

### 第 2 步：上传代码

将以下 3 个文件上传到仓库根目录：

| 文件 | 路径 |
|------|------|
| Python 脚本 | `cb_new_issue_alert.py` |
| 工作流配置 | `.github/workflows/cb-new-issue-alert.yml` |
| 忽略文件 | `.gitignore` |

### 第 3 步：配置 Secret

1. 进入仓库 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`PUSHPLUS_TOKEN`
4. Secret 填你的 PushPlus Token
5. 点击 **Add secret**

### 完成！

每天工作日早上 8:30（北京时间），GitHub Actions 会自动运行，有可转债申购就推送到你的微信。

## 手动触发

如果想立即测试，进入仓库 **Actions** 页面 → 左侧选 "可转债申购提醒" → 右侧点 **Run workflow**。

## 推送消息预览

- 🔴 **今天有可申购**：红色醒目标题，显示转债名称、申购代码、发行规模、发行价
- 📅 **即将申购**：蓝色表格展示未来 7 天的可转债申购日期
- ✅ **无数据**：自动跳过推送，不浪费额度

## 工作原理

```
GitHub Actions (cron 每天 8:30 CST)
    → 运行 Python 脚本
    → 调用 Tushare API 获取可转债发行数据
    → 筛选今天及未来 7 天有网上申购日期的转债
    → 通过 PushPlus API 推送 HTML 消息到微信
```

## 数据来源

Tushare 金融数据接口（通过 codebuddy.cn 代理）
