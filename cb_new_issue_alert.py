# -*- coding: utf-8 -*-
"""
可转债申购提醒脚本
检查今天及近期是否有可转债可以网上申购，有则通过 PushPlus 推送微信消息。
支持本地运行和 GitHub Actions 运行。
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# ============ 配置区 ============
# PushPlus Token（优先从环境变量读取，也支持直接填写）
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
FINANCE_API_URL = "https://www.codebuddy.cn/v2/tool/financedata"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
# ================================


def get_cb_issues():
    """获取近期的可转债发行数据"""
    today = datetime.now()
    # 查询过去7天到未来14天，覆盖所有可能的公告日期
    start_date = (today - timedelta(days=7)).strftime("%Y%m%d")
    end_date = (today + timedelta(days=14)).strftime("%Y%m%d")

    payload = {
        "api_name": "cb_issue",
        "params": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "fields": "ts_code,ann_date,onl_code,onl_name,onl_date,issue_size,issue_price,lead_underwriter"
    }

    try:
        req = urllib.request.Request(
            FINANCE_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))

        if result.get("code") != 0:
            print(f"[ERROR] API 错误: {result.get('msg', '未知错误')}")
            return []

        fields = result["data"]["fields"]
        items = result["data"]["items"]
        idx = {f: i for i, f in enumerate(fields)}

        today_str = today.strftime("%Y%m%d")
        future_date = (today + timedelta(days=7)).strftime("%Y%m%d")

        upcoming = []
        for item in items:
            onl_date = item[idx["onl_date"]]
            if onl_date and today_str <= onl_date <= future_date:
                record = dict(zip(fields, item))
                record["is_today"] = onl_date == today_str
                upcoming.append(record)

        upcoming.sort(key=lambda x: x["onl_date"])
        return upcoming

    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return []


def format_size(size_in_yi):
    """将发行规模（亿元）格式化为易读字符串"""
    if size_in_yi is None:
        return "未知"
    return f"{size_in_yi:.2f}亿"


def format_date(date_str):
    """将 YYYYMMDD 格式化为 MM月DD日"""
    if not date_str:
        return "未知"
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        return dt.strftime("%m月%d日")
    except ValueError:
        return date_str


def get_weekday(date_str):
    """获取日期对应的星期几"""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"（{weekdays[dt.weekday()]}）"
    except ValueError:
        return ""


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
        html.append(f'<td style="text-align:center;padding:6px;">{item.get("issue_price", 100)}元</td>')
        html.append("</tr>")
    html.append("</table>")
    html.append('<p style="color:#e74c3c;font-size:13px;font-weight:bold;">⏰ 记得在交易时间（9:30-15:00）内顶格申购！</p>')
    html.append('<p style="color:#666;font-size:12px;">💡 可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。</p>')

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html.append(f'<p style="color:#aaa;font-size:11px;margin-top:15px;">数据来源：Tushare | {now_str}</p>')

    title = "🔔 可转债申购提醒"
    return title, "\n".join(html)


def send_pushplus(title, content, max_retries=2):
    """通过 PushPlus 发送微信推送，带重试"""
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

    issues = get_cb_issues()

    if not issues:
        print("[INFO] 近期没有可转债申购信息，跳过推送。")
        return 0

    # 只筛选今天可申购的转债
    today_issues = [i for i in issues if i["is_today"]]

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
