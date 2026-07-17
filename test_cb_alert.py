import io
import unittest
import urllib.error

import cb_alert


class ConvertibleBondAlertTests(unittest.TestCase):
    def test_normalize_apply_date_accepts_common_formats(self):
        cases = {
            "20260707": "2026-07-07",
            "2026/7/7": "2026-07-07",
            "2026.07.07": "2026-07-07",
            "2026-07-07 00:00:00": "2026-07-07",
            "2026-07-07T00:00:00": "2026-07-07",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(cb_alert.normalize_apply_date(raw_value), expected)

    def test_normalize_apply_date_rejects_invalid_values(self):
        for raw_value in (None, "", "nan", "None", "NaT", "not-a-date"):
            with self.subTest(raw_value=raw_value):
                self.assertIsNone(cb_alert.normalize_apply_date(raw_value))

    def test_normalize_apply_code_preserves_six_digit_codes(self):
        cases = {
            "1234.0": "001234",
            "754786": "754786",
            123456: "123456",
            None: "",
            "nan": "",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(cb_alert.normalize_apply_code(raw_value), expected)

    def test_safe_html_escapes_special_chars(self):
        self.assertEqual(
            cb_alert.safe_html('<b>A&B"C'),
            "&lt;b&gt;A&amp;B&quot;C",
        )
        self.assertEqual(cb_alert.safe_html(None), "")

    def test_format_size(self):
        self.assertEqual(cb_alert.format_size("1.2"), "1.20亿")
        self.assertEqual(cb_alert.format_size("0.01"), "100万")
        self.assertEqual(cb_alert.format_size(None), "未知")
        self.assertEqual(cb_alert.format_size("not-a-number"), "未知")

    def test_build_message_renders_html_table_and_escapes_cells(self):
        title, content = cb_alert.build_message([
            {
                "onl_name": "A<B转债",
                "onl_code": "001234",
                "issue_size": "1.2",
                "credit_rating": "AA+",
            }
        ])
        self.assertIn("可转债申购提醒", title)
        # HTML 表格结构与边框
        self.assertIn("<table", content)
        self.assertIn("border:1px solid", content)
        self.assertIn("转债名称", content)
        # 单元格内容与 HTML 转义
        self.assertIn("A&lt;B转债", content)
        self.assertIn("001234", content)
        self.assertIn("1.20亿", content)
        self.assertIn("AA+", content)
        # 已去掉“今天可申购”标题
        self.assertNotIn("今天可申购", content)

    def test_build_message_renders_all_rows_with_alternating_background(self):
        _, content = cb_alert.build_message([
            {"onl_name": "甲转债", "onl_code": "111111", "issue_size": "1", "credit_rating": "AA"},
            {"onl_name": "乙转债", "onl_code": "222222", "issue_size": "2", "credit_rating": "A+"},
        ])
        self.assertIn("甲转债", content)
        self.assertIn("乙转债", content)
        # 隔行变色：偶数行 #fff5f5，奇数行 #ffffff
        self.assertIn("background:#fff5f5;", content)
        self.assertIn("background:#ffffff;", content)

    def test_summarize_response_body_compacts_html_and_stardust_block(self):
        self.assertEqual(
            cb_alert.summarize_response_body("<html>请求携带恶意参数 星尘盾</html>"),
            "PushPlus 星尘盾拦截：请求携带恶意参数，已被拦截。",
        )
        self.assertEqual(
            cb_alert.summarize_response_body("<!doctype html><html><body>blocked</body></html>"),
            "PushPlus 返回了 HTML 页面，可能是风控/网关拦截。",
        )

    def test_is_retryable_error_handles_transient_http_statuses(self):
        retryable = urllib.error.HTTPError(
            url="https://example.invalid",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(b""),
        )
        permanent = urllib.error.HTTPError(
            url="https://example.invalid",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )
        try:
            self.assertTrue(cb_alert.is_retryable_error(retryable))
            self.assertFalse(cb_alert.is_retryable_error(permanent))
        finally:
            retryable.close()
            permanent.close()


if __name__ == "__main__":
    unittest.main()
