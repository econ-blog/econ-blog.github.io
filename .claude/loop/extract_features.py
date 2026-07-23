"""텍스트 특성 추출기 — loop-writing-style의 유일한 측정 주체.

결정론적. 표준 라이브러리 + 정규식만 사용한다.
어떤 LLM도 여기의 숫자를 산출하지 않는다.

사용:
    python3 extract_features.py <파일...> [--json]
"""

import json
import math
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 정규화

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
BLOCKQUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)
HEADING = re.compile(r"^\s*#{1,6}\s+.*$", re.MULTILINE)
LIST_MARK = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML_TAG = re.compile(r"<[^>]+>")
BOLD = re.compile(r"\*\*([^*]*)\*\*")


def normalize(raw: str) -> str:
    """마크다운 골격을 제거하고 산문만 남긴다.

    front matter / 표 / 인용블록 요약 / 헤딩은 writing-styles.md가 의무화한
    구조물이라 참조 코퍼스에 있을 이유가 없다. 그 차이를 AI 흔적으로 오인하지
    않도록 특성 계산 전에 양쪽에서 동일하게 걷어낸다.
    """
    t = FRONT_MATTER.sub("", raw)
    t = TABLE_ROW.sub("", t)
    t = BLOCKQUOTE.sub("", t)
    t = HEADING.sub("", t)
    t = MD_LINK.sub(r"\1", t)
    t = BOLD.sub(r"\1", t)
    t = HTML_TAG.sub("", t)
    t = LIST_MARK.sub("", t)
    # 네이버 에디터가 심는 zero-width space·nbsp·연속 공백을 걷어낸다.
    # 이걸 남기면 문장 길이가 서식 잡음만큼 부풀고, 부푸는 양이 문장마다
    # 달라서 코퍼스 쪽 분산이 실제보다 커진다(측정 대상을 오염시킴).
    t = t.replace("​", "").replace("﻿", "").replace("\xa0", " ")
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [s.strip() for s in parts if len(s.strip()) >= 2]


# ---------------------------------------------------------------- 보조

def _cv(xs: list[float]) -> float:
    """변동계수. 평균 대비 흩어짐 — 문장/문단 길이 리듬 지표."""
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var) / mean


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return abs(-sum((c / total) * math.log2(c / total) for c in counts if c))


def _per_1k(n: int, text: str) -> float:
    return 1000.0 * n / len(text) if text else 0.0


def _ending_token(sentence: str) -> str:
    """문장 말미 2음절 — 어투 레지스터(존댓말/평서체) 판정용."""
    s = re.sub(r"[^\w가-힣]+$", "", sentence)
    return s[-2:] if len(s) >= 2 else s


def _tail_token(sentence: str) -> str:
    """문장 말미 4음절 — 어간+어미 결합형.

    순수 종결어미('습니다')만 보면 한국어 존댓말 산문은 문법상 거의 한 값으로
    수렴해 변별력이 없다. 4음절을 쓰면 '있습니다/했습니다/커졌습니다'가 구분되어
    문장 끝 어휘 반복을 잡을 수 있다. 대신 어간 일부가 섞이는 것을 감수한다.
    """
    s = re.sub(r"[^\w가-힣]+$", "", sentence)
    return s[-4:] if len(s) >= 4 else s


# ---------------------------------------------------------------- 어휘 목록

FORMAL_END = re.compile(r"(니다|니까|세요|예요|에요|죠|군요|는데요)$")
# 평서체는 '다'로 끝나되 존댓말 '니다'가 아닌 것. 동사 어미를 열거하면
# '짧다' 같은 형용사 평서형을 놓친다.
PLAIN_END = re.compile(r"(?<!니)다$")

FILLER = ["결국", "종합적으로", "무엇보다", "특히", "다만", "즉", "한편",
          "이처럼", "그만큼", "사실상", "다시 말해", "요컨대"]
ABSTRACT_ADJ = ["다양한", "중요한", "효과적인", "핵심적인", "주요한", "상당한",
                "매우 ", "significant", "복합적인", "다각적인", "긍정적인",
                "부정적인", "지속적인"]
PREVIEW_INTRO = [r"에 대해 (알아|살펴|짚어)", r"를 (알아|살펴|짚어)보", r"가 화제",
                 r"에 대해 정리", r"를 정리해", r"함께 (알아|살펴)"]


# ---------------------------------------------------------------- 특성

def f_sentence_len_mean(text, paras, sents):
    return sum(len(s) for s in sents) / len(sents) if sents else 0.0


