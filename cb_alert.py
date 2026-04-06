# -*- coding: utf-8 -*-
"""
可转债申购提醒脚本
数据来源：AKShare（东方财富），稳定可靠，无需 Token。
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


def get_cb_issues(today_str):
    """
    获取近期可转债申购数据
    数据来源：东方财富（通过 AKShare bond_zh_cov 接口），稳定可靠
    返回包含今天及未来14天可申购转债的列表
    """
    try:
        import akshare as ak
    except ImportError:
        raise ImportError("akshare 未安装，请执行: pip install akshare")

    today = datetime.strptime(today_str, "%Y-%m-%d")
    future_limit = (today + timedelta(days=14)).strftime("%Y-%m-%d")

    try:
        # bond_zh_cov: 东方财富可转债全量数据（1000+条），一次调用获取全部
        df = ak.bond_zh_cov()
    except Exception as e:
        raise RuntimeError(f"AKShare 接口调用失败: {e}")

    if df is None or df.empty:
        raise RuntimeError("bond_zh_cov 返回空数据，可能是接口变动或网络问题")

    issues = []
    for _, row in df.iterrows():
        apply_date = str(row.get("申购日期", "")).strip()
        if not apply_date or apply_date in ("nan", "None", "NaT"):
            continue

        # 统一日期格式为 YYYY-MM-DD（接口返回的可能是 YYYYMMDD）
        if len(apply_date) == 8:
            apply_date_fmt = f"{apply_date[:4]}-{apply_date[4:6]}-{apply_date[6:8]}"
        else:
            apply_date_fmt = apply_date[:10]  # 截断可能的时间部分

        # 只保留今天到未来14天的数据
        if apply_date_fmt < today_str or apply_date_fmt > future_limit:
            continue

        bond_name = str(row.get("债券简称", "")).strip()
        apply_code = str(row.get("申购代码", "")).strip()
        if not bond_name or bond_name in ("nan", "None"):
            continue

        # 发行规模：接口返回单位为亿元
        issue_size = row.get("发行规模")

        # 信用评级（可选展示）
        credit_rating = str(row.get("信用评级", "")).strip()
        if credit_rating in ("nan", "None", ""):
            credit_rating = None

        issues.append({
            "onl_name": bond_name,
            "onl_code": apply_code,
            "onl_date": apply_date_fmt,
            "issue_size": issue_size,
            "credit_rating": credit_rating,
        })

    issues.sort(key=lambda x: x["onl_date"])
    return issues


def format_size(size_in_yi):
    """将发行规模（亿元）格式化为易读字符串"""
    if size_in_yi is None or str(size_in_yi) == "nan":
        return "未知"
    try:
        val = float(size_in_yi)
        if val >= 1:
            return f"{val:.2f}亿"
        else:
            return f"{val * 10000:.0f}万"
    except (ValueError, TypeError):
        return "未知"


def build_message(today_issues, upcoming_issues):
    """构建 HTML 格式推送消息（当天可申购 + 未来几天预告）"""
    html = []

    # ---- 今日申购 ----
    html.append('<h2 style="color:#e74c3c;">🔔 今天可申购！</h2>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:14px;">')
    html.append('<tr style="background:#f8d7da;"><th style="padding:8px;">转债名称</th><th style="padding:8px;">申购代码</th><th style="padding:8px;">发行规模</th><th style="padding:8px;">信用评级</th></tr>')
    for i, item in enumerate(today_issues):
        bg = "#fff5f5" if i % 2 == 0 else "#ffffff"
        rating = item.get("credit_rating") or "-"
        html.append(f'<tr style="background:{bg};">')
        html.append(f'<td style="text-align:center;padding:6px;font-weight:bold;">{item["onl_name"]}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{item["onl_code"]}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{format_size(item["issue_size"])}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{rating}</td>')
        html.append("</tr>")
    html.append("</table>")
    html.append('<p style="color:#e74c3c;font-size:13px;font-weight:bold;">⏰ 记得在交易时间（9:30-15:00）内顶格申购！</p>')

    # ---- 未来预告 ----
    if upcoming_issues:
        html.append('<hr style="border:none;border-top:1px solid #eee;margin:15px 0;">')
        html.append('<h3 style="color:#2980b9;">📅 近期预告</h3>')
        html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
        html.append('<tr style="background:#d6eaf8;"><th style="padding:6px;">日期</th><th style="padding:6px;">转债名称</th><th style="padding:6px;">申购代码</th><th style="padding:6px;">发行规模</th></tr>')
        for i, item in enumerate(upcoming_issues):
            bg = "#ebf5fb" if i % 2 == 0 else "#ffffff"
            html.append(f'<tr style="background:{bg};">')
            html.append(f'<td style="text-align:center;padding:5px;">{item["onl_date"]}</td>')
            html.append(f'<td style="text-align:center;padding:5px;font-weight:bold;">{item["onl_name"]}</td>')
            html.append(f'<td style="text-align:center;padding:5px;">{item["onl_code"]}</td>')
            html.append(f'<td style="text-align:center;padding:5px;">{format_size(item["issue_size"])}</td>')
            html.append("</tr>")
        html.append("</table>")

    # ---- 底部提示 ----
    html.append('<p style="color:#666;font-size:12px;margin-top:12px;">💡 可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。</p>')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html.append(f'<p style="color:#aaa;font-size:11px;">数据来源：东方财富（AKShare）| {now_str}</p>')

    title = "🔔 可转债申购提醒"
    return title, "\n".join(html)


def build_upcoming_only_message(upcoming_issues):
    """构建纯预告消息（今天没有，但未来几天有）"""
    html = []
    html.append('<h2 style="color:#2980b9;">📅 近期可转债申购预告</h2>')
    html.append('<p style="color:#666;font-size:13px;">今天没有可申购的转债，以下是近期安排：</p>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
    html.append('<tr style="background:#d6eaf8;"><th style="padding:6px;">日期</th><th style="padding:6px;">转债名称</th><th style="padding:6px;">申购代码</th><th style="padding:6px;">发行规模</th></tr>')
    for i, item in enumerate(upcoming_issues):
        bg = "#ebf5fb" if i % 2 == 0 else "#ffffff"
        html.append(f'<tr style="background:{bg};">')
        html.append(f'<td style="text-align:center;padding:5px;">{item["onl_date"]}</td>')
        html.append(f'<td style="text-align:center;padding:5px;font-weight:bold;">{item["onl_name"]}</td>')
        html.append(f'<td style="text-align:center;padding:5px;">{item["onl_code"]}</td>')
        html.append(f'<td style="text-align:center;padding:5px;">{format_size(item["issue_size"])}</td>')
        html.append("</tr>")
    html.append("</table>")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html.append(f'<p style="color:#aaa;font-size:11px;">数据来源：东方财富（AKShare）| {now_str}</p>')

    title = "📅 可转债申购预告"
    return title, "\n".join(html)


def build_error_message(error_detail):
    """构建接口异常告警 HTML 消息"""
    html = []
    html.append('<h2 style="color:#e67e22;">⚠️ 可转债数据获取异常</h2>')
    html.append('<p style="color:#333;font-size:14px;">脚本在获取可转债申购数据时出错，请及时检查！</p>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
    html.append('<tr style="background:#fdebd0;"><th style="padding:8px;text-align:left;">项目</th><th style="padding:8px;text-align:left;">详情</th></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">错误信息</td><td style="padding:6px;">{error_detail}</td></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">发生时间</td><td style="padding:6px;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</td></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">数据源</td><td style="padding:6px;">AKShare（东方财富 bond_zh_cov）</td></tr>')
    html.append('</table>')
    html.append('<p style="color:#666;font-size:12px;">可能原因：AKShare 版本过旧、东方财富接口变动、网络问题。</p>')
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
        except Exception as e:
            print(f"[ERROR] 推送失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")

        if attempt < max_retries:
            time.sleep(3)

    return False


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 可转债申购提醒 {now} ===")

    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        issues = get_cb_issues(today_str)
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

    # 分类：今天 vs 未来
    today_issues = [i for i in issues if i["onl_date"] == today_str]
    upcoming_issues = [i for i in issues if i["onl_date"] != today_str]

    if today_issues:
        print(f"[INFO] 今天有 {len(today_issues)} 只可转债可申购：")
        for item in today_issues:
            print(f"  🔴 {item['onl_name']} | 代码: {item['onl_code']} | 规模: {format_size(item['issue_size'])}")

        if upcoming_issues:
            print(f"[INFO] 未来还有 {len(upcoming_issues)} 只转债待申购")

        title, content = build_message(today_issues, upcoming_issues)
        send_pushplus(title, content)
        return 0

    # 今天没有，但未来几天有 → 推送预告
    if upcoming_issues:
        print(f"[INFO] 今天没有可申购转债，未来 {len(upcoming_issues)} 只将推出预告推送")
        title, content = build_upcoming_only_message(upcoming_issues)
        send_pushplus(title, content)
        return 0

    print("[INFO] 今天没有可转债申购，跳过推送。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
