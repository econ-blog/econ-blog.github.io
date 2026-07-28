"""수치 무결성 축 ⑥ (N1–N5). 순수·결정론. 표준 라이브러리 + 정규식만.

⑥은 원장을 갖지 않는다(AC #61). 매 실행 content/에서 새로 계산하며 같은 입력에
같은 출력을 낸다. content/를 수정하지 않고 네트워크를 쓰지 않는다.

내적 정합성만 본다 — 값이 ECOS의 실제 값과 다르더라도 여기서는 통과한다.
⑥이 조용하다는 것은 "숫자가 맞다"가 아니라 "저장소가 스스로와 모순되지
않는다"는 뜻이다. (SEED Known limits #20)

사용:
    .venv/bin/python .claude/audit/lib/numerics.py    # N1–N5 JSON
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from internal_links import CONTENT_ROOT, TERMS_PATH, load_terms  # noqa: E402
from mdtext import MD_LINK, mask_code_spans, split_front_matter  # noqa: E402

# AC #54 — 단위는 닫힌 목록. 긴 것을 먼저 둬야 '%포인트'가 '%'에, '배럴'이
# '배'에 먹히지 않는다. 정규식 대안(|)은 왼쪽부터 시도하기 때문이다.
UNITS = ("%포인트", "%p", "%", "원", "달러", "배럴", "배", "bp")
NUMBER = r"-?\d[\d,]*(?:\.\d+)?"
# 숫자와 단위 사이에 만·억이 끼면(400만 배럴) 아예 매치되지 않는다. 이것은 의도한
# 손실이다 — 만을 무시하고 400으로 읽으면 N3·N5가 '400만 배럴'과 '400 배럴'을
# 같은 값으로 대조해 없는 모순을 만든다. 뽑지 않는 쪽이 틀리게 뽑는 쪽보다 낫다.
CLAIM = re.compile(rf"({NUMBER})\s*({'|'.join(re.escape(u) for u in UNITS)})")

# 연·월·일, 연·월, 연도 단독(2025년/2025년 기준), 분기(2분기/2025년 2분기), ISO형 공존.
ASOF = re.compile(
    r"20\d{2}년(?:\s*[1-4]분기|\s*\d{1,2}월(?:\s*\d{1,2}일)?)?"
    r"|[1-4]분기"
    r"|20\d{2}-\d{2}(?:-\d{2})?"
)

TABLE_ROW = re.compile(r"^\s*\|")
# 소수점과 문장 끝을 가르는 유일한 신호는 마침표 앞 글자가 한글인지다.
SENT_END = re.compile(r"(?<=[가-힣])\.(?=\s|$)")

# AC #56 — draft.md:68이 정한 1차 출처. SEED D4(AC #44)의 목록과 다르다(D4는
# bok.or.kr을 포함하고 portal.kfb.or.kr을 빼놓았다). AC #56이 draft.md를
# 지목하므로 N2는 이쪽을 따른다. 목록 자체를 이 축이 고치지 않는다.
PRIMARY_HOSTS = ("ecos.bok.or.kr", "fred.stlouisfed.org", "kosis.kr",
                 "dart.fss.or.kr", "portal.kfb.or.kr")
HOST = re.compile(r"^https?://([^/?#]+)")
NUMBERS_HEADER = "## 숫자로 보면"

# AC #58 — 닫힌 목록. tuple 순서가 words 필드의 출력 순서를 정한다.
SUPERLATIVES = ("사상 최고", "사상 최대", "사상 최저",
                "역대 최고", "역대 최대", "역대 최저", "최초로")
# 기간이 명시된 최상급('38년 만에 최고')은 검증 가능한 형태이므로 대상이 아니다.
BOUNDED = re.compile(r"\d+\s*(?:년|개월|주|일)\s*만에")

# 공지(welcome.md)와 섹션 인덱스는 해설글이 아니므로 대상에서 뺀다.
EXCLUDE = {"_index.md", "welcome.md"}
CAP = 10  # AC #60 — 한 번의 감사에서 출력하는 최대 소견 수


def _rel(path: Path | str) -> str:
    """리포트 및 JSON 출력의 상대 경로 (repository root 기준, e.g. content/posts/foo.md)."""
    p = Path(path)
    try:
        return p.relative_to(CONTENT_ROOT.parent).as_posix()
    except ValueError:
        return p.as_posix()


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def value_columns(lines: list[str]) -> dict[int, int]:
    """행 인덱스 → 그 표의 '값' 열 인덱스. (AC #54 "표 안에서는 값 열만 본다")

    '값' 헤더가 없는 표는 어느 열이 값인지 결정론적으로 알 수 없으므로 통째로
    제외한다 — 재현율을 포기하고 오탐을 막는다.
    """
    out: dict[int, int] = {}
    col = None
    for i, line in enumerate(lines):
        if not TABLE_ROW.match(line):
            col = None
            continue
        cells = _cells(line)
        if "값" in cells:
            col = cells.index("값")
        elif col is not None:
            out[i] = col
    return out


def claims(raw: str) -> list[dict]:
    """수치 주장 목록. {line, value, unit, scope, in_table}.

    line은 파일 기준 1-origin. scope는 기준일·지표 판정의 단위다.
    """
    front, body = split_front_matter(raw)
    offset = front.count("\n")
    lines = mask_code_spans(body).split("\n")
    vcols = value_columns(lines)
    out = []
    for i, line in enumerate(lines):
        in_table = bool(TABLE_ROW.match(line))
        if in_table:
            if i not in vcols:
                continue
            cells = _cells(line)
            col = vcols[i]
            if col >= len(cells):
                continue
            scopes = [(cells[col], line.strip())]
        else:
            scopes = [(s, s.strip()) for s in SENT_END.split(line) if s.strip()]
        for text, scope in scopes:
            for m in CLAIM.finditer(text):
                out.append({
                    "line": offset + i + 1,
                    "value": m.group(1),
                    "unit": m.group(2),
                    "scope": scope,
                    "in_table": in_table,
                })
    return out


def n1_missing_asof(raw: str) -> list[dict]:
    """N1 — 같은 문장/표 행에 기준일이 없는 수치 주장. (AC #55)

    writing-styles.md가 기준일 병기를 이미 요구하므로 규칙 위반이지 취향이 아니다.
    """
    return [c for c in claims(raw) if not ASOF.search(c["scope"])]


def is_primary(host: str) -> bool:
    """1차 출처 호스트인가. 서브도메인은 허용하되 상위 도메인은 아니다."""
    host = host.lower()
    return any(host == p or host.endswith("." + p) for p in PRIMARY_HOSTS)


def numbers_block(raw: str) -> list[tuple[int, str]]:
    """'## 숫자로 보면' 블록의 (파일 기준 줄번호, 줄). 다음 '## '에서 끝난다."""
    front, body = split_front_matter(raw)
    offset = front.count("\n")
    out, inside = [], False
    for i, line in enumerate(mask_code_spans(body).split("\n")):
        if line.startswith("## "):
            inside = line.strip() == NUMBERS_HEADER
            continue
        if inside:
            out.append((offset + i + 1, line))
    return out


def n2_nonprimary(raw: str) -> list[dict]:
    """N2 — 숫자 슬롯 안의 외부 링크 중 1차 출처 목록 밖인 것. (AC #56)

    도메인 문자열 비교만 한다. 문서를 열지 않으며 네트워크를 쓰지 않는다.
    """
    out = []
    for lineno, line in numbers_block(raw):
        for _anchor, target in MD_LINK.findall(line):
            m = HOST.match(target)
            if not m:
                continue
            host = m.group(1).lower()
            if not is_primary(host):
                out.append({"line": lineno, "host": host, "target": target})
    return out


def n4_unbounded_superlative(raw: str) -> list[dict]:
    """N4 — 기간 한정도 1차 출처 링크도 없는 최상급. (AC #58)

    문단 = 줄이다. 이 저장소의 마크다운이 문단을 한 줄로 쓰기 때문이다(실측).
    """
    front, body = split_front_matter(raw)
    offset = front.count("\n")
    out = []
    for i, line in enumerate(mask_code_spans(body).split("\n")):
        hits = [w for w in SUPERLATIVES if w in line]
        if not hits or BOUNDED.search(line):
            continue
        hosts = [HOST.match(t).group(1) for _a, t in MD_LINK.findall(line)
                 if HOST.match(t)]
        if any(is_primary(h) for h in hosts):
            continue
        out.append({"line": offset + i + 1, "words": hits, "text": line.strip()})
    return out


def norm_value(value: str) -> float:
    """천단위 구분을 지우고 실수로. '2.50'과 '2.5'를 같은 값으로 만든다."""
    return float(value.replace(",", ""))


def norm_asof(scope: str) -> str | None:
    """기준일을 'YYYY-MM' 또는 'YYYY-MM-DD'로 정규화. 없으면 None.

    한글형('2026년 7월 16일')과 ISO형('2026-07-19')이 실제로 공존하므로
    대조 전에 한 형태로 모은다.
    """
    m = ASOF.search(scope)
    if not m:
        return None
    s = m.group(0)
    k = re.match(r"(20\d{2})년(?:\s*([1-4])분기|\s*(\d{1,2})월(?:\s*(\d{1,2})일)?)?", s)
    if not k:
        return s
    year = k.group(1)
    q = k.group(2)
    month = k.group(3)
    day = k.group(4)
    if q:
        return f"{year}-Q{q}"
    if month:
        out = f"{year}-{int(month):02d}"
        if day:
            out += f"-{int(day):02d}"
        return out
    return year


def indicator_of(scope: str, terms: dict) -> str | None:
    """scope에 등장하는 _terms.yaml title/alias 중 가장 긴 것의 slug. (AC #57)

    가장 긴 것을 고르는 이유: '기준금리'와 '금리'가 둘 다 사전에 있으면 짧은
    쪽이 먼저 걸려 서로 다른 지표가 한 통에 섞인다.
    """
    best = None
    for slug, entry in terms.items():
        for name in [entry["title"], *entry.get("aliases", [])]:
            if name and name in scope and (best is None or len(name) > best[0]):
                best = (len(name), slug)
    return best[1] if best else None


def n3_conflicts(files: list[Path], terms: dict) -> list[dict]:
    """N3 — 같은 지표·기준일·단위에 값이 다른 경우. (AC #57 + 좁힌 세 규칙)

    지표 동일성은 _terms.yaml로만 판정한다. 사전 항목이 없는 지표는 대조되지
    않으며, 커버리지가 _terms.yaml 크기에 묶이는 것이 의도된 경계다.

    이름만으로는 수량이 식별되지 않아('브렌트유'가 종가·장중가·등락률을 모두
    덮는다) 문면 그대로면 오탐만 난다. 세 규칙으로 좁힌다:
      1. 단위가 다르면 다른 수량이다 — 버킷 키에 unit을 넣는다.
      2. 한 scope가 그 버킷의 값을 전부 담고 있으면 전이·열거이지 모순이 아니다.
      3. 파일이 교차할 때만 낸다 — 한 글 안에서 여러 변형을 나란히 적는 것은 정상.
    """
    buckets: dict[tuple, list[tuple]] = {}
    for path in files:
        rel_path = _rel(path)
        for c in claims(path.read_text(encoding="utf-8")):
            slug = indicator_of(c["scope"], terms)
            asof = norm_asof(c["scope"])
            if not slug or not asof:
                continue
            buckets.setdefault((slug, asof, c["unit"]), []).append(
                (norm_value(c["value"]), rel_path, c["line"], c["scope"]))

    out = []
    for (slug, asof, unit), items in sorted(buckets.items()):
        values = {v for v, _f, _l, _s in items}
        if len(values) < 2:
            continue
        by_scope: dict[str, set] = {}
        for v, _f, _l, scope in items:
            by_scope.setdefault(scope, set()).add(v)
        if any(vs == values for vs in by_scope.values()):
            continue  # 규칙 2 — 한 scope 안의 전이·열거
        if len({f for _v, f, _l, _s in items}) < 2:
            continue  # 규칙 3 — 파일 교차만
        locs: dict[float, list[str]] = {}
        for v, f, line, _s in items:
            locs.setdefault(v, []).append(f"{f}:{line}")
        out.append({
            "indicator": slug, "asof": asof, "unit": unit,
            "values": [{"value": v, "at": sorted(set(locs[v]))}
                       for v in sorted(values)],
        })
    return out


def n5_reprint(dict_files: list[Path], post_files: list[Path]) -> list[dict]:
    """N5 — 사전의 수치가 포스트의 수치와 값·단위 모두 같은 경우. (AC #59)

    draft.md의 "이미 발행된 글의 수치를 사전으로 옮겨 적지 않는다"가 근거다.
    우연의 일치일 수 있으므로 판정이 아니라 확인 요청으로 낸다.
    """
    in_posts: dict[tuple, list[str]] = {}
    for path in post_files:
        rel_path = _rel(path)
        for c in claims(path.read_text(encoding="utf-8")):
            key = (norm_value(c["value"]), c["unit"])
            in_posts.setdefault(key, []).append(f"{rel_path}:{c['line']}")
    out = []
    for path in dict_files:
        rel_path = _rel(path)
        for c in claims(path.read_text(encoding="utf-8")):
            key = (norm_value(c["value"]), c["unit"])
            if key in in_posts:
                out.append({"at": f"{rel_path}:{c['line']}",
                            "value": c["value"], "unit": c["unit"],
                            "also_in": sorted(set(in_posts[key]))})
    return out


def _md(sub: str) -> list[Path]:
    return sorted(p for p in (CONTENT_ROOT / sub).glob("*.md")
                  if p.name not in EXCLUDE)


def claims_summary(files: list[Path]) -> dict:
    """수치 주장의 총량. N1 건수의 분모이며 회피 탐지의 유일한 신호다.

    N1을 작성 시점에 막으면 가장 싼 해소 경로는 기준일 추가가 아니라 수치 삭제다.
    건수만 세면 개선과 회피가 같은 숫자로 보인다 — 분모가 함께 줄면 비율이
    개선돼 보이지 않는다는 것이 이 값을 고른 이유다. (Plan 5 판단 라)
    """
    per_doc = [len(claims(p.read_text(encoding="utf-8"))) for p in files]
    total = sum(per_doc)
    ordered = sorted(per_doc)
    return {
        "claims_total": total,
        "claims_docs": len(per_doc),
        "claims_per_post": round(total / len(per_doc), 1) if per_doc else 0.0,
        "claims_median": ordered[len(ordered) // 2] if ordered else 0,
    }


def main() -> None:
    posts, dicts = _md("posts"), _md("dictionary")
    terms = load_terms(TERMS_PATH.read_text(encoding="utf-8"))

    rows = []
    for path in posts + dicts:
        raw = path.read_text(encoding="utf-8")
        at = _rel(path)
        for c in n1_missing_asof(raw):
            rows.append({"check": "N1", "at": f"{at}:{c['line']}",
                         "quote": c["scope"][:60],
                         "why": f"{c['value']}{c['unit']} 에 기준일 없음"})
        for c in n2_nonprimary(raw):
            rows.append({"check": "N2", "at": f"{at}:{c['line']}",
                         "quote": c["target"],
                         "why": f"{c['host']} 는 1차 출처 목록 밖"})
        for c in n4_unbounded_superlative(raw):
            rows.append({"check": "N4", "at": f"{at}:{c['line']}",
                         "quote": c["text"][:60],
                         "why": "·".join(c["words"]) + " — 기간 한정도 1차 출처도 없음"})
    for c in n3_conflicts(posts + dicts, terms):
        rows.append({"check": "N3", "at": c["values"][0]["at"][0],
                     "quote": " vs ".join(f"{v['value']}{c['unit']}"
                                           for v in c["values"]),
                     "why": f"{c['indicator']} {c['asof']} 값 불일치 — "
                            + " / ".join(loc for v in c["values"]
                                         for loc in v["at"])})
    for c in n5_reprint(dicts, posts):
        rows.append({"check": "N5", "at": c["at"],
                     "quote": f"{c['value']}{c['unit']}",
                     "why": ", ".join(c["also_in"]) + " 와 값·단위 동일 — 전재 확인 요청"})

    counts = {n: sum(1 for r in rows if r["check"] == n)
              for n in ("N1", "N2", "N3", "N4", "N5")}
    rows.sort(key=lambda r: (counts[r["check"]], r["check"], r["at"]))

    summary = claims_summary(posts)
    n1_posts_count = sum(1 for r in rows if r["check"] == "N1" and r["at"].startswith("content/posts/"))
    n1_share = (round(n1_posts_count / summary["claims_total"], 3)
                if summary["claims_total"] else 0.0)
    print(json.dumps({"counts": counts, "total": len(rows),
                      "rows": rows[:CAP], "overflow": max(0, len(rows) - CAP),
                      "claims": summary, "n1_posts_count": n1_posts_count, "n1_share": n1_share},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
