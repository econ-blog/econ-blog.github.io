"""골든 테스트 — quality (Q1·Q3·Q4·Q5·P2).

.venv/bin/python .claude/audit/lib/test_quality.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality import front_matter_issues  # noqa: E402

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


DESC = "이것은 오십 자 이상 백육십 자 이하의 적정 길이 설명문입니다. 경제 뉴스를 쉽게 풀어 설명하는 문장을 담고 있습니다."

FULL_POST = (
    "---\n"
    'title: "제목"\n'
    "date: 2026-07-21T19:30:00+09:00\n"
    f'description: "{DESC}"\n'
    'tags: ["금리"]\n'
    "draft: false\n"
    'source_url: "https://a.com/x"\n'
    "---\n\n본문\n"
)


def write(tmp, sub, name, text):
    d = Path(tmp) / sub
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


print("front_matter_issues — 포스트")
with tempfile.TemporaryDirectory() as tmp:
    ok_post = write(tmp, "posts", "a.md", FULL_POST)
    check("완비 → 결함 0", front_matter_issues(ok_post), [])

    no_src = write(tmp, "posts", "b.md", FULL_POST.replace(
        'source_url: "https://a.com/x"\n', ""))
    check("source_url 누락 감지", any("source_url" in i for i in front_matter_issues(no_src)), True)

    short = write(tmp, "posts", "c.md", FULL_POST.replace(DESC, "짧은 설명"))
    check("description 짧음 감지", any("description" in i for i in front_matter_issues(short)), True)

    long_desc = write(tmp, "posts", "d.md", FULL_POST.replace(DESC, "가" * 200))
    check("description 김 감지", any("description" in i for i in front_matter_issues(long_desc)), True)

    print("front_matter_issues — 공지 예외")
    notice = write(tmp, "posts", "welcome.md",
                   '---\ntitle: "공지"\ndate: 2026-07-18T09:00:00+09:00\n'
                   'tags: ["공지"]\ndraft: false\n---\n\n본문\n')
    check("공지는 source_url·description 면제", front_matter_issues(notice), [])

    print("front_matter_issues — 사전")
    dict_ok = write(tmp, "dictionary", "cofix.md",
                    "---\n"
                    'title: "코픽스"\n'
                    "date: 2026-07-21T19:30:00+09:00\n"
                    f'description: "{DESC}"\n'
                    'tags: ["용어사전"]\n'
                    "draft: false\n---\n\n본문\n")
    check("사전은 source_url 면제", front_matter_issues(dict_ok), [])

print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")
