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
from mdtext import (  # noqa: E402
    MD_LINK, inventory, split_front_matter, strip_code_spans,
)
# 1차 출처 호스트 목록은 numerics 가 단일 진리원이다 — 여기서 다시 세지 않는다.
from numerics import is_primary as _is_primary_host  # noqa: E402

DESC_MIN, DESC_MAX = 50, 160
# Q7 본문 분량 — soft는 목표 이탈, hard는 발행 게이트가 잡는 선.
BODY_SOFT_MAX, BODY_HARD_MAX = 2200, 2500
# Q9 문장 리듬 — 변동계수 하한. 실측 25퍼센타일 0.403, 중앙 0.463 기준.
RHYTHM_SOFT_MIN, RHYTHM_HARD_MIN = 0.40, 0.30
# 소수점과 문장 끝을 가르는 신호는 마침표 앞 글자가 한글인지다(numerics 와 동일).
SENT_END_Q = re.compile(r"(?<=[가-힣])\.(?=\s|$)")
# 우리가 직접 계산했다고 본문이 명시한 자리. 원문 인용과 구분되는 유일한 표지다.
DERIVED_MARK = re.compile(r"직접 계산|계산해 보면|환산하면|나눠 보면|따져 보면")

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

    임계는 구조가 강제하는 바닥에서 역산했다. 최근 14건 구간별 중앙값은
    서론+3줄요약 423자 · 본문 H2 1~3 1,425자 · 투자 관점 1,017자다. 투자 관점은
    시소표·인과 사슬·공부 포인트가 고정이라 압축 여지가 가장 작아 약 740자가
    바닥이고, 나머지를 눌러도 전체 바닥은 약 2,090자다. 그래서 상한을 2,500자에
    두면 바닥 위로 400자가 남는다 — 조이되 발행을 막지 않는 선이다.

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


def _prose_sentence_lengths(body: str) -> list[int]:
    """산문 문단의 문장 길이. 표·인용·헤딩·불릿은 리듬 대상이 아니라 제외한다."""
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "|", ">", "-", "*", "```")):
            continue
        for sent in SENT_END_Q.split(s):
            sent = sent.strip()
            if len(sent) >= 8:
                out.append(len(sent))
    return out


def sentence_rhythm(path: Path) -> dict | None:
    """Q9 — 문장 길이 변동계수(CV). 낮을수록 균일하고, 균일함이 AI 티의 핵심이다.

    AI 탐지기가 실제로 보는 것은 어휘가 아니라 통계적 리듬(burstiness)이다.
    `writing-styles.md` §7-5가 "문장 길이가 획일적인가"를 이미 묻고 있었지만
    검사기가 없었다 — 회차 1의 인과대로 그런 규칙은 무작위로 어겨진다.

    2026-09-06 실측(포스트 46건): CV 최소 0.255 · 25% 0.403 · 중앙 0.463 ·
    최대 0.837. 사람이 쓴 한국어 산문은 대체로 0.5 이상이다. 하한을 25퍼센타일
    근처인 0.40(soft)에 두고, 실제로 발행을 막는 선은 0.30(hard)으로 둔다 —
    현재 코퍼스에서 0.30 미만은 2건뿐이라 게이트가 상시로 걸리지 않는다.
    """
    raw = path.read_text(encoding="utf-8")
    if NOTICE_TAG.search(raw):
        return None
    _front, body = split_front_matter(raw)
    lengths = _prose_sentence_lengths(strip_code_spans(body))
    if len(lengths) < 5:
        return None  # 표본이 없으면 판정하지 않는다
    mean = sum(lengths) / len(lengths)
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    cv = (var ** 0.5) / mean if mean else 0.0
    level = "ok"
    if cv < RHYTHM_HARD_MIN:
        level = "hard"
    elif cv < RHYTHM_SOFT_MIN:
        level = "soft"
    return {
        "cv": round(cv, 3),
        "sentences": len(lengths),
        "mean_len": round(mean, 1),
        "level": level,
    }


def rhythm_violations(content_root: Path) -> list[dict]:
    """Q9 전수. 목표 미달(soft·hard)만 낸다."""
    out = []
    for path in sorted((content_root / "posts").glob("*.md")):
        if path.name.startswith("_"):
            continue
        r = sentence_rhythm(path)
        if r and r["level"] != "ok":
            r["file"] = path.relative_to(content_root).as_posix()
            out.append(r)
    return out


