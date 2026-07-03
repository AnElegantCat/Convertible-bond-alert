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
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

# ============ 配置区 ============
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
PUSHPLUS_URL = "https://www.pushplus.plus/send"
CHINA_TZ = ZoneInfo("Asia/Shanghai")
DATA_RETRY_COUNT = 3
DATA_RETRY_BASE_DELAY = 3
REQUIRED_COLUMNS = ("申购日期", "债券简称", "申购代码", "发行规模")
RETRYABLE_ERROR_KEYWORDS = (
    "ended prematurely",
    "timed out",
    "timeout",
    "connection",
    "remote end closed",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "http error 5",
    "max retries exceeded",
    "read timed out",
)
# ================================


def now_china():
    """返回北京时间。"""
    return datetime.now(CHINA_TZ)


def safe_html(value):
    """转义 HTML 特殊字符，避免接口异常数据破坏推送排版。"""
    if value is None:
        return ""
    return escape(str(value), quote=True)


def is_retryable_error(error):
    """判断 AKShare 调用失败是否更像临时网络/服务端问题。"""
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    message = str(error).lower()
    return any(keyword in message for keyword in RETRYABLE_ERROR_KEYWORDS)


def normalize_apply_date(value):
    """把接口返回的申购日期统一为 YYYY-MM-DD。"""
    if value is None:
        return None

    text = str(value).strip()
    if not text or text in ("nan", "None", "NaT"):
        return None

    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]

    if len(text) == 8 and text.isdigit():
        candidate = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    else:
        candidate = text[:10].replace("/", "-").replace(".", "-")

    try:
        return datetime.strptime(candidate, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def get_today_cb(today_str):
    """
    获取今天可转债申购数据
    数据来源：东方财富（通过 AKShare bond_zh_cov 接口），稳定可靠
    返回今天可申购转债的列表
    """
    try:
        import akshare as ak
    except ImportError:
        raise ImportError("akshare 未安装，请执行: pip install akshare")

    try:
        # bond_zh_cov: 东方财富可转债全量数据（1000+条），带重试防止网络抖动
        df = None
        last_err = None
        for attempt in range(DATA_RETRY_COUNT):
            try:
                df = ak.bond_zh_cov()
                break
            except Exception as e:
                last_err = e
                if not is_retryable_error(e):
                    raise  # 非网络问题直接抛出
                if attempt < DATA_RETRY_COUNT - 1:
                    wait_seconds = DATA_RETRY_BASE_DELAY * (attempt + 1)
                    print(f"[WARN] 数据接口临时异常 (尝试 {attempt + 1}/{DATA_RETRY_COUNT})，等待 {wait_seconds} 秒后重试: {e}")
                    time.sleep(wait_seconds)
        else:
            raise RuntimeError(f"AKShare 接口调用失败(已重试{DATA_RETRY_COUNT}次): {last_err}")
    except Exception as e:
        raise RuntimeError(f"AKShare 接口调用失败: {e}")

    if df is None or df.empty:
        raise RuntimeError("bond_zh_cov 返回空数据，可能是接口变动或网络问题")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise RuntimeError(f"bond_zh_cov 返回字段缺失: {', '.join(missing_columns)}")

    issues = []
    for _, row in df.iterrows():
        apply_date_fmt = normalize_apply_date(row.get("申购日期"))
        if apply_date_fmt is None:
            continue

        # 只保留今天的数据
        if apply_date_fmt != today_str:
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
            "issue_size": issue_size,
            "credit_rating": credit_rating,
        })

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


def build_message(today_issues):
    """构建 HTML 格式推送消息（当天可申购）"""
    html = []

    # ---- 今日申购 ----
    html.append('<h2 style="color:#e74c3c;">🔔 今天可申购！</h2>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:14px;">')
    html.append('<tr style="background:#f8d7da;"><th style="padding:8px;">转债名称</th><th style="padding:8px;">申购代码</th><th style="padding:8px;">发行规模</th><th style="padding:8px;">信用评级</th></tr>')
    for i, item in enumerate(today_issues):
        bg = "#fff5f5" if i % 2 == 0 else "#ffffff"
        rating = item.get("credit_rating") or "-"
        html.append(f'<tr style="background:{bg};">')
        html.append(f'<td style="text-align:center;padding:6px;font-weight:bold;">{safe_html(item["onl_name"])}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{safe_html(item["onl_code"])}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{safe_html(format_size(item["issue_size"]))}</td>')
        html.append(f'<td style="text-align:center;padding:6px;">{safe_html(rating)}</td>')
        html.append("</tr>")
    html.append("</table>")
    html.append('<p style="color:#e74c3c;font-size:13px;font-weight:bold;">⏰ 记得在交易时间（9:30-15:00）内顶格申购！</p>')

    # ---- 底部提示 ----
    html.append('<p style="color:#666;font-size:12px;margin-top:12px;">💡 可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。</p>')
    now_str = now_china().strftime("%Y-%m-%d %H:%M")
    html.append(f'<p style="color:#aaa;font-size:11px;">数据来源：东方财富（AKShare）| {now_str}</p>')

    title = "🔔 可转债申购提醒"
    return title, "\n".join(html)


def build_error_message(error_detail):
    """构建接口异常告警 HTML 消息"""
    html = []
    html.append('<h2 style="color:#e67e22;">⚠️ 可转债数据获取异常</h2>')
    html.append('<p style="color:#333;font-size:14px;">脚本在获取可转债申购数据时出错，请及时检查！</p>')
    html.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
    html.append('<tr style="background:#fdebd0;"><th style="padding:8px;text-align:left;">项目</th><th style="padding:8px;text-align:left;">详情</th></tr>')
    safe_detail = safe_html(error_detail)
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">错误信息</td><td style="padding:6px;">{safe_detail}</td></tr>')
    html.append(f'<tr><td style="padding:6px;font-weight:bold;">发生时间</td><td style="padding:6px;">{now_china().strftime("%Y-%m-%d %H:%M:%S")}</td></tr>')
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
            with urllib.request.urlopen(req, timeout=30) as resp:
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
    now = now_china()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 可转债申购提醒 {now_str} ===")

    today_str = now.strftime("%Y-%m-%d")

    try:
        issues = get_today_cb(today_str)
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] 获取数据失败: {error_msg}")

        # 接口异常，推送告警通知
        print("[INFO] 正在发送异常告警通知...")
        title, content = build_error_message(error_msg)
        send_pushplus(title, content)
        return 1

    if not issues:
        print("[INFO] 今天没有可转债申购，跳过推送。")
        return 0

    print(f"[INFO] 今天有 {len(issues)} 只可转债可申购：")
    for item in issues:
        print(f"  🔴 {item['onl_name']} | 代码: {item['onl_code']} | 规模: {format_size(item['issue_size'])}")

    title, content = build_message(issues)
    if not send_pushplus(title, content):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
