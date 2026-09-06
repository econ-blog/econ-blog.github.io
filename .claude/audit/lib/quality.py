"""포스트 품질·내부 순환 축 (Q1·Q3·Q4·Q5·Q6·P2).

결정론적. stdlib + 정규식만. 어떤 파일도 수정하지 않는다 — ④는 읽기 전용이다(AC #34).
Q2(미연결 용어)는 backfill.py가 같은 계산을 이미 하므로 재구현하지 않고 재사용한다.

사용:
    .venv/bin/python .claude/audit/lib/quality.py   # 전체 축 JSON
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import WRITING_STYLES_PATH, count_self_review_items  # noqa: E402
from internal_links import CONTENT_ROOT, TERMS_PATH, load_terms  # noqa: E402
from kstdate import kst_today  # noqa: E402
from mdtext import inventory, split_front_matter, strip_code_spans  # noqa: E402

DESC_MIN, DESC_MAX = 50, 160
# Q7 본문 분량 — soft는 목표 이탈, hard는 발행 게이트가 잡는 선.
BODY_SOFT_MAX, BODY_HARD_MAX = 2600, 3000

FIELD = {
    "title": re.compile(r"^title:\s*\S", re.MULTILINE),
    "date": re.compile(r"^date:\s*\S", re.MULTILINE),
    "tags": re.compile(r"^tags:\s*\[", re.MULTILINE),
    "draft": re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE),
    "source_url": re.compile(r"^source_url:\s*\S", re.MULTILINE),
}
DESCRIPTION = re.compile(r'^description:\s*"?(.*?)"?\s*$', re.MULTILINE)
NOTICE_TAG = re.compile(r'^tags:\s*\[[^\]]*"공지"', re.MULTILINE)


def _required(path: Path, front: str) -> list[str]:
    """파일 유형별 필수 필드. 공지는 source_url·description 면제(원문이 없다)."""
    base = ["title", "date", "tags", "draft"]
    if NOTICE_TAG.search(front):
        return base
    if path.parent.name == "dictionary":
        return base + ["description"]
    return base + ["source_url", "description"]


def front_matter_issues(path: Path) -> list[str]:
    """Q1 — front matter 완비 + description 길이."""
    front, _ = split_front_matter(path.read_text(encoding="utf-8"))
    if not front:
        return ["front matter 없음"]
    required = _required(path, front)
    out = []
    for name in required:
        if name == "description":
            m = DESCRIPTION.search(front)
            if not m or not m.group(1).strip():
                out.append("description 누락")
                continue
            n = len(m.group(1).strip())
            if not (DESC_MIN <= n <= DESC_MAX):
                out.append(f"description 길이 {n}자 (권장 {DESC_MIN}~{DESC_MAX})")
            continue
        if not FIELD[name].search(front):
            out.append(f"{name} 누락")
    return out


DRAFT_TRUE = re.compile(r"^draft:\s*true\s*$", re.MULTILINE)
DATE_ONLY = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def stale_drafts(content_root: Path, today: str, days: int = 7) -> list[dict]:
    """Q4 — draft: true로 days일 이상 방치된 파일."""
    out = []
    for md in sorted(content_root.rglob("*.md")):
        if md.name.startswith("_"):
            continue
        front, _ = split_front_matter(md.read_text(encoding="utf-8"))
        if not DRAFT_TRUE.search(front):
            continue
        m = DATE_ONLY.search(front)
        if not m:
            continue
        age = (date.fromisoformat(today) - date.fromisoformat(m.group(1))).days
        if age >= days:
            # posts/와 dictionary/를 함께 훑으므로 파일명만으로는 소견의 '위치'가
            # 되지 못한다 — 같은 슬러그가 양쪽에 존재할 수 있다 (AC #33).
            out.append({
                "file": md.relative_to(content_root).as_posix(),
                "date": m.group(1),
                "age": age,
            })
    return out


def self_review_budget(writing_styles_text: str, budget: int = 12) -> dict:
    """Q5 — 자가검토 항목 수와 예산 잔량. 개수만 센다(내용은 loop 소유)."""
    n = count_self_review_items(writing_styles_text)
    return {"count": n, "budget": budget, "remaining": budget - n}


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    mid = len(s) // 2
    return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def internal_link_density(content_root: Path) -> dict:
    """P2 — 포스트당 내부 링크 수. 체류시간은 pre-AdSense 유일 신호이므로 별도로 본다."""
    per = []
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name.startswith("_"):
            continue
        inv = inventory(md.read_text(encoding="utf-8"))
        per.append({"file": md.name, "internal_links": len(inv["internal"])})
    counts = [float(x["internal_links"]) for x in per]
    return {
        "per_post": per,
        "median": _median(counts),
        "zero_link_posts": [x["file"] for x in per if x["internal_links"] == 0],
    }


HANGUL_TOKEN = re.compile(r"[가-힣]{2,10}|[A-Z]{2,6}")

STOPWORDS = {
    "그리고", "하지만", "그러나", "때문에", "이라고", "합니다", "입니다", "있습니다",
    "없습니다", "됩니다", "습니다", "경우에", "우리나라", "이번에", "지난해", "올해",
    "다음과", "이라는", "라는", "정도로", "만큼", "가운데", "사람들", "이야기",
    "무슨", "의미", "관점", "지표", "상황", "영향", "수준", "가능성", "이유",
}

JOSA_SUFFIXES = ("에서", "으로", "보다", "에게", "부터", "까지", "인가", "이다", "가", "을", "를", "의", "은", "는", "이", "에", "로", "도", "와", "과")



BOLD = re.compile(r"\*\*[^*\n]+\*\*")


def bold_violations(content_root: Path) -> list[dict]:
    """Q6 — 볼드체(`**`) 사용. writing-styles.md의 '볼드체 전면 금지'를 강제한다.

    이 규칙은 2026-08-28까지 아무도 검사하지 않았고 발행글 39건 중 26건이 어겼다.
    산문 규칙 중 유일하게 결정론적으로 판정 가능한 것이라 여기에 둔다 — 나머지
    문체 규칙(선 정의 후 비유 등)은 정규식으로 셀 수 없어 post-reviewer의 몫이다.

    코드 스팬·펜스 안의 `**`는 세지 않는다. 예시로 규칙 자체를 인용하는 경우가 있다.
    """
    out = []
    for sub in ("posts", "dictionary"):
        for path in sorted((content_root / sub).glob("*.md")):
            if path.name.startswith("_"):
                continue
            _front, body = split_front_matter(path.read_text(encoding="utf-8"))
            hits = []
            for i, line in enumerate(strip_code_spans(body).split("\n"), 1):
                for m in BOLD.finditer(line):
                    hits.append({"line": i, "quote": m.group(0)[:40]})
            if hits:
                out.append({
                    "file": path.relative_to(content_root).as_posix(),
                    "count": len(hits),
                    "hits": hits[:5],
                })
    return out


def body_length_violations(content_root: Path) -> list[dict]:
    """Q7 — 본문 분량. 아무 규칙도 없어서 조용히 길어진 축이다.

    2026-09-06 실측: 발행 48건의 본문이 전반부 평균 2,437자에서 최근 5건 평균
    3,324자로 36% 늘었고, 최근 14건은 2,813자에서 3,715자까지 단조 증가했다.
    분량은 `writing-styles.md`에 목표도 상한도 없던 유일한 축이다 — 회차 1이
    확인한 인과("검사기가 붙은 규칙만 수렴한다")대로, 규칙도 검사기도 없으면
    글은 길어지는 쪽으로만 표류한다.

    본문 전체 글자수를 센다. 표·인용블록도 독자가 읽는 분량이므로 포함하고,
    코드 스팬만 제외한다(마크다운 예시는 읽는 분량이 아니다).
    공지는 분량 규율 대상이 아니다.
    """
    out = []
    for path in sorted((content_root / "posts").glob("*.md")):
        if path.name.startswith("_"):
            continue
        hit = body_length_of(path)
        if hit:
            hit["file"] = path.relative_to(content_root).as_posix()
            out.append(hit)
    return out


def body_length_of(path: Path) -> dict | None:
    """단일 포스트의 분량 판정. 목표 이내면 None. 발행 게이트(`--file`)가 쓴다."""
    raw = path.read_text(encoding="utf-8")
    if NOTICE_TAG.search(raw):
        return None
    _front, body = split_front_matter(raw)
    chars = len(strip_code_spans(body).strip())
    if chars <= BODY_SOFT_MAX:
        return None
    return {
        "chars": chars,
        "level": "hard" if chars > BODY_HARD_MAX else "soft",
        "over": chars - BODY_SOFT_MAX,
    }


def front_matter_delimiter_issues(content_root: Path) -> list[dict]:
    """Q8 — front matter 종료 구분자 위생.

    2026-09-06에 12파일(포스트 9·사전 3)이 `---본문` 형태로 종료 구분자와 첫
    본문 줄이 붙어 있는 것을 발견했다. Hugo는 이것을 관대하게 파싱해 사이트는
    멀쩡했고, 그래서 아무도 몰랐다. 그러나 `mdtext.split_front_matter`는
    `\\n---\\n`을 요구하므로 매칭에 실패했고, 실패하면 예외 대신 ('', raw)를
    돌려준다 — front matter 전체가 본문으로 취급되며 그 사실은 어디에도
    보고되지 않는다. Q1·Q6·Q7·numerics가 전부 그 12파일을 잘못 읽고 있었다.

    조용히 틀리는 것이 이 결함의 본질이므로 재발을 여기서 잡는다.
    """
    out = []
    for sub in ("posts", "dictionary"):
        for path in sorted((content_root / sub).glob("*.md")):
            if path.name.startswith("_"):
                continue
            raw = path.read_text(encoding="utf-8")
            if not raw.startswith("---\n"):
                out.append({
                    "file": path.relative_to(content_root).as_posix(),
                    "issue": "front matter 시작 구분자 없음",
                })
            elif split_front_matter(raw)[0] == "":
                out.append({
                    "file": path.relative_to(content_root).as_posix(),
                    "issue": "종료 구분자가 본문과 붙어 있음 (`---본문`)",
                })
    return out


def trim_josa(tok: str) -> str:
    """한국어 조사 접미사를 잘라내어 동일 명사의 격변화를 통합한다."""
    if len(tok) <= 2:
        return tok
    for j in JOSA_SUFFIXES:
        if tok.endswith(j) and len(tok) - len(j) >= 2:
            return tok[:-len(j)]
    return tok


def term_candidates(
    content_root: Path, terms: dict, min_posts: int = 2, min_count: int = 3
) -> list[dict]:
    """Q3 — 반복 등장하지만 _terms.yaml에 없는 토큰의 결정론적 빈도표.

    경제 용어인지는 판정하지 않는다 — 그 선별은 스테이지의 LLM이 하며 재현되지
    않는다. 형태소 분석기 대신 조사 접미사 제거(trim_josa)로 체언을 정규화한다.
    """
    known = set()
    for t in terms.values():
        known.add(t["title"])
        known.update(t["aliases"])
        # 괄호 표기 변형("코픽스(COFIX)")의 앞부분도 등재로 간주
        known.add(t["title"].split("(")[0].strip())

    doc_hits: dict = {}
    total: dict = {}
    for md in sorted((content_root / "posts").glob("*.md")):
        if md.name.startswith("_"):
            continue
        _, body = split_front_matter(md.read_text(encoding="utf-8"))
        seen_here = set()
        for raw_tok in HANGUL_TOKEN.findall(strip_code_spans(body)):
            tok = trim_josa(raw_tok)
            if tok in known or tok in STOPWORDS:
                continue
            total[tok] = total.get(tok, 0) + 1
            seen_here.add(tok)
        for tok in seen_here:
            doc_hits[tok] = doc_hits.get(tok, 0) + 1

    out = [
        {"token": tok, "posts": doc_hits[tok], "count": total[tok]}
        for tok in total
        if doc_hits[tok] >= min_posts and total[tok] >= min_count
    ]
    out.sort(key=lambda x: (-x["count"], -x["posts"], x["token"]))
    return out


def _file_mode(target: Path) -> int:
    """포스트 1건의 분량 게이트. hard 초과일 때만 종료코드 1."""
    hit = body_length_of(target)
    chars = hit["chars"] if hit else len(
        strip_code_spans(split_front_matter(
            target.read_text(encoding="utf-8"))[1]).strip())
    level = hit["level"] if hit else "ok"
    print(json.dumps({
        "file": target.as_posix(),
        "chars": chars,
        "target_max": BODY_SOFT_MAX,
        "hard_max": BODY_HARD_MAX,
        "level": level,
        "total": 1 if level == "hard" else 0,
    }, ensure_ascii=False, indent=2))
    return 1 if level == "hard" else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--file":
        sys.exit(_file_mode(Path(sys.argv[2])))
    today = sys.argv[1] if len(sys.argv) > 1 else kst_today()
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))
    files = sorted((CONTENT_ROOT / "posts").glob("*.md")) + \
        sorted((CONTENT_ROOT / "dictionary").glob("*.md"))
    ws = WRITING_STYLES_PATH.read_text(encoding="utf-8")
    print(json.dumps({
        "Q1": [
            {
                "file": p.relative_to(CONTENT_ROOT).as_posix(),
                "issues": front_matter_issues(p),
            }
            for p in files
            if not p.name.startswith("_") and front_matter_issues(p)
        ],
        "Q3": term_candidates(CONTENT_ROOT, terms)[:30],
        "Q4": stale_drafts(CONTENT_ROOT, today),
        "Q5": self_review_budget(ws),
        "Q6": bold_violations(CONTENT_ROOT),
        "Q7": body_length_violations(CONTENT_ROOT),
        "Q8": front_matter_delimiter_issues(CONTENT_ROOT),
        "P2": internal_link_density(CONTENT_ROOT),
    }, ensure_ascii=False, indent=2))


