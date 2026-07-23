"""골든 테스트 — 추출기가 조용히 바뀌는 것을 막는다.

python3 test_extract_features.py
"""

import math
import sys

from extract_features import extract, normalize, paragraphs, sentences

FAILED = []


def check(label, got, want, tol=1e-4):
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label} = {got!r}")


# ---------------------------------------------------------- 정규화

RAW = """---
title: "테스트"
draft: false
---

## 첫 헤딩

> 요약 인용블록입니다.
> 두 번째 줄입니다.

본문 첫 문단입니다. **강조**가 있고 [기준금리](/dictionary/base-rate/) 링크도 있습니다.

| 지표 | 값 |
| --- | --- |
| 금리 | 3.5% |

본문 둘째 문단입니다.
"""

print("normalize")
norm = normalize(RAW)
check("front matter 제거", "title:" in norm, False)
check("헤딩 제거", "첫 헤딩" in norm, False)
check("인용블록 제거", "요약 인용블록" in norm, False)
check("표 제거", "3.5%" in norm, False)
check("볼드 마크업 제거, 텍스트 유지", "**" not in norm and "강조" in norm, True)
check("링크 앵커 유지, URL 제거", "기준금리" in norm and "dictionary" not in norm, True)
check("본문 유지", "본문 둘째 문단입니다." in norm, True)

# ---------------------------------------------------------- 분할

print("\nsplit")
check("문단 수", len(paragraphs(norm)), 2)
check("문장 수", len(sentences("가나다입니다. 라마바입니다. 사아자입니다.")), 3)

# ---------------------------------------------------------- 특성

print("\nfeatures")
# 문장 4개, 전부 '~습니다'로 끝남 → 엔트로피 0, 존댓말 비율 1.0
UNIFORM = "가나다라마바사입니다. 아자차카타파하입니다. 가나다라마바사입니다. 아자차카타파하입니다."
u = extract(UNIFORM)
# 4음절 말미가 '사입니다'/'하입니다' 두 종류가 각 2회 → 정규화 엔트로피 = 1/2
check("2종 말미 균등 → evenness 0.5", u["tail_evenness"], 0.5)
check("존댓말 비율 1.0", u["formal_ending_ratio"], 1.0)
check("평서체 비율 0.0", u["plain_ending_ratio"], 0.0)
check("문장 수 4", u["_sents"], 4)

# 길이가 완전히 같은 문장 2종이 번갈아 → CV는 0이 아니지만 작다
check("균일 길이 → CV 낮음", u["sentence_len_cv"] < 0.05, True)

MIXED = "짧다. 이것은 훨씬 더 긴 문장이며 여러 절을 포함하고 있어 길이가 크게 다릅니다."
m = extract(MIXED)
check("혼합 길이 → CV 높음", m["sentence_len_cv"] > 0.5, True)
check("평서체 감지", m["plain_ending_ratio"], 0.5)

SAME_TAIL = "가나다 있습니다. 라마바 있습니다. 사아자 있습니다. 차카타 있습니다."
check("동일 말미 반복 → evenness 0", extract(SAME_TAIL)["tail_evenness"], 0.0)

VARIED = "가나다 있습니다. 라마바 했습니다. 사아자 됩니다. 차카타 옵니다."
check("말미 전부 상이 → evenness 1.0", extract(VARIED)["tail_evenness"], 1.0)

DASH = "가나다 — 라마바입니다. 사아자 — 차카타입니다."
check("em-dash 밀도 > 0", extract(DASH)["emdash_per_1k"] > 0, True)

PREVIEW = "오늘은 금리에 대해 알아보겠습니다. 함께 살펴보시죠."
check("예고형 서론 감지", extract(PREVIEW)["preview_intro_count"] >= 1.0, True)

FILLER_T = "결국 그렇습니다. 무엇보다 중요합니다. 종합적으로 봅니다."
check("filler 밀도 > 0", extract(FILLER_T)["filler_per_1k"] > 0, True)

ADJ = "다양한 요인과 중요한 변수, 효과적인 대응이 필요합니다."
check("추상 형용사 밀도 > 0", extract(ADJ)["abstract_adj_per_1k"] > 0, True)

# 문단 첫 문장이 동일 → Jaccard 1.0
SAME = "같은 문장으로 시작합니다. 뒤는 다릅니다.\n\n같은 문장으로 시작합니다. 여기도 다릅니다."
check("동일 서두 → Jaccard 1.0", extract(SAME)["para_opening_jaccard"], 1.0)

DIFF = "전혀 다른 서두입니다. 뒤는 다릅니다.\n\n완벽히 상이한 문장 구성. 여기도 다릅니다."
check("상이 서두 → Jaccard 낮음", extract(DIFF)["para_opening_jaccard"] < 0.2, True)

# ---------------------------------------------------------- 결정론

print("\ndeterminism")
check("2회 실행 동일", extract(RAW) == extract(RAW), True)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
