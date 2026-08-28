"""격주 점검의 장기 기억 (`.claude/audit/health-memory.md`) 접근 도구.

## 왜 파일이 아니라 도구를 거치나

점검 세션은 2주에 한 번, 매번 **빈 맥락으로** 시작한다. 지난 회차의 자기 자신이
무엇을 왜 했는지 아는 유일한 경로가 이 파일이고, 그 파일은 회차마다 길어진다.
통째로 Read 하면 언젠가 맥락을 다 먹거나 잘려서 읽히고, 잘렸다는 사실은 티가 나지
않는다 — 그냥 "지난번에 아무 일도 없었나 보다"가 된다.

그래서 읽기는 **회차 단위**로 자른다. 쓰기는 형식을 강제한다. 형식이 무너지면
자르는 것도 무너지므로 둘은 같은 문제다.

## 형식 계약

회차 하나는 `## YYYY-MM-DD · 회차 N` 헤딩으로 시작한다. 그 위(첫 회차 헤딩 이전)는
파일을 읽는 법을 적은 머리말이며 회차가 아니다 — `tail`은 머리말을 항상 함께 낸다.
"""

import argparse
import os
import re
import sys
from datetime import datetime

MEMORY_PATH = ".claude/audit/health-memory.md"

# `## 2026-09-10 · 회차 3` — 가운뎃점 앞뒤 공백과 회차 번호는 필수다.
ENTRY_HEADER = re.compile(r'^## (\d{4}-\d{2}-\d{2}) · 회차 (\d+)\s*$')

# 이 줄 수를 넘으면 압축할 때가 됐다고 알린다. 강제로 자르지는 않는다 —
# 무엇을 버릴지는 판단이고, 스크립트가 오래된 회차를 소리 없이 지우면
# 그것이야말로 이 파일이 막으려는 상황이다.
COMPACT_THRESHOLD_LINES = 1200


def read(path: str = MEMORY_PATH) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def split_entries(text: str) -> tuple:
    """(머리말, [(날짜, 회차, 본문), ...]) 로 가른다.

    본문에는 헤딩 줄이 포함된다 — 그대로 다시 이어 붙이면 원본이 된다.
    """
    lines = text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if ENTRY_HEADER.match(ln.rstrip("\n"))]
    if not starts:
        return text, []
    preamble = "".join(lines[:starts[0]])
    entries = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        m = ENTRY_HEADER.match(lines[i].rstrip("\n"))
        entries.append((m.group(1), int(m.group(2)), "".join(lines[i:end])))
    return preamble, entries


def tail(text: str, count: int) -> str:
    """머리말 + 마지막 `count` 회차. 회차가 없으면 머리말만."""
    preamble, entries = split_entries(text)
    if not entries:
        return preamble
    kept = entries[-count:] if count > 0 else entries
    return preamble + "".join(e[2] for e in kept)


def next_round(text: str) -> int:
    _pre, entries = split_entries(text)
    return (max(e[1] for e in entries) + 1) if entries else 1


def validate_entry(body: str) -> str:
    """새 회차 본문을 검사한다. 문제가 있으면 사유 문자열, 없으면 빈 문자열."""
    first = body.lstrip("\n").splitlines()[0] if body.strip() else ""
    m = ENTRY_HEADER.match(first)
    if not m:
        return (f"첫 줄이 회차 헤딩이 아니다: {first[:60]!r}\n"
                "형식: '## YYYY-MM-DD · 회차 N'")
    try:
        datetime.strptime(m.group(1), "%Y-%m-%d")
    except ValueError:
        return f"날짜를 읽을 수 없다: {m.group(1)!r}"
    return ""


def append(text: str, body: str) -> str:
    """회차 하나를 덧붙인다. 같은 날짜의 회차가 이미 있으면 그것을 대체한다 —
    같은 날 두 번 돌았다는 뜻이고, 그건 회차 둘이 아니라 재실행이다."""
    body = body.strip("\n") + "\n"
    m = ENTRY_HEADER.match(body.splitlines()[0])
    date = m.group(1)
    preamble, entries = split_entries(text)
    entries = [e for e in entries if e[0] != date]
    entries.append((date, int(m.group(2)), body))
    entries.sort(key=lambda e: e[0])
    joined = "\n".join(e[2].strip("\n") for e in entries)
    head = preamble.rstrip("\n")
    return (head + "\n\n" + joined + "\n") if head else (joined + "\n")


def write(text: str, path: str = MEMORY_PATH):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def stats(text: str) -> dict:
    _pre, entries = split_entries(text)
    lines = len(text.splitlines())
    return {
        "entries": len(entries),
        "lines": lines,
        "oldest": entries[0][0] if entries else None,
        "newest": entries[-1][0] if entries else None,
        "next_round": next_round(text),
        "compact_due": lines > COMPACT_THRESHOLD_LINES,
        "compact_threshold": COMPACT_THRESHOLD_LINES,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="격주 점검 장기 기억")
    ap.add_argument("action", choices=["tail", "append", "stats"])
    ap.add_argument("--path", default=MEMORY_PATH)
    ap.add_argument("--entries", type=int, default=3,
                    help="tail: 최근 몇 회차를 낼지 (0이면 전부)")
    a = ap.parse_args(argv)

    text = read(a.path)

    if a.action == "tail":
        sys.stdout.write(tail(text, a.entries))
        return 0

    if a.action == "stats":
        import json
        print(json.dumps(stats(text), ensure_ascii=False))
        return 0

    body = sys.stdin.read()
    problem = validate_entry(body)
    if problem:
        print(f"회차를 덧붙이지 않았다 — {problem}", file=sys.stderr)
        return 1
    write(append(text, body), a.path)
    import json
    print(json.dumps(stats(read(a.path)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
