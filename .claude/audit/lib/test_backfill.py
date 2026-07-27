"""골든 테스트 — backfill. AC #65(1링크 원칙)·#66(선행 언급)이 핵심.

.venv/bin/python .claude/audit/lib/test_backfill.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backfill import find_candidates  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


TERMS = {"base-rate": {"title": "기준금리", "aliases": ["정책금리"]}}


def write(tmp, name, body):
    p = Path(tmp) / name
    p.write_text("---\ntitle: x\n---\n" + body, encoding="utf-8")
    return p


print("find_candidates")
with tempfile.TemporaryDirectory() as tmp:
    # 이미 링크된 문서 → 후보 0 (AC #65)
    linked = write(tmp, "a.md", "[기준금리](/dictionary/base-rate/)를 올렸다.")
    check("이미 링크 → 후보 0", find_candidates([linked], TERMS), [])

    # 미연결 등장 + 기존 링크 없음 → backfill 1건
    plain = write(tmp, "b.md", "오늘 기준금리 이야기.")
    cands = find_candidates([plain], TERMS)
    check("미연결 → backfill 1건", len(cands), 1)
    check("backfill 종류", cands[0]["kind"], "backfill")
    check("slug 정확", cands[0]["slug"], "base-rate")

    # 선행 미연결 + 이후 링크 → precedence (소견만, AC #66)
    prec = write(tmp, "c.md", "먼저 기준금리 언급.\n\n뒤에 [기준금리](/dictionary/base-rate/).")
    pc = find_candidates([prec], TERMS)
    check("선행 언급 → precedence", [c["kind"] for c in pc], ["precedence"])

    # alias도 인식
    al = write(tmp, "d.md", "정책금리를 논한다.")
    check("alias 미연결 → backfill", find_candidates([al], TERMS)[0]["slug"], "base-rate")

    # 코드스팬 안 등장은 무시 (AC #5·#64)
    code = write(tmp, "e.md", "코드 `기준금리` 예시.")
    check("코드스팬 안은 후보 아님", find_candidates([code], TERMS), [])

    # 다행 펜스 코드블록 안 등장은 무시 (AC #64)
    multiline_code = write(tmp, "f.md", "```python\nprint(\"기준금리\")\n```")
    check("다행 펜스 코드블록 안은 후보 아님", find_candidates([multiline_code], TERMS), [])

    # 앵커가 포함된 링크도 인식
    anchor_linked = write(tmp, "g.md", "[기준금리](/dictionary/base-rate/#section)를 올렸다.")
    check("앵커 포함 링크 → 후보 0", find_candidates([anchor_linked], TERMS), [])

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
