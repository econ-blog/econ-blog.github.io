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

# 규칙 A — 백필 부분문자열 가드 (더 긴 낱말의 일부는 버린다)
LOAN_TERMS = {"loan": {"title": "대출", "aliases": []}}
print("부분문자열 가드")
with tempfile.TemporaryDirectory() as tmp:
    # "대출금리"·"가계대출"의 일부로만 등장 → 후보 0
    inner = write(tmp, "h.md", "오늘 대출금리와 가계대출 동향입니다.")
    check("더 긴 낱말 내부 → 후보 0", find_candidates([inner], LOAN_TERMS), [])

    # 조사가 붙은 정상 등장은 낱말 경계로 허용 (예: "대출은")
    particle = write(tmp, "i.md", "대출은 늘었다.")
    cands = find_candidates([particle], LOAN_TERMS)
    check("조사 결합은 낱말 경계 → backfill 1건", len(cands), 1)
    check("조사 결합 slug", cands[0]["slug"] if cands else None, "loan")

    # 앞은 낱말 경계(공백)이나 뒤가 다른 한글로 이어지면 여전히 내부로 간주
    mixed = write(tmp, "j.md", "대출금리가 올랐다.")
    check("앞만 경계이고 뒤가 이어지면 여전히 내부", find_candidates([mixed], LOAN_TERMS), [])

    # 기준금리 뒤에 조사 "는"이 붙는 정상 케이스는 계속 backfill로 잡혀야 한다
    kikeum = write(tmp, "k.md", "기준금리는 동결됐다.")
    cands2 = find_candidates([kikeum], TERMS)
    check("기준금리+조사 → backfill 유지", [c["kind"] for c in cands2], ["backfill"])

# 영숫자 표면(LNG)도 같은 낱말 경계 판정을 받는다
LNG_TERMS = {"lng": {"title": "LNG", "aliases": []}}
with tempfile.TemporaryDirectory() as tmp:
    # "LNG" 뒤에 영문자가 바로 이어지면(예: "LNGX") 낱말 내부로 버린다
    glued = write(tmp, "l.md", "회사명은 LNGX입니다.")
    check("영숫자 표면도 뒤 결합이면 후보 0", find_candidates([glued], LNG_TERMS), [])

    plain_lng = write(tmp, "m.md", "오늘 LNG 가격이 올랐다.")
    check("영숫자 표면 정상 등장 → backfill",
          find_candidates([plain_lng], LNG_TERMS)[0]["kind"], "backfill")

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
