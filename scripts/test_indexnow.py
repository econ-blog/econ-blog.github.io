#!/usr/bin/env python3
"""test_indexnow.py — scripts/indexnow.py 단위 테스트."""

import unittest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indexnow



class TestIndexNow(unittest.TestCase):
    def test_find_indexnow_key(self):
        key, loc = indexnow.find_indexnow_key()
        self.assertIsNotNone(key)
        self.assertIsNotNone(loc)
        self.assertEqual(key, "d049868f03d747069a45efc8fb3183b2")
        self.assertTrue(loc.endswith(".txt"))
        self.assertTrue(loc.startswith("https://econ-blog.github.io/"))

    def test_resolve_urls_from_files(self):
        files = [
            "content/posts/example-slug.md",
            "content/dictionary/sample-term.md",
            "content/dictionary/_terms.yaml",
            "content/other.md",
        ]
        urls = indexnow.resolve_urls_from_files(files)
        self.assertIn("https://econ-blog.github.io/posts/example-slug/", urls)
        self.assertIn("https://econ-blog.github.io/dictionary/sample-term/", urls)
        # _terms.yaml and other files should be excluded
        self.assertEqual(len(urls), 2)

    def test_get_recent_posts(self):
        urls = indexnow.get_recent_posts(limit=3)
        self.assertIsInstance(urls, list)
        self.assertGreater(len(urls), 0)
        self.assertLessEqual(len(urls), 3)
        for u in urls:
            self.assertTrue(u.startswith("https://econ-blog.github.io/posts/"))

    def test_submit_dry_run(self):
        res = indexnow.submit_indexnow(
            ["https://econ-blog.github.io/posts/test/"],
            dry_run=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], 200)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["payload"]["urlList"], ["https://econ-blog.github.io/posts/test/"])

    @patch.dict(os.environ, {"POST_FILES": "content/posts/my-new-post.md\ncontent/dictionary/my-term.md"})
    def test_post_files_env(self):
        urls = indexnow.resolve_urls_from_files(os.environ["POST_FILES"].splitlines())
        self.assertEqual(len(urls), 2)
        self.assertIn("https://econ-blog.github.io/posts/my-new-post/", urls)
        self.assertIn("https://econ-blog.github.io/dictionary/my-term/", urls)


class TestDraftExclusion(unittest.TestCase):
    """보류 초안(`draft: true`)의 URL을 IndexNow에 넘기지 않는지.

    2026-09-27 회차 4에서 발견한 결함의 회귀 테스트다. 발행 게이트가 글을 보류하면
    `draft: true`로 `main`에 남는데 커밋 제목은 여전히 `post: `이라서
    `notify-post.yml`의 IndexNow 단계가 그대로 실행됐고, Hugo가 렌더하지 않는
    URL(=404)을 네이버·빙에 제출했다. 09-24·09-27 두 건이 실제로 나갔다.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "content/posts").mkdir(parents=True)
        (self.root / "content/dictionary").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rel, draft, extra=""):
        fp = self.root / rel
        fp.write_text(
            "---\n"
            'title: "테스트"\n'
            "date: 2026-09-27T05:00:00+09:00\n"
            f"{extra}"
            f"draft: {'true' if draft else 'false'}\n"
            "---\n\n본문\n",
            encoding="utf-8",
        )
        return rel

    def test_draft_post_excluded(self):
        held = self._write("content/posts/held.md", draft=True)
        live = self._write("content/posts/live.md", draft=False)
        urls = indexnow.resolve_urls_from_files([held, live], repo_root=self.root)
        self.assertEqual(urls, ["https://econ-blog.github.io/posts/live/"])

    def test_draft_dictionary_term_excluded(self):
        """사전 용어는 같은 회차 포스트와 draft 값을 공유한다 — 보류되면 같이 빠진다."""
        held = self._write("content/dictionary/held-term.md", draft=True)
        live = self._write("content/dictionary/live-term.md", draft=False)
        urls = indexnow.resolve_urls_from_files([held, live], repo_root=self.root)
        self.assertEqual(urls, ["https://econ-blog.github.io/dictionary/live-term/"])

    def test_draft_line_after_long_front_matter(self):
        """description·faq가 길어 `draft:` 줄이 앞 1024자 밖으로 밀려도 잡아낸다."""
        long_desc = 'description: "' + ("가" * 900) + '"\n'
        faq = "faq:\n" + "".join(
            f'  - q: "질문{i}"\n    a: "{"답" * 120}"\n' for i in range(3)
        )
        held = self._write("content/posts/long.md", draft=True, extra=long_desc + faq)
        urls = indexnow.resolve_urls_from_files([held], repo_root=self.root)
        self.assertEqual(urls, [])

    def test_unreadable_path_still_submitted(self):
        """읽을 수 없는 경로는 초안이라고 단정하지 않는다(기존 동작 유지)."""
        urls = indexnow.resolve_urls_from_files(
            ["content/posts/does-not-exist.md"], repo_root=self.root
        )
        self.assertEqual(urls, ["https://econ-blog.github.io/posts/does-not-exist/"])

    def test_terms_yaml_still_excluded(self):
        urls = indexnow.resolve_urls_from_files(
            ["content/dictionary/_terms.yaml"], repo_root=self.root
        )
        self.assertEqual(urls, [])

    def test_get_recent_posts_excludes_drafts(self):
        self._write("content/posts/held.md", draft=True)
        self._write("content/posts/live.md", draft=False)
        urls = indexnow.get_recent_posts(repo_root=self.root, limit=5)
        self.assertEqual(urls, ["https://econ-blog.github.io/posts/live/"])


if __name__ == "__main__":
    unittest.main()

