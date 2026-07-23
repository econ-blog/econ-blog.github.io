"""참조 코퍼스 수집기 — 네이버 블로그 경제 해설 게시물.

수집물은 reference-corpus/ 로컬에만 저장되며 .gitignore로 커밋을 막는다.
타인 저작물이므로 발행·재배포하지 않는다.

사용:
    python3 collect_corpus.py "검색어1" "검색어2" ...
    python3 collect_corpus.py --manifest      # 현재 수집 현황만 출력
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from extract_features import f_formal_ending_ratio, normalize, sentences  # noqa: E402

try:
    from bs4 import BeautifulSoup
    from curl_cffi import requests
except ImportError:
    sys.exit("pip install -U 'curl_cffi>=0.15.0' beautifulsoup4")

HERE = Path(__file__).parent
CORPUS = HERE / "reference-corpus"
MANIFEST = HERE / "corpus-manifest.json"

DATE_RANGE = "from20180101to20221231"   # 스펙: 2023-01-01 이전
# 검색의 nso 날짜 필터는 샌다(2026년 글이 섞여 나오는 것을 실측). 페이지에서
# 발행일을 직접 읽어 재확인한다 — 2023년 이후 글은 LLM으로 썼을 가능성이 높고,
# 그러면 측정 대상으로 기준선을 만드는 꼴이 된다.
MAX_YEAR, MAX_MONTH = 2022, 12
DATE_SELECTORS = ".se_publishDate, .blog_date, .date, .se_date"
MIN_CHARS = 800                          # 스펙: 본문 ≥800자
MIN_FORMAL = 0.60                        # 스펙: 존댓말 종결어미 ≥60%
MAX_LIST_RATIO = 0.30                    # 스펙: 리스트 요약형 배제

AD_MARKERS = ["협찬", "체험단", "원고료", "소정의 수수료", "광고 포함",
              "제품을 제공받", "업체로부터"]
BODY_SELECTORS = ["div.se-main-container", "div#postViewArea", "div.post_ct"]


def _session(impersonate, referer):
    s = requests.Session(impersonate=impersonate)
    s.headers.update({"Accept-Language": "ko-KR,ko;q=0.9", "Referer": referer})
    return s


def search(query, pages=3):
    """네이버 블로그 탭에서 날짜 필터를 걸어 blog URL을 모은다."""
    s = _session("chrome124", "https://www.google.com/")
    s.get("https://www.naver.com/", timeout=10)
    s.headers["Referer"] = "https://www.naver.com/"
    nso = quote(f"so:r,p:{DATE_RANGE}")
    found = []
    for page in range(pages):
        start = page * 30 + 1
        url = (f"https://search.naver.com/search.naver?where=post"
               f"&query={quote(query)}&nso={nso}&start={start}")
        try:
            r = s.get(url, timeout=20)
        except Exception as e:
            print(f"    검색 실패 p{page}: {e}", file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"    검색 status {r.status_code} p{page}", file=sys.stderr)
            break
        found += re.findall(r"https://blog\.naver\.com/([A-Za-z0-9_-]+)/(\d+)", r.text)
        time.sleep(0.7)
    return sorted(set(found))


def parse_date(soup):
    """발행일을 (년, 월)로 반환. 못 읽으면 None."""
    node = soup.select_one(DATE_SELECTORS)
    if not node:
        return None
    m = re.search(r"(\d{4})\.\s*(\d{1,2})\.", node.get_text(strip=True))
    return (int(m.group(1)), int(m.group(2))) if m else None


def fetch_body(blog_id, log_no):
    """모바일 PostView에서 본문 텍스트를 뽑는다. 발행일 검증 포함."""
    s = _session("safari_ios", "https://m.naver.com/")
    url = (f"https://m.blog.naver.com/PostView.naver"
           f"?blogId={blog_id}&logNo={log_no}")
    r = s.get(url, timeout=20)
    if r.status_code != 200:
        return None, f"http_{r.status_code}", None

    soup = BeautifulSoup(r.text, "html.parser")
    ymd = parse_date(soup)
    if ymd is None:
        return None, "no_date", None           # 날짜 미확인 건은 채택하지 않는다
    if (ymd[0], ymd[1]) > (MAX_YEAR, MAX_MONTH):
        return None, f"too_recent_{ymd[0]}", ymd

    for sel in BODY_SELECTORS:
        node = soup.select_one(sel)
        if node:
            text = re.sub(r"[ \t]+", " ", node.get_text("\n"))
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return text, None, ymd
    return None, "no_body_selector", ymd


def screen(text):
    """스펙의 자동 필터. 통과하면 None, 아니면 탈락 사유."""
    if len(text) < MIN_CHARS:
        return f"too_short_{len(text)}"
    for m in AD_MARKERS:
        if m in text:
            return f"ad_marker_{m}"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    listy = sum(1 for l in lines if re.match(r"^([-*•▶▷◆■□○]|\d+[.)])\s*", l))
    if lines and listy / len(lines) > MAX_LIST_RATIO:
        return f"listy_{listy / len(lines):.2f}"
    norm = normalize(text)
    sents = sentences(norm)
    if len(sents) < 10:
        return f"too_few_sentences_{len(sents)}"
    formal = f_formal_ending_ratio(norm, None, sents)
    if formal < MIN_FORMAL:
        return f"register_{formal:.2f}"
    return None


def load_manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def collect(queries):
    CORPUS.mkdir(exist_ok=True)
    manifest = load_manifest()
    kept = sum(1 for v in manifest.values() if v["status"] == "kept")

    for q in queries:
        print(f"\n[검색] {q}")
        hits = search(q)
        print(f"  후보 {len(hits)}건")
        for blog_id, log_no in hits:
            key = f"{blog_id}_{log_no}"
            if key in manifest:
                continue
            try:
                text, err, ymd = fetch_body(blog_id, log_no)
            except Exception as e:
                manifest[key] = {"status": "rejected", "reason": f"fetch_error_{type(e).__name__}", "query": q}
                continue
            if err:
                manifest[key] = {"status": "rejected", "reason": err, "query": q}
                continue
            reason = screen(text)
            if reason:
                manifest[key] = {"status": "rejected", "reason": reason, "query": q}
            else:
                (CORPUS / f"{key}.md").write_text(text, encoding="utf-8")
                manifest[key] = {"status": "kept", "chars": len(text), "query": q,
                                 "date": f"{ymd[0]}-{ymd[1]:02d}",
                                 "url": f"https://blog.naver.com/{blog_id}/{log_no}"}
                kept += 1
                print(f"  + {key} ({len(text)}자)  누적 {kept}")
            save_manifest(manifest)
            time.sleep(0.5)
    return manifest


def report(manifest):
    kept = [k for k, v in manifest.items() if v["status"] == "kept"]
    rej = [v["reason"] for v in manifest.values() if v["status"] == "rejected"]
    print(f"\n{'=' * 46}\n채택 {len(kept)}건 / 검토 {len(manifest)}건")
    if rej:
        from collections import Counter
        print("탈락 사유:")
        for r, n in Counter(re.sub(r"_[\d.]+$", "", x) for x in rej).most_common():
            print(f"  {n:4}  {r}")
    print(f"\n스펙 하한 30건 {'충족' if len(kept) >= 30 else '미달'} / 목표 50건")


if __name__ == "__main__":
    argv = sys.argv[1:]
    # 병렬 수집 시 에이전트마다 별도 매니페스트를 쓰게 해 덮어쓰기를 막는다.
    # 본문 파일은 blogId_logNo 키라 겹쳐도 동일 내용이므로 충돌이 무해하다.
    if "--tag" in argv:
        i = argv.index("--tag")
        MANIFEST = HERE / f"corpus-manifest-{argv[i + 1]}.json"
        argv = argv[:i] + argv[i + 2:]

    args = [a for a in argv if not a.startswith("--")]
    if "--manifest" in sys.argv:
        report(load_manifest())
    elif args:
        report(collect(args))
    else:
        sys.exit(__doc__)
