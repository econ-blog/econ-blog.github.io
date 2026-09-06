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

    print("front_matter_issues — front matter 부재")
    bare = write(tmp, "posts", "bare.md", "본문만 있고 front matter가 없다\n")
    check("front matter 없음 감지", front_matter_issues(bare), ["front matter 없음"])

print("stale_drafts (Q4)")
from quality import stale_drafts, self_review_budget, internal_link_density  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "old-draft.md",
          '---\ntitle: "x"\ndate: 2026-07-01T00:00:00+09:00\n'
          'tags: ["금리"]\ndraft: true\n---\n\n본문\n')
    write(tmp, "posts", "new-draft.md",
          '---\ntitle: "y"\ndate: 2026-07-24T00:00:00+09:00\n'
          'tags: ["금리"]\ndraft: true\n---\n\n본문\n')
    write(tmp, "posts", "published.md", FULL_POST)
    write(tmp, "dictionary", "old-draft.md",
          '---\ntitle: "z"\ndate: 2026-07-01T00:00:00+09:00\n'
          'tags: ["용어사전"]\ndraft: true\n---\n\n본문\n')
    st = stale_drafts(root, "2026-07-25")
    # 위치는 저장소 상대경로 — posts/와 dictionary/에 같은 슬러그가 있어도
    # 소견이 어느 파일을 가리키는지 모호해지지 않는다 (AC #33).
    check("7일 이상 방치만 + 경로로 구분",
          [s["file"] for s in st],
          ["dictionary/old-draft.md", "posts/old-draft.md"])
    check("경과일 계산", st[0]["age"], 24)

print("self_review_budget (Q5)")
WS5 = "## AI 흔적 자가검토\n1. a\n2. b\n3. c\n"
b = self_review_budget(WS5)
check("항목 수", b["count"], 3)
check("예산", b["budget"], 12)
check("잔량", b["remaining"], 9)

print("internal_link_density (P2)")
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "two.md", FULL_POST.replace(
        "본문\n", "[a](/dictionary/base-rate/) [b](/dictionary/per/)\n"))
    write(tmp, "posts", "zero.md", FULL_POST)
    d = internal_link_density(root)
    per = {x["file"]: x["internal_links"] for x in d["per_post"]}
    check("링크 2건 문서", per["two.md"], 2)
    check("링크 0건 문서", per["zero.md"], 0)
    check("무링크 포스트 목록", d["zero_link_posts"], ["zero.md"])
    check("중앙값", d["median"], 1.0)

with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "posts").mkdir()
    empty = internal_link_density(Path(tmp))
    check("포스트 0건 → 중앙값 0.0", empty["median"], 0.0)
    check("포스트 0건 → 무링크 목록 빈 것", empty["zero_link_posts"], [])

print("trim_josa (Q3)")
from quality import term_candidates, trim_josa  # noqa: E402
check("조사 제거 - 가", trim_josa("기준금리가"), "기준금리")
check("조사 제거 - 를", trim_josa("기준금리를"), "기준금리")
check("조사 제거 - 에서", trim_josa("미국에서"), "미국")
check("2자 이하 보존", trim_josa("물가"), "물가")

TERMS_Q3 = {"base-rate": {"title": "기준금리", "aliases": ["정책금리"]}}
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    body = "환율 이야기. 환율 변동. 환율 전망. 기준금리 이야기."
    write(tmp, "posts", "p1.md", FULL_POST.replace("본문\n", body + "\n"))
    write(tmp, "posts", "p2.md", FULL_POST.replace("본문\n", "환율 재등장. 환율 또.\n"))
    cands = term_candidates(root, TERMS_Q3, min_posts=2, min_count=3)
    tokens = [c["token"] for c in cands]
    check("반복 토큰 후보에 포함", "환율" in tokens, True)
    check("_terms 등재 용어는 제외", "기준금리" not in tokens, True)
    hit = [c for c in cands if c["token"] == "환율"][0]
    check("등장 포스트 수", hit["posts"], 2)
    check("총 등장 수", hit["count"], 5)

    # 1개 포스트에만 있으면 탈락
    write(tmp, "posts", "p3.md", FULL_POST.replace("본문\n", "고용 고용 고용.\n"))
    tokens2 = [c["token"] for c in term_candidates(root, TERMS_Q3, 2, 3)]
    check("단일 포스트 토큰 제외", "고용" not in tokens2, True)