def information_gain(path: Path) -> dict:
    """Q10 — 정보 이득. 원문을 옮겨 적기만 한 글인지 본다.

    2026년 3월 코어 업데이트 이후 검색이 실제로 가르는 축은 "AI가 썼는가"가
    아니라 "이 글에만 있는 것이 있는가"다. 경쟁자가 복사할 수 없는 것은
    1차 출처를 직접 짚은 수치와 우리가 계산한 값 둘뿐이다.

    2026-09-06 실측: 1차 출처 링크를 가진 포스트는 48건 중 14건(29%)뿐이다.
    그래서 이것은 게이트가 아니라 계측이다 — 지금 막으면 71%가 보류된다.
    먼저 세고, 비율이 올라온 뒤에 조인다.
    """
    raw = path.read_text(encoding="utf-8")
    _front, body = split_front_matter(raw)
    body = strip_code_spans(body)
    hosts = []
    for _anchor, target in MD_LINK.findall(body):
        m = re.match(r"^https?://([^/]+)", target)
        if m:
            hosts.append(m.group(1))
    primary = sorted({h for h in hosts if _is_primary_host(h)})
    derived = len(DERIVED_MARK.findall(body))
    return {
        "primary_links": len(primary),
        "primary_hosts": primary,
        "derived_figures": derived,
        "has_gain": bool(primary) or derived > 0,
    }


def _information_gain_summary(content_root: Path) -> dict:
    """Q10 전수 요약. 게이트가 아니라 비율 계측이다."""
    rows = []
    for path in sorted((content_root / "posts").glob("*.md")):
        if path.name.startswith("_"):
            continue
        raw = path.read_text(encoding="utf-8")
        if NOTICE_TAG.search(raw):
            continue
        g = information_gain(path)
        g["file"] = path.relative_to(content_root).as_posix()
        rows.append(g)
    total = len(rows)
    with_gain = sum(1 for r in rows if r["has_gain"])
    return {
        "posts": total,
        "with_gain": with_gain,
        "ratio": round(with_gain / total, 3) if total else 0.0,
        "without_gain": [r["file"] for r in rows if not r["has_gain"]][:20],
    }


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


DATE_FIELD = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
# Q7·Q9 게이트가 `daily-post.md`에 배선돼 발효된 첫 발행일(병합 4551f56, 2026-09-06).
# 그 이전 글이 지금 임계로 hard 인 것은 게이트 누수가 아니라 알려진 backlog다.
GATE_EFFECTIVE = "2026-09-07"


def publish_date_of(path: Path) -> str | None:
    """front matter 의 `date:` 날짜 부분. 없으면 None."""
    front, _ = split_front_matter(path.read_text(encoding="utf-8"))
    m = DATE_FIELD.search(front)
    return m.group(1) if m else None


def publish_date_issue(target: Path, today: str) -> dict | None:
    """Q11(파일 모드) — 발행하려는 글의 `date:`가 KST 오늘인가.

    2026-09-13 05:31 KST 에 나간 글이 `date: 2026-09-12`를 달고 발행됐다.
    그 하루 밀림 자체는 사소하지만 결과가 사소하지 않다 — 09-12 에 두 건,
    09-13 에 0 건이 되어 **발행 연속성 계측이 있지도 않은 결번을 세게 된다.**
    연속 발행은 이 시스템에서 가장 비싼 자산이고, 그 자산을 재는 자가
    거짓으로 울리면 다음 회차는 없는 고장을 쫓는다.

    원인은 회차 1이 세운 인과의 다섯 번째 사례다(볼드·분량·리듬·고정요소에
    이어): `draft.md`가 `date: <현재시각 KST, +09:00>`라고만 적고 어떤
    헬퍼도 부르지 않았다. 검사기 없는 규칙은 지켜지지 않는다.

    hard 로 둔다. 고치는 데 판단이 필요 없고(`kstdate.py --stamp` 한 줄),
    그래서 게이트에 걸려도 그 회차 안에서 닫힌다 — 결번을 만들지 않는다.
    """
    got = publish_date_of(target)
    if got is None:
        return {"level": "hard", "expected": today, "got": None,
                "note": "front matter 에 date 가 없다"}
    if got != today:
        return {"level": "hard", "expected": today, "got": got,
                "note": "`.venv/bin/python .claude/audit/lib/kstdate.py --stamp` 값으로 고친다"}
    return None


