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

def select_top_published_urls(posts_dir: str, base_url: str = "https://econ-blog.github.io", limit: int = 5) -> List[str]:
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
            slug = os.path.basename(fpath).replace(".md", "")
            url = f"{base_url.rstrip('/')}/posts/{slug}/"
            published.append((meta["date"], url))
            
    published.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in published[:limit]]

if __name__ == "__main__":
    p_dir = sys.argv[1] if len(sys.argv) > 1 else "content/posts"
    urls = select_top_published_urls(p_dir)
    print(" ".join(urls))
