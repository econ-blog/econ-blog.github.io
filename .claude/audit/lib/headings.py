"""제목 규율 검사 — 쓰기시점 전용 (T1~T4).

`/daily-post` §5가 이번 실행이 만든 포스트 1건에만 돌린다.

**감사에 배선하지 않는다.** 2026-08-10 결정으로 이미 발행된 17건은 옛 4개 고정 H2를 그대로
두기로 했고, 감사 축에 넣으면 그 17건이 매주 소견 17행으로 되살아난다. 쓰기시점 게이트와
감사시점 판정이 갈리는 것이 여기서는 의도된 것이며, N1·N2·N4·N5(`numerics.py`)와는 다르다.

규약: 표준 라이브러리 + 정규식만(`AGENTS.md`의 「.claude/audit/lib/ 규약」). 형태소 분석기를
쓰지 않으므로 조사만 잘라 낸다 — 어미는 건드리지 않는다.

사용:
    .venv/bin/python .claude/audit/lib/headings.py --file content/posts/<slug>.md
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdtext import mask_code_spans, split_front_matter  # noqa: E402

# 2026-08-10 이전 17건이 글자 단위로 공유하던 제목. 새 글에서 되살아나면 위반이다.
LEGACY_H2 = ("무슨 일이 있었나", "왜 중요한가", "나에게 무슨 의미인가", "투자 관점에서 보면")

SECTION_COUNT = 4     # 4단 구성은 유지한다 — 바뀌는 것은 제목 문자열뿐이다
TITLE_MAX = 40        # 위반선
TITLE_SOFT = 35       # 권장선. 위반으로 만들지 않는다
TOPICAL_FLOOR = 3     # 4개 중 3개는 title 의 주제어를 담아야 한다

FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
H2 = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
TITLE = re.compile(r'^title:\s*"(.*)"\s*$', re.MULTILINE)
TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|은|는|이|가|을|를|의|에|도|와|과|로)$")
PUNCT = re.compile(r"[\s.,!?·…\-—:;'\"()\[\]]")


def _norm(text: str) -> str:
    """공백·문장부호를 떼어 낸 비교용 형태. '## 왜 중요한가?' 도 옛 제목으로 잡는다."""
    return PUNCT.sub("", text)


def stems(text: str) -> set[str]:
    """토큰과 조사 제거형을 함께 낸다. 조사만 자른다 — 형태소 분석기는 규약상 금지다."""
    out = set()
    for tok in TOKEN.findall(text):
        out.add(tok)
        s = PARTICLE.sub("", tok)
        if len(s) >= 2:
            out.add(s)
    return out


def check_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    front, body = split_front_matter(raw)
    body = mask_code_spans(FENCE.sub("", body))
    heads = [h.strip() for h in H2.findall(body)]
    m = TITLE.search(front)
    title = m.group(1) if m else ""

    issues: list[dict] = []

    if len(heads) != SECTION_COUNT:
        issues.append({
            "check": "T1",
            "detail": f"본문 H2가 {len(heads)}개 — 4단 구성은 정확히 {SECTION_COUNT}개다",
        })

    legacy = {_norm(s) for s in LEGACY_H2}
    for h in heads:
        if _norm(h) in legacy:
            issues.append({
                "check": "T2",
                "detail": f"'## {h}' 는 옛 고정 제목이다 — 이 글의 주제를 말하는 제목으로 바꾼다",
            })

    if not title:
        issues.append({
            "check": "T3",
            "detail": 'front matter title 을 `title: "..."` 형태로 읽지 못했다',
        })
    else:
        if len(title) > TITLE_MAX:
            issues.append({
                "check": "T3",
                "detail": f"title {len(title)}자 > 상한 {TITLE_MAX}자 "
                          f"(권장 {TITLE_SOFT}자 이하 — 한국어 SERP는 30~35자에서 잘린다)",
            })
        if heads:
            keys = stems(title)
            topical = sum(1 for h in heads if any(k in h for k in keys))
            if topical < TOPICAL_FLOOR:
                issues.append({
                    "check": "T4",
                    "detail": f"title 의 주제어를 담은 H2가 {topical}개 — "
                              f"최소 {TOPICAL_FLOOR}개여야 한다",
                })

    return {"file": path.as_posix(), "issues": issues, "total": len(issues)}


USAGE = "usage: headings.py --file <경로>"


def main() -> None:
    argv = sys.argv[1:]
    # numerics.py 와 같은 규약 — 알아듣지 못한 호출을 통과로 흘리지 않는다.
    if argv[:1] != ["--file"] or len(argv) != 2:
        sys.exit(USAGE)
    print(json.dumps(check_file(Path(argv[1])), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