def f_sentence_len_cv(text, paras, sents):
    """문장 길이 변동계수. 낮을수록 리듬이 평평하다 = LLM 흔적 후보."""
    return _cv([float(len(s)) for s in sents])


def f_para_len_cv(text, paras, sents):
    return _cv([float(len(p)) for p in paras])


def f_emdash_per_1k(text, paras, sents):
    return _per_1k(len(re.findall(r"[—–]", text)), text)


def f_tail_evenness(text, paras, sents):
    """문장 말미 4음절 분포의 정규화 엔트로피(0~1). 낮을수록 끝맺음이 반복적.

    log2(문장 수)로 나눠 길이가 다른 글끼리 비교 가능하게 만든다. 정규화 없이
    쓰면 문장이 많은 글이 자동으로 높게 나온다.
    """
    toks = {}
    for s in sents:
        t = _tail_token(s)
        if t:
            toks[t] = toks.get(t, 0) + 1
    if len(sents) < 2:
        return 0.0
    return _entropy(list(toks.values())) / math.log2(len(sents))


def f_formal_ending_ratio(text, paras, sents):
    """존댓말 종결어미 비율. 코퍼스 레지스터 필터에도 쓰인다."""
    if not sents:
        return 0.0
    n = sum(1 for s in sents if FORMAL_END.search(_ending_token(s) or ""))
    return n / len(sents)


def f_plain_ending_ratio(text, paras, sents):
    if not sents:
        return 0.0
    n = sum(1 for s in sents if PLAIN_END.search(re.sub(r"[^\w가-힣]+$", "", s)))
    return n / len(sents)


def f_filler_per_1k(text, paras, sents):
    return _per_1k(sum(text.count(w) for w in FILLER), text)


def f_abstract_adj_per_1k(text, paras, sents):
    return _per_1k(sum(text.count(w) for w in ABSTRACT_ADJ), text)


def f_preview_intro_count(text, paras, sents):
    return float(sum(len(re.findall(p, text)) for p in PREVIEW_INTRO))


def f_para_opening_jaccard(text, paras, sents):
    """인접 문단 첫 문장의 문자 3-gram Jaccard 평균.

    임베딩 코사인 유사도의 대체재다. 열등하다는 점을 인정하고 채택했다 —
    결정론성과 무의존성이 정확도보다 우선이라고 판단.
    """
    def grams(s):
        s = s[:60]
        return {s[i:i + 3] for i in range(max(0, len(s) - 2))}

    openers = [grams(sentences(p)[0]) for p in paras if sentences(p)]
    if len(openers) < 2:
        return 0.0
    scores = []
    for a, b in zip(openers, openers[1:]):
        union = a | b
        scores.append(len(a & b) / len(union) if union else 0.0)
    return sum(scores) / len(scores)


FEATURES = {
    "sentence_len_mean": f_sentence_len_mean,
    "sentence_len_cv": f_sentence_len_cv,
    "para_len_cv": f_para_len_cv,
    "emdash_per_1k": f_emdash_per_1k,
    "tail_evenness": f_tail_evenness,
    "formal_ending_ratio": f_formal_ending_ratio,
    "plain_ending_ratio": f_plain_ending_ratio,
    "filler_per_1k": f_filler_per_1k,
    "abstract_adj_per_1k": f_abstract_adj_per_1k,
    "preview_intro_count": f_preview_intro_count,
    "para_opening_jaccard": f_para_opening_jaccard,
}


def extract(raw: str) -> dict:
    text = normalize(raw)
    paras = paragraphs(text)
    sents = sentences(text)
    out = {"_chars": len(text), "_paras": len(paras), "_sents": len(sents)}
    for name, fn in FEATURES.items():
        out[name] = round(fn(text, paras, sents), 4)
    return out


def main(argv):
    as_json = "--json" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    results = {p.name: extract(p.read_text(encoding="utf-8")) for p in paths}

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    names = list(next(iter(results.values())).keys())
    w = max(len(n) for n in names) + 1
    cols = list(results)
    print("특성".ljust(w) + "".join(c[:18].rjust(20) for c in cols) + "     CV")
    print("-" * (w + 20 * len(cols) + 8))
    for n in names:
        vals = [results[c][n] for c in cols]
        cv = _cv([float(v) for v in vals])
        print(n.ljust(w) + "".join(f"{v:>20.4g}" for v in vals) + f"{cv:>8.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
