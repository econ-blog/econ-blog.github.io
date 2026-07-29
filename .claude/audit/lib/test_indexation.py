"""골든 테스트 — indexation(③). Hugo minify의 함정을 코드로 고정한다.

.venv/bin/python .claude/audit/lib/test_indexation.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indexation import (  # noqa: E402
    TIER_FINDING, TIER_OBSERVE, check_baseurl, check_noindex, check_property_type,
    check_robots, check_sitemap, escalation_tier, sitemap_submission,
)

FAILED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILED.append(f"{label}: got {got!r}, want {want!r}")
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")


print("escalation_tier")
check("경계 상수", (TIER_OBSERVE, TIER_FINDING), (14, 42))
check("D=0 정상", escalation_tier(0), "정상")
check("D=13 정상", escalation_tier(13), "정상")
check("D=14 관찰", escalation_tier(14), "관찰")
check("D=41 관찰", escalation_tier(41), "관찰")
check("D=42 소견", escalation_tier(42), "소견")
check("D=200 소견", escalation_tier(200), "소견")

print("check_sitemap (minify 함정)")
# Hugo는 sitemap을 한 줄로 minify한다 — 줄 수를 세면 항상 1이다.
ONE_LINE = ('<?xml version="1.0" encoding="utf-8" standalone="yes"?><urlset>'
            "<url><loc>https://x/</loc></url><url><loc>https://x/a/</loc></url>"
            "<url><loc>https://x/b/</loc></url></urlset>")
with tempfile.TemporaryDirectory() as tmp:
    pub = Path(tmp)
    (pub / "sitemap.xml").write_text(ONE_LINE, encoding="utf-8")
    r = check_sitemap(pub, 3)
    check("존재", r["exists"], True)
    check("loc 개수를 센다", r["loc_count"], 3)
    check("줄 수가 아니다", r["loc_count"] != ONE_LINE.count("\n") + 1, True)
    check("발행글 수 이상이면 통과", r["met"], True)
    check("발행글이 더 많으면 미달", check_sitemap(pub, 5)["met"], False)
    check("부재", check_sitemap(Path(tmp) / "nope", 3)["exists"], False)
    check("부재는 미달", check_sitemap(Path(tmp) / "nope", 3)["met"], False)

print("check_robots")
with tempfile.TemporaryDirectory() as tmp:
    pub = Path(tmp)
    (pub / "robots.txt").write_text(
        "User-agent: *\nDisallow:\nSitemap: https://x/sitemap.xml\n", encoding="utf-8")
    r = check_robots(pub)
    check("전면 차단 아님", r["blanket_disallow"], False)
    check("Sitemap 줄 있음", r["has_sitemap_line"], True)
    check("통과", r["met"], True)
    (pub / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    r2 = check_robots(pub)
    check("전면 차단 감지", r2["blanket_disallow"], True)
    check("Sitemap 줄 없음", r2["has_sitemap_line"], False)
    check("미달", r2["met"], False)

print("check_baseurl")
r = check_baseurl('baseURL = "https://econ-blog.github.io/"\n',
                  "git@github.com:econ-blog/econ-blog.github.io.git",
                  "https://econ-blog.github.io/")
check("hugo host", r["hugo_host"], "econ-blog.github.io")
check("remote host", r["remote_host"], "econ-blog.github.io")
check("gsc host", r["gsc_host"], "econ-blog.github.io")
check("3자 정합", r["met"], True)
check("즉시 소견 플래그", r["immediate"], True)
bad = check_baseurl('baseURL = "https://other.example/"\n',
                    "git@github.com:econ-blog/econ-blog.github.io.git",
                    "https://econ-blog.github.io/")
check("불일치 감지", bad["met"], False)
none_gsc = check_baseurl('baseURL = "https://econ-blog.github.io/"\n',
                         "https://github.com/econ-blog/econ-blog.github.io",
                         None)
check("https remote도 파싱", none_gsc["remote_host"], "econ-blog.github.io")
check("GSC 미조회는 2자만 비교", none_gsc["met"], True)

print("check_noindex")
with tempfile.TemporaryDirectory() as tmp:
    pub = Path(tmp)
    (pub / "posts").mkdir()
    (pub / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    check("유출 없음", check_noindex(pub)["met"], True)
    (pub / "posts" / "index.html").write_text(
        '<meta name=robots content=noindex>', encoding="utf-8")
    r = check_noindex(pub)
    check("유출 감지", r["met"], False)
    check("파일 목록", [Path(f).name for f in r["files"]], ["index.html"])

print("check_property_type")
check("URL 접두어", check_property_type("https://econ-blog.github.io/",
                                     "econ-blog.github.io")["type"], "url-prefix")
check("도메인 속성", check_property_type("sc-domain:econ-blog.github.io",
                                    "econ-blog.github.io")["type"], "domain")
check("호스트 일치", check_property_type("https://econ-blog.github.io/",
                                    "econ-blog.github.io")["host_matches"], True)
check("호스트 불일치", check_property_type("https://other.example/",
                                     "econ-blog.github.io")["met"], False)
check("미조회", check_property_type(None, "econ-blog.github.io")["type"], None)

print("sitemap_submission")
PENDING = [{"path": "https://x/sitemap.xml", "lastSubmitted": "2026-07-19T05:43:00Z",
            "lastDownloaded": None, "isPending": True, "warnings": "0", "errors": "0"}]
r = sitemap_submission(PENDING)
check("제출됨", r["submitted"], True)
check("pending", r["pending"], True)
check("미read는 None", r["last_downloaded"], None)
check("lastSubmitted 전달", r["last_submitted"], "2026-07-19T05:43:00Z")
check("제출됐으면 통과", r["met"], True)
check("즉시 소견 플래그", r["immediate"], True)
# lastSubmitted가 없는 경우 (아직 읽히지 않은 sitemap)
UNREAD = [{"path": "https://x/sitemap.xml", "isPending": True, "warnings": "0", "errors": "0"}]
r2 = sitemap_submission(UNREAD)
check("미read는 last_submitted None", r2["last_submitted"], None)
check("미read여도 제출됨", r2["submitted"], True)
check("미read여도 통과", r2["met"], True)
check("미제출은 실패", sitemap_submission([])["met"], False)
check("미조회는 실패로 보지 않음", sitemap_submission(None)["submitted"], False)
check("미조회 met None", sitemap_submission(None)["met"], None)
ERRORED = [dict(PENDING[0], errors="3")]
check("오류 수 전달", sitemap_submission(ERRORED)["errors"], "3")

print()
if FAILED:
    print("실패:")
    for f in FAILED:
        print(" -", f)
    sys.exit(1)
print("전부 통과")
