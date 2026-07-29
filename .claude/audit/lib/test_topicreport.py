"""골든 테스트 — topicreport. .claude/audit/README.md의 형식 계약을 코드로 고정한다.

.venv/bin/python .claude/audit/lib/test_topicreport.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contracts import check_topic_report_format  # noqa: E402
from topicreport import REQUIRED_HEADINGS, render  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


def raises(label, fn):
    try:
        fn()
    except ValueError:
        check(label, True, True)
    else:
        check(label, "예외 없음", "ValueError")


print("render")
OUT = render(
    good=[{"주제": "금리", "조정치": 2}, {"주제": "에너지", "조정치": 1}],
    bad=[{"주제": "증시", "조정치": -1}],
    conditions=["숫자 근거를 표로 제시한 글의 체류시간이 길다"],
    today="2026-09-20",
)
LINES = OUT.splitlines()
check("첫 줄 생성일", LINES[0], "생성일: 2026-09-20")
check("제목 세 개", REQUIRED_HEADINGS,
      ("## 잘 되는 주제", "## 안 되는 주제", "## 좋은 포스트의 조건"))
check("제목 전부 포함", all(h in OUT for h in REQUIRED_HEADINGS), True)
check("양수 부호 표기", "- 금리 (조정치: +2)" in OUT, True)
check("음수 부호 표기", "- 증시 (조정치: -1)" in OUT, True)
check("조건 줄", "- 숫자 근거를 표로 제시한 글의 체류시간이 길다" in OUT, True)
check("내부 기호 누출 없음", "n_g" in OUT or "r_g" in OUT, False)

IDX = [i for i, l in enumerate(LINES) if l in REQUIRED_HEADINGS]
check("제목 순서 유지", IDX, sorted(IDX))

print("계약 왕복")
check("contracts 위반 0건", check_topic_report_format(OUT), [])
EMPTY = render(good=[], bad=[], conditions=[], today="2026-09-20")
check("빈 보고서도 제목 유지", all(h in EMPTY for h in REQUIRED_HEADINGS), True)
check("빈 섹션에 '없음' 넣지 않는다", "없음" in EMPTY, False)
check("빈 보고서 위반 0건", check_topic_report_format(EMPTY), [])

print("조정치 범위")
raises("+9는 거부", lambda: render(good=[{"주제": "금리", "조정치": 9}], bad=[],
                                  conditions=[], today="2026-09-20"))
raises("-3은 거부", lambda: render(good=[], bad=[{"주제": "증시", "조정치": -3}],
                                 conditions=[], today="2026-09-20"))
raises("0은 어느 섹션에도 못 들어간다",
       lambda: render(good=[{"주제": "금리", "조정치": 0}], bad=[],
                      conditions=[], today="2026-09-20"))
raises("잘 되는 주제에 음수 거부",
       lambda: render(good=[{"주제": "금리", "조정치": -1}], bad=[],
                      conditions=[], today="2026-09-20"))
raises("안 되는 주제에 양수 거부",
       lambda: render(good=[], bad=[{"주제": "증시", "조정치": 1}],
                      conditions=[], today="2026-09-20"))

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" ", f)
    sys.exit(1)
print("전부 통과")
