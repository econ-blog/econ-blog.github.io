#!/usr/bin/env python3
"""test_indexnow.py — scripts/indexnow.py 단위 테스트."""

import unittest
import os
import sys
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


if __name__ == "__main__":
    unittest.main()

