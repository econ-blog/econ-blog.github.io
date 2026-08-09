"""③ 색인 건전성 — I1·I2·I3·I5·I7 판정 + 경보 단계. (SEED AC #26–29)

GSC 노출이 0이라는 사실 하나만으로는 고장인지 정상인지 구분되지 않는다.
사이트 연령으로 경보 수위를 나눈다 — 신생 도메인은 색인까지 통상 수 주가
걸리므로 이진 경보는 첫 달 내내 거짓 경보만 낸다.

I4·I6은 네트워크가 필요해 scripts/fetch_gsc.py가 조회한다(AC #23). 이 모듈은
그 결과를 받아 판정만 한다.

  .venv/bin/python .claude/audit/lib/indexation.py
"""
import re
from pathlib import Path

TIER_OBSERVE = 14
TIER_FINDING = 42

LOC_TAG = re.compile(r"<loc>")
BASEURL = re.compile(r'^\s*baseURL\s*=\s*["\'](?P<url>[^"\']+)', re.M)
HOST_FROM_URL = re.compile(r"^(?:https?://)?(?P<host>[^/:]+)")
REMOTE_HOST = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\s.]+)")


def escalation_tier(site_age: int) -> str:
    """D < 14 정상(노출 0을 보고하지 않음) / 14~41 관찰(표만) / 42+ 소견. (AC #27)"""
    if site_age < TIER_OBSERVE:
        return "정상"
    if site_age < TIER_FINDING:
        return "관찰"
    return "소견"


def check_sitemap(public_root: Path, published_count: int) -> dict:
    """I1 — <loc> 태그 개수를 센다. Hugo는 sitemap을 한 줄로 minify하므로
    줄 수를 세면 항상 1이 나온다. (AC #28 I1)"""
    path = public_root / "sitemap.xml"
    if not path.is_file():
        return {"exists": False, "loc_count": 0,
                "published_count": published_count, "met": False}
    count = len(LOC_TAG.findall(path.read_text(encoding="utf-8")))
    return {"exists": True, "loc_count": count,
            "published_count": published_count, "met": count >= published_count}


def check_robots(public_root: Path) -> dict:
    """I2 — 빌드 산출물을 본다. layouts/robots.txt는 템플릿이다. (AC #28 I2)"""
    path = public_root / "robots.txt"
    if not path.is_file():
        return {"exists": False, "blanket_disallow": False,
                "has_sitemap_line": False, "met": False}
    text = path.read_text(encoding="utf-8")
    blanket = bool(re.search(r"^\s*Disallow:\s*/\s*$", text, re.M | re.I))
    has_sitemap = bool(re.search(r"^\s*Sitemap:\s*\S+", text, re.M | re.I))
    return {"exists": True, "blanket_disallow": blanket,
            "has_sitemap_line": has_sitemap,
            "met": (not blanket) and has_sitemap}


def _host(value: str | None) -> str | None:
    if not value:
        return None
    m = HOST_FROM_URL.match(value.replace("sc-domain:", ""))
    return m.group("host") if m else None


def check_baseurl(hugo_toml: str, git_remote: str,
                  gsc_site_url: str | None) -> dict:
    """I3 — baseURL 3자 정합. 하나라도 다르면 즉시 소견: 모든 canonical·sitemap
    URL이 틀어져 색인이 원천 차단된다. (AC #28 I3)"""
    bm = BASEURL.search(hugo_toml)
    hugo_host = _host(bm.group("url")) if bm else None
    rm = REMOTE_HOST.search(git_remote or "")
    remote_host = rm.group("repo").lower() if rm else None
    if remote_host and not remote_host.endswith("github.io"):
        remote_host = f"{rm.group('owner').lower()}.github.io"
    gsc_host = _host(gsc_site_url)

    hosts = [h for h in (hugo_host, remote_host, gsc_host) if h]
    return {"hugo_host": hugo_host, "remote_host": remote_host,
            "gsc_host": gsc_host,
            "met": len(set(hosts)) == 1 and len(hosts) >= 2,
            "immediate": True}


def check_noindex(public_root: Path) -> dict:
    """I5 — 빌드 산출물의 noindex 유출. (AC #28 I5)"""
    hits = []
    if public_root.is_dir():
        for path in sorted(public_root.rglob("*.html")):
            if "noindex" in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(path))
    return {"files": hits, "met": not hits}


def check_property_type(gsc_site_url: str | None, hugo_host: str) -> dict:
    """I7 — URL 접두어인데 프로토콜·호스트가 실제 사이트와 다르면 데이터는
    영원히 0이다. (AC #28 I7)"""
    if not gsc_site_url:
        return {"type": None, "host_matches": None, "met": None}
    kind = "domain" if gsc_site_url.startswith("sc-domain:") else "url-prefix"
    matches = _host(gsc_site_url) == hugo_host
    return {"type": kind, "host_matches": matches, "met": matches}


def sitemap_submission(sitemaps: list[dict] | None) -> dict:
    """I4 — 미제출이면 단계와 무관하게 즉시 소견. (AC #28 I4)

    lastDownloaded와 lastSubmitted는 아직 읽히지 않은 sitemap의 응답에 아예 없을 수 있다(2026-07-26 실측).
    없는 것이 곧 실패는 아니다 — 제출은 됐다.
    """
    if sitemaps is None:
        return {"submitted": False, "pending": None, "last_downloaded": None,
                "last_submitted": None, "errors": None, "met": None, "immediate": True}
    if not sitemaps:
        return {"submitted": False, "pending": None, "last_downloaded": None,
                "last_submitted": None, "errors": None, "met": False, "immediate": True}
    first = sitemaps[0]
    return {"submitted": True, "pending": first.get("isPending"),
            "last_downloaded": first.get("lastDownloaded"),
            "last_submitted": first.get("lastSubmitted"),
            "errors": first.get("errors"), "met": True, "immediate": True}


def main() -> None:
    """네트워크 없는 점검(I1·I2·I3·I5)만 JSON으로. I4·I6·I7은 스테이지가
    fetch_gsc.py 결과를 넘겨 판정한다."""
    import json
    import subprocess
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from corpus import published, site_age  # noqa: E402
    from kstdate import kst_today  # noqa: E402

    content, public = Path("content"), Path("public")
    posts = published(content)
    age = site_age(content, kst_today())
    remote = subprocess.run(["git", "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    hugo_toml = Path("hugo.toml").read_text(encoding="utf-8")
    print(json.dumps({
        "site_age": age,
        "tier": escalation_tier(age),
        "published_count": len(posts),
        "I1_sitemap": check_sitemap(public, len(posts)),
        "I2_robots": check_robots(public),
        "I3_baseurl": check_baseurl(hugo_toml, remote, None),
        "I5_noindex": check_noindex(public),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
