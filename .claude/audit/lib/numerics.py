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

from mdtext import MD_LINK, mask_code_spans, split_front_matter  # noqa: E402

# AC #54 — 단위는 닫힌 목록. 긴 것을 먼저 둬야 '%포인트'가 '%'에, '배럴'이
# '배'에 먹히지 않는다. 정규식 대안(|)은 왼쪽부터 시도하기 때문이다.
UNITS = ("%포인트", "%p", "%", "원", "달러", "배럴", "배", "bp")
NUMBER = r"-?\d[\d,]*(?:\.\d+)?"
# 숫자와 단위 사이에 만·억이 끼면(400만 배럴) 아예 매치되지 않는다. 이것은 의도한
# 손실이다 — 만을 무시하고 400으로 읽으면 N3·N5가 '400만 배럴'과 '400 배럴'을
# 같은 값으로 대조해 없는 모순을 만든다. 뽑지 않는 쪽이 틀리게 뽑는 쪽보다 낫다.
CLAIM = re.compile(rf"({NUMBER})\s*({'|'.join(re.escape(u) for u in UNITS)})")

# 연·월 또는 연·월·일. 한글형과 ISO형이 실제로 공존한다(실측).
ASOF = re.compile(r"20\d{2}년\s*\d{1,2}월(?:\s*\d{1,2}일)?|20\d{2}-\d{2}(?:-\d{2})?")

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


if __name__ == "__main__":
    pass

