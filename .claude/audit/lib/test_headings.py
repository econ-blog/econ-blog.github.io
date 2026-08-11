import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from headings import check_file, stems  # noqa: E402

GOOD = '''---
title: "근원물가가 2년 7개월 만에 최고치를 찍은 이유"
date: 2026-08-10T09:00:00+09:00
description: "설명"
tags: ["금리", "물가"]
draft: true
source_url: "https://example.com/a"
---

첫 문단이다.

> 요약 인용블록.

## 근원물가가 최고치를 찍은 경위

내용.

## 근원물가가 왜 한은의 발목을 잡나

내용.

## 최고치가 내 대출 이자에 닿는 경로

내용.

## 물가 국면에서 자산군이 갈리는 지점

내용.
'''

LEGACY = GOOD.replace("## 근원물가가 최고치를 찍은 경위", "## 무슨 일이 있었나") \
             .replace("## 근원물가가 왜 한은의 발목을 잡나", "## 왜 중요한가") \
             .replace("## 최고치가 내 대출 이자에 닿는 경로", "## 나에게 무슨 의미인가") \
             .replace("## 물가 국면에서 자산군이 갈리는 지점", "## 투자 관점에서 보면")

LONG_TITLE = GOOD.replace(
    '"근원물가가 2년 7개월 만에 최고치를 찍은 이유"',
    '"근원물가가 2년 7개월 만에 최고치를 찍으며 한국은행의 8월 금리 결정 셈법이 복잡해진 이유"',
)

THREE_SECTIONS = GOOD.replace("## 물가 국면에서 자산군이 갈리는 지점\n\n내용.\n", "")

GENERIC = GOOD.replace("## 근원물가가 최고치를 찍은 경위", "## 배경") \
              .replace("## 근원물가가 왜 한은의 발목을 잡나", "## 의미") \
              .replace("## 최고치가 내 대출 이자에 닿는 경로", "## 영향") \
              .replace("## 물가 국면에서 자산군이 갈리는 지점", "## 앞으로")


def write(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "sample.md"
    p.write_text(text, encoding="utf-8")
    return p


def checks(text: str) -> list[str]:
    return [i["check"] for i in check_file(write(text))["issues"]]


class TestHeadings(unittest.TestCase):
    def test_good_post_passes(self):
        self.assertEqual(check_file(write(GOOD))["total"], 0)

    def test_legacy_headings_flagged(self):
        self.assertEqual(checks(LEGACY).count("T2"), 4)

    def test_long_title_flagged(self):
        self.assertEqual(checks(LONG_TITLE), ["T3"])

    def test_wrong_section_count_flagged(self):
        self.assertIn("T1", checks(THREE_SECTIONS))

    def test_generic_headings_flagged(self):
        self.assertEqual(checks(GENERIC), ["T4"])

    def test_stems_strips_particles(self):
        self.assertIn("근원물가", stems("근원물가가 최고치를 찍었다"))
        self.assertIn("최고치", stems("근원물가가 최고치를 찍었다"))


if __name__ == "__main__":
    unittest.main()