def date_anomalies(content_root: Path, today: str) -> list[dict]:
    """Q11(코퍼스 모드) — 같은 날짜 두 건, 미래 날짜, 날짜 없음.

    파일 모드가 막지 못하고 지나간 것이 여기 흔적으로 남는다. 중복 날짜는
    "그날 하나도 안 나갔다"와 짝을 이루므로, 연속성을 셀 때 이 목록을 먼저
    본다.
    """
    seen: dict[str, list[str]] = {}
    out = []
    for path in sorted((content_root / "posts").glob("*.md")):
        if path.name.startswith("_"):
            continue
        raw = path.read_text(encoding="utf-8")
        if NOTICE_TAG.search(raw):
            continue  # 공지는 발행 리듬의 일부가 아니다
        rel = path.relative_to(content_root).as_posix()
        got = publish_date_of(path)
        if got is None:
            out.append({"file": rel, "issue": "date 없음"})
            continue
        if got > today:
            out.append({"file": rel, "issue": f"미래 날짜 {got}"})
        seen.setdefault(got, []).append(rel)
    for day, files in sorted(seen.items()):
        if len(files) > 1:
            out.append({"date": day, "issue": f"같은 날짜 {len(files)}건",
                        "files": files})
    return out


def gate_claim_mismatches(content_root: Path) -> list[dict]:
    """Q12 — 발행된 글 중 지금 게이트를 다시 돌리면 hard 인 것.

    커밋 본문의 `검사: 통과`를 검증하는 장치가 하나도 없었다. 실제로
    2026-09-07 발행분은 Q7 2,543자(hard)인데 `검사: 통과`로 나갔다.
    게이트가 돌지 않았는지 윤문 뒤 재검사를 건너뛰었는지는 여기서 알 수
    없지만, **알 수 없다는 것이 문제다** — 게이트는 통과했다고 말하는
    쪽이 아니라 다시 세어 보는 쪽이 진실이어야 한다.

    계측이고 게이트가 아니다. 여기 뜬 글은 이미 발행됐으므로 고칠 대상은
    그 글이 아니라 파이프라인이다. 게이트 발효(`GATE_EFFECTIVE`) 이후
    발행분만 센다 — 그 전 글까지 세면 알려진 backlog 36건에 묻혀
    정작 봐야 할 한 건이 안 보인다.
    """
    out = []
    for path in sorted((content_root / "posts").glob("*.md")):
        if path.name.startswith("_"):
            continue
        raw = path.read_text(encoding="utf-8")
        if re.search(r"^draft:\s*true\s*$", raw, re.MULTILINE):
            continue
        published = publish_date_of(path)
        if not published or published < GATE_EFFECTIVE:
            continue  # 게이트 발효 전 글은 backlog 이지 누수가 아니다
        hit = body_length_of(path)
        rhythm = sentence_rhythm(path)
        axes = []
        if hit and hit["level"] == "hard":
            axes.append(f"Q7 {hit['chars']}자")
        if rhythm and rhythm["level"] == "hard":
            axes.append(f"Q9 cv {rhythm['cv']}")
        if axes:
            out.append({"file": path.relative_to(content_root).as_posix(),
                        "hard": axes})
    return out


def _file_mode(target: Path) -> int:
    """포스트 1건의 발행 게이트 — Q7 분량 · Q9 리듬 · Q11 발행일 (· Q10 계측).

    `total` 은 hard 인 축의 수다. Q10 은 계측이므로 total 에 넣지 않는다 —
    현재 코퍼스의 41%만 충족하므로 게이트로 쓰면 대부분이 보류된다.
    """
    hit = body_length_of(target)
    chars = hit["chars"] if hit else len(
        strip_code_spans(split_front_matter(
            target.read_text(encoding="utf-8"))[1]).strip())
    q7_level = hit["level"] if hit else "ok"

    rhythm = sentence_rhythm(target)
    q9_level = rhythm["level"] if rhythm else "ok"

    today = kst_today()
    q11 = publish_date_issue(target, today)

    hard = sum(1 for lv in (q7_level, q9_level) if lv == "hard") + (1 if q11 else 0)
    print(json.dumps({
        "file": target.as_posix(),
        "Q7": {
            "chars": chars,
            "target_max": BODY_SOFT_MAX,
            "hard_max": BODY_HARD_MAX,
            "level": q7_level,
        },
        "Q9": rhythm or {"level": "ok", "note": "문장 5개 미만 — 판정 안 함"},
        "Q10": information_gain(target),
        "Q11": q11 or {"level": "ok", "date": today},
        "total": hard,
    }, ensure_ascii=False, indent=2))
    return 1 if hard else 0


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
        "Q9": rhythm_violations(CONTENT_ROOT),
        "Q10": _information_gain_summary(CONTENT_ROOT),
        "Q11": date_anomalies(CONTENT_ROOT, today),
        "Q12": gate_claim_mismatches(CONTENT_ROOT),
        "P2": internal_link_density(CONTENT_ROOT),
    }, ensure_ascii=False, indent=2))


