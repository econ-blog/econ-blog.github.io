#!/usr/bin/env python3
"""IndexNow 실시간 검색엔진 색인 통보 스크립트.

네이버, 빙(Bing) 등 IndexNow 프로토콜을 지원하는 검색엔진에
새 글 발행이나 사이트 갱신 URL 목록을 즉시 통보합니다.
공식 문서: https://www.indexnow.org/documentation
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path
import urllib.error
import urllib.request

INDEXNOW_API = "https://api.indexnow.org/IndexNow"
DEFAULT_HOST = "econ-blog.github.io"
SITE_BASE = f"https://{DEFAULT_HOST}"
REPO_ROOT = Path(__file__).resolve().parent.parent


def find_indexnow_key(repo_root: Path = REPO_ROOT) -> tuple[str | None, str | None]:
    """static/ 폴더 내 IndexNow 키 파일 및 위치를 탐색합니다."""
    static_dir = repo_root / "static"
    if not static_dir.exists():
        return None, None

    for p in sorted(static_dir.glob("*.txt")):
        name = p.stem
        # 보통 32자 내외의 16진수 키
        if len(name) >= 16 and re.match(r"^[0-9a-fA-F]+$", name):
            content = p.read_text(encoding="utf-8").strip()
            if content == name:
                key = content
                key_location = f"{SITE_BASE}/{p.name}"
                return key, key_location

    return None, None


DRAFT_TRUE = re.compile(r"^draft:\s*true\s*$", re.M)


def front_matter(path: Path) -> str:
    """파일 맨 앞 `---` 블록만 돌려준다. 없으면 빈 문자열.

    바이트 윈도로 앞부분만 읽는 방식(`get_recent_posts`가 쓰던 1024자)은 front
    matter에 `faq`·`related_articles`가 붙으면 `draft:` 줄을 놓칠 수 있다. 블록을
    정확히 잘라 읽는다.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else text


def is_draft(path: Path) -> bool:
    """front matter가 `draft: true`인가.

    읽을 수 없으면 초안이라고 단정하지 않는다(False). 워크플로는 `--diff-filter=d`로
    삭제 파일을 이미 걸러 넘기므로, 여기서 못 읽는 경로는 예외 상황이고 그때는
    기존 동작(제출)을 유지하는 쪽이 안전하다.
    """
    return bool(DRAFT_TRUE.search(front_matter(path)))


def resolve_urls_from_files(file_paths: list[str],
                            repo_root: Path = REPO_ROOT) -> list[str]:
    """파일 경로(포스트/사전)로부터 퍼머링크 URL 목록을 도출합니다.

    **`draft: true`인 파일은 제외한다.** Hugo는 초안을 렌더하지 않으므로 그 URL은
    사이트에 존재하지 않는다. 발행 게이트가 글을 보류하면(`draft: true`로 `main`에
    남긴다) 커밋 제목은 여전히 `post: `이고, `notify-post.yml`은 그 접두사만 보므로
    IndexNow 단계까지 그대로 내려온다 — 즉 보류될 때마다 404 URL을 네이버·빙에
    제출하고 있었다. 2026-09-24·09-27 두 회차가 실제로 그렇게 나갔다.
    """
    urls = []
    for fp in file_paths:
        p = Path(fp)
        name = p.stem
        if "content/posts" in fp or "content/dictionary" in fp:
            if p.name.startswith("_"):
                continue
            abs_p = p if p.is_absolute() else repo_root / fp
            if is_draft(abs_p):
                continue
        if "content/posts" in fp:
            urls.append(f"{SITE_BASE}/posts/{name}/")
        elif "content/dictionary" in fp:
            urls.append(f"{SITE_BASE}/dictionary/{name}/")
        elif fp.endswith("index.html") or fp in ("/", "index.html"):
            urls.append(f"{SITE_BASE}/")
    return sorted(set(urls))


