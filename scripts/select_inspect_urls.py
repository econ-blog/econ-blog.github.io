import os
import glob
import re
import sys
from typing import List, Dict, Any


def _root(base_url: str = None) -> str:
    if not base_url:
        base_url = os.environ.get("GSC_SITE_URL") or "https://econ-blog.github.io"
    if base_url.startswith("sc-domain:"):
        base_url = "https://" + base_url.removeprefix("sc-domain:")
    return base_url.rstrip("/")


def _published(md_dir: str, url_prefix: str, root: str) -> List[tuple]:
    """(발행일, URL) 목록. draft·welcome·`_` 시작 파일은 뺀다."""
    out = []
    if not os.path.isdir(md_dir):
        return out
    for fpath in sorted(glob.glob(os.path.join(md_dir, "*.md"))):
        name = os.path.basename(fpath)
        if name.startswith("_") or name == "welcome.md":
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            meta = parse_post_metadata(f.read())
        if meta["draft"] or not meta["date"]:
            continue
        out.append((meta["date"], f"{root}/{url_prefix}/{name.removesuffix('.md')}/"))
    return out


def select_all_urls(content_dir: str = "content", base_url: str = None) -> List[str]:
    """I6 전수 목록. **표본이 아니다** — '아직 색인 안 된 URL'의 완전한 목록을 만든다.

    순서가 곧 우선순위다. `fetch_gsc.py`가 cap 에서 자르므로 앞에 둔 것이 살아남는다:
      1. 홈 — 크롤 진입점
      2. 섹션 목록 두 개 — 여기가 수집되면 개별 글로 퍼진다
      3. 발행 글·사전 항목을 **오래된 순으로** — 오래된 글은 색인될 시간을 이미 받았으므로
         그것마저 미색인이면 신호가 세다. 최신순으로 두면 정의상 가장 색인 안 됐을 URL만
         앞에 오고, cap 에 걸렸을 때 정보량이 가장 적은 쪽이 살아남는다.
    """
    root = _root(base_url)
    urls = [f"{root}/", f"{root}/posts/", f"{root}/dictionary/"]
    rows = _published(os.path.join(content_dir, "posts"), "posts", root)
    rows += _published(os.path.join(content_dir, "dictionary"), "dictionary", root)
    rows.sort(key=lambda x: x[0])
    for _, url in rows:
        if url not in urls:
            urls.append(url)
    return urls


def parse_post_metadata(content: str) -> Dict[str, Any]:
    meta = {"draft": True, "date": ""}
    match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if match:
        fm = match.group(1)
        for line in fm.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "draft":
                    meta["draft"] = (v.lower() == "true")
                elif k == "date":
                    meta["date"] = v
    return meta

def select_top_published_urls(posts_dir: str, base_url: str = None, limit: int = 5) -> List[str]:
    """I6 색인 표본. **최신순 상위 N건이 아니다** — 크롤이 멈춘 지점을 찾는 표본이다.

    최신 글만 뽑으면 정의상 가장 색인될 가능성이 낮은 URL만 조회하게 되어
    "이 사이트가 색인되고는 있는가"에 답하지 못한다. 2026-08-01에 그 표본만
    보다가 홈페이지가 이미 색인돼 있다는 사실(`Submitted and indexed`,
    크롤 2026-07-19)을 13일간 놓쳤다.

    그래서 한정된 쿼터(최대 5건)를 셋으로 나눈다:
      1. 홈페이지 — 크롤 진입점. 여기가 죽으면 나머지는 볼 필요도 없다
      2. 최신 2건 — 새 글이 수집되고 있는가
      3. 최고령 2건 — 시간이 지나면 색인되기는 하는가

    `limit`이 5보다 작으면 위 순서대로 잘린다(홈페이지가 가장 먼저 살아남는다).
    """
    root = _root(base_url)

    pattern = os.path.join(posts_dir, "**", "*.md")
    files = glob.glob(pattern, recursive=True)
    published = []

    for fpath in files:
        if os.path.basename(fpath) == "welcome.md":
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        meta = parse_post_metadata(content)
        if not meta["draft"] and meta["date"]:
            slug = os.path.basename(fpath).removesuffix(".md")
            published.append((meta["date"], f"{root}/posts/{slug}/"))

    published.sort(key=lambda x: x[0], reverse=True)
    newest = [u for _, u in published[:2]]
    oldest = [u for _, u in published[-2:]]

    # 발행글이 적으면 newest와 oldest가 겹친다 — 순서를 보존한 채 중복만 제거한다.
    out: List[str] = [f"{root}/"]
    for url in newest + oldest:
        if url not in out:
            out.append(url)
    return out[:limit]

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == ["--all"]:
        # 인자를 조용히 흘리면 워크플로가 표본을 전수로 오독한다.
        print(" ".join(select_all_urls(argv[1] if len(argv) > 1 else "content")))
    elif argv[:1] and argv[0].startswith("--"):
        sys.exit("usage: select_inspect_urls.py [--all <content_dir> | <posts_dir>]")
    else:
        print(" ".join(select_top_published_urls(argv[0] if argv else "content/posts")))
