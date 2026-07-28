"""골든 테스트 — numerics (N1–N5).

.venv/bin/python .claude/audit/lib/test_numerics.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from numerics import claims, value_columns  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


FM = '---\ntitle: "제목 10%"\ndate: 2026-07-25T09:00:00+09:00\n---\n'

print("claims")
c = claims(FM + "\n기준금리는 2.75%로 올랐습니다. 유가는 80달러입니다.\n")
check("front matter의 10%는 제외", [x["value"] for x in c], ["2.75", "80"])
check("단위 인식", [x["unit"] for x in c], ["%", "달러"])
check("줄 번호는 파일 기준", [x["line"] for x in c], [6, 6])
check("문장이 scope", c[0]["scope"], "기준금리는 2.75%로 올랐습니다")
check("표 밖이면 in_table False", c[0]["in_table"], False)

check("긴 단위 우선 — %포인트",
      [(x["value"], x["unit"]) for x in claims("금리차가 1.5%포인트 벌어졌습니다.\n")],
      [("1.5", "%포인트")])
check("긴 단위 우선 — 배럴",
      [(x["value"], x["unit"]) for x in claims("재고는 12배럴입니다.\n")],
      [("12", "배럴")])
check("만·억이 붙으면 아예 뽑지 않는다",
      claims("하루 400만 배럴이 걸려 있습니다.\n"), [])
check("음수·천단위 구분",
      [(x["value"], x["unit"]) for x in claims("낙폭은 -23.65%였고 값은 1,200원입니다.\n")],
      [("-23.65", "%"), ("1,200", "원")])
check("단위 없는 숫자는 제외", claims("2026년 7월 16일에 발표했습니다.\n"), [])
check("코드스팬 안은 제외", claims("설정값 `rate = 10%` 을 씁니다.\n"), [])

print("value_columns")
TABLE = [
    "| 지표 | 값 | 출처 | 기준일 |",
    "|---|---|---|---|",
    "| 기준금리 | 연 2.75% | 한국은행 | 2026년 7월 16일 |",
]
check("값 열 인덱스", value_columns(TABLE), {1: 1, 2: 1})
check("값 헤더 없는 표는 제외",
      value_columns(["| A | B |", "|---|---|", "| 1% | 2% |"]), {})

t = claims(FM + "\n" + "\n".join(TABLE) + "\n")
check("표는 값 열만 추출", [(x["value"], x["unit"]) for x in t], [("2.75", "%")])
check("표 행이 scope", t[0]["scope"], TABLE[2])
check("표 안이면 in_table True", t[0]["in_table"], True)
check("표 줄 번호", t[0]["line"], 8)

print("N1 기준일 누락")
from numerics import n1_missing_asof  # noqa: E402

check("기준일 있는 문장은 통과",
      n1_missing_asof("2026년 7월 16일 기준금리는 2.75%입니다.\n"), [])
check("ISO 기준일도 통과",
      n1_missing_asof("2026-07-19 낙폭은 -23.65%였습니다.\n"), [])
check("연·월만 있어도 통과",
      n1_missing_asof("코픽스는 2026년 6월 기준 3.05%입니다.\n"), [])
check("기준일 없으면 적발",
      [x["value"] for x in n1_missing_asof("단가를 10% 올렸습니다.\n")], ["10"])
check("같은 줄 다른 문장의 기준일은 빌려오지 못한다",
      [x["value"] for x in n1_missing_asof(
          "2026년 7월 기준 3.05%입니다. 이후 10% 올랐습니다.\n")], ["10"])
check("표 행은 행 전체에서 기준일을 찾는다",
      n1_missing_asof(
          "| 지표 | 값 | 출처 | 기준일 |\n|---|---|---|---|\n"
          "| 기준금리 | 연 2.75% | 한국은행 | 2026년 7월 16일 |\n"), [])
check("기준일 열이 빈 표 행은 적발",
      [x["value"] for x in n1_missing_asof(
          "| 지표 | 값 | 출처 | 기준일 |\n|---|---|---|---|\n"
          "| 기준금리 | 연 2.75% | 한국은행 |  |\n")], ["2.75"])

print("N2 비1차 출처")
from numerics import is_primary, n2_nonprimary, numbers_block  # noqa: E402

check("1차 출처 판정", [is_primary(h) for h in
      ("ecos.bok.or.kr", "portal.kfb.or.kr", "www.hankyung.com", "bok.or.kr")],
      [True, True, False, False])

BLOCK = (
    "리드 문단입니다.\n\n"
    "## 숫자로 보면\n\n"
    "기준금리는 2.75%입니다(출처: [ECOS](https://ecos.bok.or.kr/x)).\n\n"
    "## 함께 보면 좋은 용어\n\n"
    "[한경](https://www.hankyung.com/a)\n"
)
check("블록 범위", [n for n, _ in numbers_block(BLOCK)], [4, 5, 6])
check("1차 출처만 있으면 통과", n2_nonprimary(BLOCK), [])

BAD = BLOCK.replace("https://ecos.bok.or.kr/x", "https://www.hankyung.com/n")
check("목록 밖 도메인 적발",
      [(x["line"], x["host"]) for x in n2_nonprimary(BAD)],
      [(5, "www.hankyung.com")])
check("블록 밖 링크는 무시", "hankyung" in str(n2_nonprimary(BLOCK)), False)
check("숫자 블록이 없으면 빈 결과",
      n2_nonprimary("## 실생활에서는\n\n[한경](https://www.hankyung.com/a)\n"), [])
check("내부 링크는 무시",
      n2_nonprimary("## 숫자로 보면\n\n[기준금리](/dictionary/base-rate/)\n"), [])

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")