def get_recent_posts(repo_root: Path = REPO_ROOT, limit: int = 5) -> list[str]:
    """최근 발행된 포스트 URL 목록을 가져옵니다."""
    posts = []
    pattern = str(repo_root / "content/posts/*.md")
    for fp in glob.glob(pattern):
        # front matter 블록을 통째로 본다 — 앞 1024자만 읽으면 description·faq가 긴
        # 글에서 `draft:` 줄이 창 밖으로 밀려 초안이 발행분으로 섞인다.
        front = front_matter(Path(fp))
        if not front or DRAFT_TRUE.search(front):
            continue
        date_m = re.search(r"^date:\s*([^\n]+)", front, re.M)
        if date_m:
            posts.append((date_m.group(1).strip("\"' "), Path(fp).stem))

    posts.sort(key=lambda x: x[0], reverse=True)
    return [f"{SITE_BASE}/posts/{stem}/" for _, stem in posts[:limit]]


def submit_indexnow(
    url_list: list[str],
    host: str = DEFAULT_HOST,
    key: str | None = None,
    key_location: str | None = None,
    api_url: str = INDEXNOW_API,
    dry_run: bool = False,
) -> dict:
    """IndexNow API 엔드포인트에 URL 목록을 POST 제출합니다."""
    if not url_list:
        return {"ok": False, "status": 0, "message": "제출할 URL 목록이 비어 있습니다."}

    if not key or not key_location:
        found_key, found_loc = find_indexnow_key()
        key = key or found_key
        key_location = key_location or found_loc

    if not key or not key_location:
        return {"ok": False, "status": 0, "message": "IndexNow 키 파일을 찾을 수 없습니다."}

    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": url_list,
    }

    if dry_run:
        return {
            "ok": True,
            "status": 200,
            "dry_run": True,
            "payload": payload,
            "message": f"[DRY-RUN] {len(url_list)}건 제출 시뮬레이션 성공",
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            # IndexNow는 200(성공) 또는 202(접수 완료)를 반환
            ok = status in (200, 202)
            return {
                "ok": ok,
                "status": status,
                "count": len(url_list),
                "message": f"IndexNow 제출 성공 (HTTP {status}, {len(url_list)}건)",
            }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status": e.code,
            "message": f"IndexNow HTTP 에러: {e.code} {e.reason}",
        }
    except Exception as e:
        return {
            "ok": False,
            "status": -1,
            "message": f"IndexNow 네트워크/연결 실패: {str(e)}",
        }


def main():
    parser = argparse.ArgumentParser(description="IndexNow URL 제출 헬퍼")
    parser.add_argument("--urls", nargs="*", help="제출할 URL 직접 지정")
    parser.add_argument("--files", nargs="*", help="제출할 마크다운 파일 경로 목록")
    parser.add_argument("--recent", type=int, default=0, help="최근 N개 포스트 제출")
    parser.add_argument("--dry-run", action="store_true", help="실제 요청 없이 페이로드 검증")
    args = parser.parse_args()

    urls_to_submit = []
    if args.urls:
        urls_to_submit.extend(args.urls)

    if args.files:
        urls_to_submit.extend(resolve_urls_from_files(args.files))

    if args.recent > 0:
        urls_to_submit.extend(get_recent_posts(limit=args.recent))

    if not urls_to_submit and not args.recent:
        env_files = os.environ.get("POST_FILES", "").strip()
        if env_files:
            file_list = [f.strip() for f in env_files.splitlines() if f.strip()]
            urls_to_submit.extend(resolve_urls_from_files(file_list))

    # 중복 제거
    urls_to_submit = sorted(set(urls_to_submit))

    if not urls_to_submit:
        print("⚠️ 제출할 대상 URL이 없습니다. (--urls, --files, --recent 또는 POST_FILES 환경변수를 지정하세요)")
        sys.exit(0)

    res = submit_indexnow(urls_to_submit, dry_run=args.dry_run)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok") and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
