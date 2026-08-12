#!/usr/bin/env python3
"""Unit tests for source-preserving HTML/CSS patches."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import html_patch as hp


SAMPLE = """<!doctype html>
<html lang="ko">
<body>
<section class="slide">
  <div class="card edge" data-region="kpi-revenue" data-label="매출 KPI 카드">
      <p class="t-cap" data-part="label">누적 매출</p>
      <p class="t-kpi" data-part="value">142<span style="font-size:32px">억</span></p>
      <p class="t-small" data-part="delta">전년 동기 대비 <b class="em">+38%</b></p>
  </div>
  <p class="t-head" data-region="insight" data-part="title">엔터프라이즈가 성장을 끌었다</p>
  <!-- keep me -->
</section>
</body>
</html>
"""


class HtmlPatchTests(unittest.TestCase):
    def test_text_leaf_preserves_surroundings(self):
        out = hp.apply_html_patch(SAMPLE, "insight", "title", {"text": "새 제목"})
        self.assertIn(">새 제목</p>", out)
        self.assertIn("<!-- keep me -->", out)
        self.assertIn('data-label="매출 KPI 카드"', out)

    def test_non_leaf_rejected(self):
        with self.assertRaises(hp.PatchError) as ctx:
            hp.apply_html_patch(SAMPLE, "kpi-revenue", "value", {"text": "200"})
        self.assertEqual(ctx.exception.code, "non_leaf")

    def test_style_add_and_clear(self):
        out = hp.apply_html_patch(
            SAMPLE, "insight", "title",
            {"style": {"color": "#f96167", "font-size": "22px"}},
        )
        self.assertIn('style="', out)
        self.assertIn("color: #f96167", out)
        self.assertIn("font-size: 22px", out)
        out2 = hp.apply_html_patch(
            out, "insight", "title",
            {"style": {"color": None, "font-size": None}},
        )
        # style attr removed entirely when empty
        m = None
        for line in out2.splitlines():
            if 'data-part="title"' in line:
                m = line
        self.assertIsNotNone(m)
        self.assertNotIn("style=", m)

    def test_missing_and_duplicate(self):
        with self.assertRaises(hp.PatchError) as ctx:
            hp.apply_html_patch(SAMPLE, "nope", None, {"text": "x"})
        self.assertEqual(ctx.exception.code, "not_found")
        dup = SAMPLE.replace(
            'data-region="insight" data-part="title"',
            'data-region="insight" data-part="title"',
        ) + '<p data-region="insight" data-part="title">two</p>'
        with self.assertRaises(hp.PatchError) as ctx:
            hp.apply_html_patch(dup, "insight", "title", {"text": "x"})
        self.assertEqual(ctx.exception.code, "duplicate")

    def test_theme_tokens_and_markers(self):
        css = """/* deck */
:root {
  --brand: #1e2761;
  --accent: #f96167;
}
"""
        tokens = hp.read_theme_tokens(css)
        self.assertEqual(tokens["--brand"], "#1e2761")
        marked = hp.ensure_theme_markers(css)
        self.assertIn(hp.THEME_START, marked)
        patched = hp.apply_theme_patch(css, {"--accent": "#00aa00"})
        self.assertIn("--accent: #00aa00;", patched)
        self.assertIn(hp.THEME_START, patched)
        tokens2 = hp.read_theme_tokens(patched)
        self.assertEqual(tokens2["--accent"], "#00aa00")

    def test_atomic_write_and_revision(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.html"
            hp.atomic_write(p, "hello")
            self.assertEqual(p.read_text(), "hello")
            r1 = hp.file_revision(p)
            hp.atomic_write(p, "hello!")
            r2 = hp.file_revision(p)
            self.assertNotEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()
