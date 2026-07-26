"""골든 테스트 — mdtext가 조용히 바뀌는 것을 막는다.

.venv/bin/python .claude/audit/lib/test_mdtext.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdtext import split_front_matter, strip_code_spans  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("split_front_matter")
FM = '---\ntitle: "x"\ndraft: false\n---\n\n본문입니다.\n'
fm, body = split_front_matter(FM)
check("front matter 분리", "title:" in fm and "본문" not in fm, True)
check("본문 분리", body.strip(), "본문입니다.")
check("front matter 없으면 빈 문자열", split_front_matter("본문만")[0], "")
check("front matter 없으면 원문 반환", split_front_matter("본문만")[1], "본문만")

print("strip_code_spans")
check("인라인 코드 제거", strip_code_spans("앞 `code` 뒤").strip(), "앞  뒤")
check(
    "펜스 코드블록 제거",
    "print" not in strip_code_spans("전\n```\nprint(1)\n```\n후"),
    True,
)
check(
    "코드 안 가짜 링크가 추출되지 않도록 제거",
    "]" not in strip_code_spans("`[가짜](/x/)`"),
    True,
)
check(
    "펜스 먼저 처리 — 펜스 내부 단일 백틱이 경계를 깨지 않음",
    "secret" not in strip_code_spans("```\na ` b secret\n```"),
    True,
)

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
