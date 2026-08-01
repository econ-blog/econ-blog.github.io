import os
import glob
import re
import sys
from typing import List, Dict, Any

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
    if not base_url:
        base_url = os.environ.get("GSC_SITE_URL") or "https://econ-blog.github.io"
    if base_url.startswith("sc-domain:"):
        base_url = "https://" + base_url.removeprefix("sc-domain:")
    root = base_url.rstrip("/")

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
    p_dir = sys.argv[1] if len(sys.argv) > 1 else "content/posts"
    urls = select_top_published_urls(p_dir)
    print(" ".join(urls))
