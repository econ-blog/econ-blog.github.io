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


if __name__ == "__main__":
    pass

