# -*- coding: utf-8 -*-
"""
可转债申购提醒脚本
数据来源：AKShare（巨潮资讯 cninfo），权威可靠，无需 Token。
检查今天是否有可转债可以网上申购，有则通过 PushPlus 推送微信消息。
接口异常时也会通过 PushPlus 推送告警通知。
支持本地运行和 GitHub Actions 运行。
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# ============ 配置区 ============
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
PUSHPLUS_URL = "https://www.pushplus.plus/send"
# ================================


def get_cb_issues():
    """
    获取近期可转债申购数据
    数据来源：巨潮资讯（通过 AKShare），权威可靠
    返回包含今天及未来14天可申购转债的列表
    """
    try:
        import akshare as ak
    except ImportError:
        raise ImportError("akshare 未安装，请执行: pip install akshare")

    today = datetime.now()
    start_date = (today - timedelta(days=30)).strftime("%Y%m%d")
    end_date = (today + timedelta(days=14)).strftime("%Y%m%d")

    try:
        df = ak.bond_cov_issue_cninfo(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise RuntimeError(f"AKShare 接口调用失败: {e}")

    if df is None or df.empty:
        return []

    today_str = today.strftime("%Y-%m-%d")

    issues = []
    for _, row in df.iterrows():
        onl_date = str(row.get("网上申购日期", "")).strip()
        if not onl_date or onl_date == "nan" or onl_date == "None":
            continue

        # 统一日期格式为 YYYY-MM-DD
        if len(onl_date) == 8:  # YYYYMMDD
            onl_date_fmt = f"{onl_date[:4]}-{onl_date[4:6]}-{onl_date[6:8]}"
        else:
            onl_date_fmt = onl_date

        # 只保留今天及未来的数据
        if onl_date_fmt < today_str:
            continue

        issues.append({
            "onl_name": str(row.get("债券简称", "未知")).strip(),
            "onl_code": str(row.get("网上申购代码", "")).strip(),
            "onl_date": onl_date_fmt,
            "issue_size": row.get("实际发行总量"),
            "issue_price": row.get("发行价格", 100),
        })

    issues.sort(key=lambda x: x["onl_date"])
    return issues


def format_size(size_in_wan):
    """将发行规模（万元）格式化为易读字符串（亿元）"""
    if size_in_wan is None or str(size_in_wan) == "nan":
        return "未知"
    try:
        size_yi = float(size_in_wan) / 10000
        return f"{size_yi:.2f}亿"
    except (ValueError, TypeError):
        return "未知"


def build_message(today_issues):
    """构建 HTML 格式推送消息（仅包含当天可申购的转债）"""
    html = []
    html.append('<h2 style="color:#e74c3c;">🔔 今天可申购！</h2>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:14px;">')
    html.append('<tr style="background:#f8d7da;"><th style="padding:8px;">转债名称</th><th style="padding:8px;">申购代码</th><th style="padding:8px;">发行规模</th><th style="padding:8px;">发行价</th></tr>')
    for i, item in enumerate(today_issues):
        bg = "#fff5f5" if i % 2 == 0 else "#ffffff"
        html.append(f'<tr style="background:{bg};">')
        html.append(f'<td style="text-align:center;padding:6px;font-weight:bold;">{item["onl_name"]}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{item["onl_code"]}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{format_size(item["issue_size"])}</td>')
        price = item.get("issue_price", 100)
        if price is None or str(price) == "nan":
            price = 100
        html.append(f'<td style="text-align:center;padding:6px;">{float(price):.0f}元</td>')
        html.append("</tr>")
    html.append("</table>")
    html.append('<p style="color:#e74c3c;font-size:13px;font-weight:bold;">⏰ 记得在交易时间（9:30-15:00）内顶格申购！</p>')
    html.append('<p style="color:#666;font-size:12px;">💡 可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。</p>')

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html.append(f'<p style="color:#aaa;font-size:11px;margin-top:15px;">数据来源：巨潮资讯（cninfo）| {now_str}</p>')

    title = "🔔 可转债申购提醒"
    return title, "\n".join(html)


def build_error_message(error_detail):
    """构建接口异常告警 HTML 消息"""
    html = []
    html.append('<h2 style="color:#e67e22;">⚠️ 可转债数据获取异常</h2>')
    html.append(f'<p style="color:#333;font-size:14px;">脚本在获取可转债申购数据时出错，请及时检查！</p>')
    html.append(f'<table style="width:100%;border-collapse:collapse;font-size:13px;">')
    html.append(f'<tr style="background:#fdebd0;"><th style="padding:8px;text-align:left;">项目</th><th style="padding:8px;text-align:left;">详情</th></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">错误信息</td><td style="padding:6px;">{error_detail}</td></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">发生时间</td><td style="padding:6px;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</td></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">数据源</td><td style="padding:6px;">AKShare（巨潮资讯 cninfo）</td></tr>')
    html.append('</table>')
    html.append('<p style="color:#666;font-size:12px;">可能原因：AKShare 版本过旧、巨潮资讯接口变动、网络问题。</p>')
    html.append('<p style="color:#666;font-size:12px;">建议：检查 GitHub Actions 运行日志，或在本地执行 <code>pip install --upgrade akshare</code>。</p>')
    return "⚠️ 可转债提醒脚本异常", "\n".join(html)


def send_pushplus(title, content, max_retries=2):
    """通过 PushPlus 发送微信推送，带重试"""
    if not PUSHPLUS_TOKEN:
        print("[ERROR] PUSHPLUS_TOKEN 未配置，无法发送推送")
        return False

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html",
    }

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                PUSHPLUS_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read().decode("utf-8"))

            if result.get("code") == 200:
                print(f"[OK] 推送成功: {result.get('msg', '')}")
                return True
            else:
                print(f"[WARN] 推送返回异常: {result}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
                return False
        except Exception as e:
            print(f"[ERROR] 推送失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return False
    return False


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 可转债申购提醒 {now} ===")

    try:
        issues = get_cb_issues()
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] 获取数据失败: {error_msg}")

        # 接口异常，推送告警通知
        print("[INFO] 正在发送异常告警通知...")
        title, content = build_error_message(error_msg)
        send_pushplus(title, content)
        return 1

    if not issues:
        print("[INFO] 近期没有可转债申购信息，跳过推送。")
        return 0

    # 只筛选今天可申购的转债
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_issues = [i for i in issues if i["onl_date"] == today_str]

    if not today_issues:
        print("[INFO] 今天没有可转债申购，跳过推送。")
        return 0

    print(f"[INFO] 今天有 {len(today_issues)} 只可转债可申购：")
    for item in today_issues:
        print(f"  🔴 {item['onl_name']} | 代码: {item['onl_code']} | 规模: {format_size(item['issue_size'])}")

    # 构建并推送消息
    title, content = build_message(today_issues)
    ok = send_pushplus(title, content)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
