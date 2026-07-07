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
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

# Windows 控制台/重定向输出可能是 GBK 编码，消息里的 emoji 会导致 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ============ 配置区 ============
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
PUSHPLUS_URL = "https://www.pushplus.plus/send"
PUSHPLUS_TEMPLATE = "markdown"
CHINA_TZ = ZoneInfo("Asia/Shanghai")
DATA_RETRY_COUNT = 3
DATA_RETRY_BASE_DELAY = 3
REQUIRED_COLUMNS = ("申购日期", "债券简称", "申购代码", "发行规模")
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
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


def safe_markdown_cell(value):
    """清理 Markdown 表格单元格，避免接口数据破坏表格结构。"""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def summarize_response_body(body, limit=300):
    """把 PushPlus 的非 JSON 响应压缩成可读摘要，避免日志刷出整页 HTML。"""
    text = unescape(str(body or ""))
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    while "  " in text:
        text = text.replace("  ", " ")

    lower_text = text.lower()
    if "请求携带恶意参数" in text or "星尘盾" in text:
        return "PushPlus 星尘盾拦截：请求携带恶意参数，已被拦截。"
    if "<!doctype html" in lower_text or "<html" in lower_text:
        return "PushPlus 返回了 HTML 页面，可能是风控/网关拦截。"
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def compact_error_detail(error_detail, limit=500):
    """告警内容只保留错误摘要，避免把整页拦截 HTML 再提交给 PushPlus。"""
    summary = summarize_response_body(error_detail, limit=limit)
    if len(summary) > limit:
        return summary[:limit] + "..."
    return summary


def is_retryable_error(error):
    """判断 AKShare 调用失败是否更像临时网络/服务端问题。"""
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRYABLE_HTTP_STATUS_CODES
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
        # 先剥离时间部分（"2026-07-04 00:00:00" / ISO "T"），避免非零填充日期被定长截断截坏
        date_part = text.split(" ")[0].split("T")[0]
        candidate = date_part.replace("/", "-").replace(".", "-")

    try:
        # strptime 接受非零填充（2026-7-4），strftime 统一输出为零填充
        return datetime.strptime(candidate, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalize_apply_code(value):
    """清理申购代码：A股申购代码固定 6 位，列被 pandas 数值化时会丢前导零、带 .0 后缀。"""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text in ("nan", "None"):
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) < 6:
        text = text.zfill(6)
    return text


def fetch_bond_data():
    """
    调用 AKShare bond_zh_cov 拉取东方财富可转债全量数据（1000+条）。
    网络/服务端临时异常自动重试，其余异常直接包装抛出。
    """
    try:
        import akshare as ak
    except ImportError as e:
        raise RuntimeError("akshare 未安装，请执行: pip install -r requirements.txt") from e

    last_err = None
    for attempt in range(DATA_RETRY_COUNT):
        try:
            return ak.bond_zh_cov()
        except Exception as e:
            if not is_retryable_error(e):
                raise RuntimeError(f"AKShare 接口调用失败: {e}") from e
            last_err = e
            if attempt < DATA_RETRY_COUNT - 1:
                wait_seconds = DATA_RETRY_BASE_DELAY * (attempt + 1)
                print(f"[WARN] 数据接口临时异常 (尝试 {attempt + 1}/{DATA_RETRY_COUNT})，等待 {wait_seconds} 秒后重试: {e}")
                time.sleep(wait_seconds)
    raise RuntimeError(f"AKShare 接口调用失败(已重试{DATA_RETRY_COUNT}次): {last_err}") from last_err


def get_today_cb(today_str):
    """
    获取今天可转债申购数据
    数据来源：东方财富（通过 AKShare bond_zh_cov 接口），稳定可靠
    返回今天可申购转债的列表
    """
    df = fetch_bond_data()

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
        apply_code = normalize_apply_code(row.get("申购代码"))
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
    """构建 Markdown 格式推送消息（当天可申购）。"""
    lines = []

    lines.append("## 今天可申购")
    lines.append("")
    lines.append("| 转债名称 | 申购代码 | 发行规模 | 信用评级 |")
    lines.append("| --- | --- | --- | --- |")
    for item in today_issues:
        rating = item.get("credit_rating") or "-"
        lines.append(
            "| {name} | {code} | {size} | {rating} |".format(
                name=safe_markdown_cell(item["onl_name"]),
                code=safe_markdown_cell(item["onl_code"]),
                size=safe_markdown_cell(format_size(item["issue_size"])),
                rating=safe_markdown_cell(rating),
            )
        )
    lines.append("")
    lines.append("记得在交易时间（9:30-15:00）内顶格申购。")
    lines.append("可转债申购无需市值，顶格申购中签概率最大，中签后缴款即可。")
    now_str = now_china().strftime("%Y-%m-%d %H:%M")
    lines.append("")
    lines.append(f"数据来源：东方财富（AKShare）| {now_str}")

    title = "可转债申购提醒"
    return title, "\n".join(lines)


def build_error_message(error_detail):
    """构建接口异常告警 Markdown 消息。"""
    safe_detail = compact_error_detail(error_detail)
    lines = [
        "## 可转债数据获取异常",
        "",
        "脚本在获取可转债申购数据时出错，请及时检查。",
        "",
        f"- 错误信息：{safe_detail}",
        f"- 发生时间：{now_china().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 数据源：AKShare（东方财富 bond_zh_cov）",
        "",
        "可能原因：AKShare 版本过旧、东方财富接口变动、网络问题。",
        "建议：检查 GitHub Actions 运行日志，或在本地执行 `pip install --upgrade akshare`。",
    ]
    return "可转债提醒脚本异常", "\n".join(lines)


def send_pushplus(title, content, max_retries=2):
    """通过 PushPlus 发送微信推送，带重试"""
    if not PUSHPLUS_TOKEN:
        print("[ERROR] PUSHPLUS_TOKEN 未配置，无法发送推送")
        return False

    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": PUSHPLUS_TEMPLATE,
    }

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                PUSHPLUS_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "User-Agent": "convertible-bond-alert/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")

            try:
                result = json.loads(body)
            except json.JSONDecodeError:
                print(f"[WARN] PushPlus 返回非 JSON 响应: {summarize_response_body(body)}")
                result = {}

            if result.get("code") == 200:
                print(f"[OK] 推送成功: {result.get('msg', '')}")
                return True
            else:
                print(f"[WARN] 推送返回异常: {result}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"[ERROR] 推送失败 HTTP {e.code}: {summarize_response_body(body)}")
        except Exception as e:
            print(f"[ERROR] 推送失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")

        if attempt < max_retries:
            time.sleep(3)

    return False


def main():
    now = now_china()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 可转债申购提醒 {now_str} ===")

    if not PUSHPLUS_TOKEN:
        print("[WARN] PUSHPLUS_TOKEN 未配置，数据获取仍会执行，但无法推送微信消息")

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