# --- Q7 분량 / Q8 front matter 구분자 -------------------------------------
from quality import (  # noqa: E402
    body_length_violations, body_length_of, front_matter_delimiter_issues,
    BODY_SOFT_MAX, BODY_HARD_MAX,
)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    short = "가" * 100
    soft = "가" * (BODY_SOFT_MAX + 50)
    hard = "가" * (BODY_HARD_MAX + 50)
    write(tmp, "posts", "short.md", FULL_POST.replace("본문\n", short + "\n"))
    write(tmp, "posts", "soft.md", FULL_POST.replace("본문\n", soft + "\n"))
    write(tmp, "posts", "hard.md", FULL_POST.replace("본문\n", hard + "\n"))

    hits = {h["file"].split("/")[-1]: h for h in body_length_violations(root)}
    check("목표 이내는 보고 안 함", "short.md" in hits, False)
    check("soft 초과 보고", hits["soft.md"]["level"], "soft")
    check("hard 초과 보고", hits["hard.md"]["level"], "hard")

    check("단일 파일 판정 (통과)", body_length_of(root / "posts" / "short.md"), None)
    check("단일 파일 판정 (hard)",
          body_length_of(root / "posts" / "hard.md")["level"], "hard")

    # 코드 스팬은 읽는 분량이 아니므로 세지 않는다.
    fenced = "가" * 100 + "\n\n```\n" + "x" * (BODY_HARD_MAX + 500) + "\n```\n"
    write(tmp, "posts", "fenced.md", FULL_POST.replace("본문\n", fenced))
    check("펜스 코드는 분량에서 제외",
          body_length_of(root / "posts" / "fenced.md"), None)

    # 공지는 분량 규율 대상이 아니다.
    notice = FULL_POST.replace('tags: ["금리"]', 'tags: ["공지"]')
    write(tmp, "posts", "notice.md", notice.replace("본문\n", hard + "\n"))
    check("공지는 면제", body_length_of(root / "posts" / "notice.md"), None)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "ok.md", FULL_POST)
    check("정상 파일은 위반 없음", front_matter_delimiter_issues(root), [])

    # 2026-09-06에 실제로 12파일에서 발견된 형태: 종료 구분자와 본문이 붙어 있다.
    fused = FULL_POST.replace("---\n\n본문\n", "---본문\n")
    write(tmp, "posts", "fused.md", fused)
    issues = front_matter_delimiter_issues(root)
    check("융합 구분자 적발", len(issues), 1)
    check("적발 파일명", issues[0]["file"].endswith("fused.md"), True)

    # 이 결함의 본질은 조용히 틀리는 것이다 — 예외가 아니라 ('', raw)로 돌아온다.
    from mdtext import split_front_matter as _sfm  # noqa: E402
    check("split_front_matter가 조용히 실패함을 고정",
          _sfm(fused)[0], "")

    write(tmp, "posts", "nohead.md", "제목 없이 시작하는 본문\n")
    check("시작 구분자 없음도 적발",
          any("시작" in i["issue"] for i in front_matter_delimiter_issues(root)), True)



# --- Q9 문장 리듬 / Q10 정보 이득 ----------------------------------------
from quality import (  # noqa: E402
    sentence_rhythm, rhythm_violations, information_gain,
    RHYTHM_SOFT_MIN, RHYTHM_HARD_MIN,
)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    # 모든 문장이 같은 길이 -> CV 0 -> hard
    uniform = "\n".join(["가" * 40 + "습니다." for _ in range(10)])
    write(tmp, "posts", "uniform.md", FULL_POST.replace("본문\n", uniform + "\n"))
    r = sentence_rhythm(root / "posts" / "uniform.md")
    check("균일한 글은 CV 0에 가깝다", r["cv"] < 0.05, True)
    check("균일한 글은 hard", r["level"], "hard")

    # 길이를 크게 섞으면 통과
    varied = "\n".join(
        "가" * n + "습니다." for n in (12, 90, 25, 130, 40, 15, 75, 110, 30, 60))
    write(tmp, "posts", "varied.md", FULL_POST.replace("본문\n", varied + "\n"))
    r2 = sentence_rhythm(root / "posts" / "varied.md")
    check("리듬 있는 글은 통과", r2["level"], "ok")
    check("CV가 하한 위", r2["cv"] > RHYTHM_SOFT_MIN, True)

    # 표본이 적으면 판정하지 않는다 (없는 위반을 만들지 않는다)
    write(tmp, "posts", "tiny.md", FULL_POST.replace("본문\n", "가" * 30 + "습니다.\n"))
    check("문장 5개 미만은 판정 안 함", sentence_rhythm(root / "posts" / "tiny.md"), None)

    # 표·인용·헤딩은 리듬 표본이 아니다
    tabled = uniform + "\n\n| 지표 | 값 |\n|---|---|\n| 금리 | 3.0% |\n"
    write(tmp, "posts", "tabled.md", FULL_POST.replace("본문\n", tabled + "\n"))
    check("표 행은 문장 수에 안 들어감",
          sentence_rhythm(root / "posts" / "tabled.md")["sentences"], 10)

    names = [v["file"].split("/")[-1] for v in rhythm_violations(root)]
    check("전수에 균일한 글 포함", "uniform.md" in names, True)
    check("전수에 리듬 있는 글 제외", "varied.md" in names, False)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    write(tmp, "posts", "none.md", FULL_POST)
    g = information_gain(root / "posts" / "none.md")
    check("이득 없는 글", g["has_gain"], False)

    prim = "한국은행 [기준금리](https://ecos.bok.or.kr/x) 자료입니다.\n"
    write(tmp, "posts", "prim.md", FULL_POST.replace("본문\n", prim))
    g2 = information_gain(root / "posts" / "prim.md")
    check("1차 출처 링크 인식", g2["primary_links"], 1)
    check("1차 출처면 이득 있음", g2["has_gain"], True)

    # 뉴스 링크는 1차 출처가 아니다
    news = "기사 [원문](https://www.hankyung.com/x) 입니다.\n"
    write(tmp, "posts", "news.md", FULL_POST.replace("본문\n", news))
    check("뉴스는 1차 출처 아님",
          information_gain(root / "posts" / "news.md")["has_gain"], False)

    calc = "직접 계산해 보면 월 3만원 차이가 납니다.\n"
    write(tmp, "posts", "calc.md", FULL_POST.replace("본문\n", calc))
    g3 = information_gain(root / "posts" / "calc.md")
    check("직접 계산 표지 인식", g3["derived_figures"], 1)
    check("계산만 있어도 이득 있음", g3["has_gain"], True)


print()
if FAILED:
    print(f"{len(FAILED)}건 실패:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("전부 통과")

