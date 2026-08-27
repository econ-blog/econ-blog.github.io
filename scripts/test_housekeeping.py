import os
import sys
import unittest
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import housekeeping

class TestHousekeepingReportOutput(unittest.TestCase):
    """2026-08-27까지 `main_flow`는 리포트를 렌더만 하고 어디에도 쓰지 않았다.
    워크플로의 `git add report/housekeeping-*.md` 는 매칭되는 파일이 없어 매번 죽었고,
    유지보수는 사실상 한 번도 커밋되지 않았다. 이제 리포트는 격주 점검의 입력이다."""

    def test_report_path_matches_the_workflow_glob(self):
        import fnmatch
        path = housekeeping.report_path("2026-09-10")
        self.assertEqual(path, "report/housekeeping-2026-09-10.md")
        self.assertTrue(fnmatch.fnmatch(path, "report/housekeeping-*.md"))

    def test_main_flow_writes_the_report_file(self):
        from unittest.mock import patch
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                with patch.object(housekeeping, "get_kst_date", lambda: "2026-09-10"), \
                     patch.object(housekeeping, "run_links",
                                  lambda: {"link": {"confirmed_dead": []}, "backfill": [], "internal": []}), \
                     patch.object(housekeeping, "run_indexation", lambda: {}), \
                     patch.object(housekeeping, "run_scan",
                                  lambda: {"quality": {}, "contracts": [], "corpus": {}}), \
                     patch.object(housekeeping, "run_numerics", lambda: {}), \
                     patch.object(housekeeping, "apply_edits", lambda *a: None):
                    housekeeping.main_flow()
                written = housekeeping.report_path("2026-09-10")
                self.assertTrue(os.path.exists(written), "리포트가 파일로 쓰이지 않았다")
                with open(written, encoding="utf-8") as fh:
                    self.assertIn("주간 유지보수 리포트", fh.read())
            finally:
                os.chdir(cwd)

    def test_dry_run_writes_nothing(self):
        from unittest.mock import patch
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                with patch.object(housekeeping, "get_kst_date", lambda: "2026-09-10"), \
                     patch.object(housekeeping, "run_links",
                                  lambda: {"link": {"confirmed_dead": []}, "backfill": [], "internal": []}), \
                     patch.object(housekeeping, "run_indexation", lambda: {}), \
                     patch.object(housekeeping, "run_scan",
                                  lambda: {"quality": {}, "contracts": [], "corpus": {}}), \
                     patch.object(housekeeping, "run_numerics", lambda: {}):
                    housekeeping.main_flow(dry_run=True)
                self.assertFalse(os.path.exists("report"))
            finally:
                os.chdir(cwd)


class TestHousekeepingApplyEdits(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    def _write_file(self, path, content):
        full_path = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    def _read_file(self, path):
        with open(os.path.join(self.root, path), "r", encoding="utf-8") as f:
            return f.read()

    def test_dead_internal_link_preserves_anchor(self):
        content = textwrap.dedent("""\
            ---
            title: Test
            ---
            문장에서 [기준금리](/dictionary/x/)를 삭제합니다.
            """)
        self._write_file("content/test.md", content)
        
        dead_links = [
            {"file": "content/test.md", "target": "/dictionary/x/", "anchor": "기준금리", "kind": "internal"}
        ]
        
        housekeeping.apply_edits(self.root, dead_links, [])
        
        updated = self._read_file("content/test.md")
        self.assertIn("문장에서 기준금리를 삭제합니다.", updated)
        self.assertNotIn("[기준금리]", updated)

    def test_related_articles_empty_list_key_deleted(self):
        content = textwrap.dedent("""\
            ---
            title: Test
            related_articles:
              - https://example.com/dead
            ---
            본문
            """)
        self._write_file("content/test2.md", content)
        
        dead_links = [
            {"file": "content/test2.md", "target": "https://example.com/dead", "kind": "external"}
        ]
        
        housekeeping.apply_edits(self.root, dead_links, [])
        
        updated = self._read_file("content/test2.md")
        self.assertNotIn("related_articles:", updated)
        self.assertNotIn("- https://example.com/dead", updated)

    def test_related_articles_structured_dict_deleted(self):
        content = textwrap.dedent("""\
            ---
            title: Test Struct
            related_articles:
              - title: "Dead Article"
                url: "https://example.com/dead"
                source: "News"
              - title: "Alive Article"
                url: "https://example.com/alive"
                source: "News2"
            ---
            본문
            """)
        self._write_file("content/test_struct.md", content)

        dead_links = [
            {"file": "content/test_struct.md", "target": "https://example.com/dead", "kind": "external"}
        ]

        housekeeping.apply_edits(self.root, dead_links, [])

        updated = self._read_file("content/test_struct.md")
        self.assertNotIn("Dead Article", updated)
        self.assertNotIn("https://example.com/dead", updated)
        self.assertIn("Alive Article", updated)
        self.assertIn("https://example.com/alive", updated)

    def test_source_url_never_changes(self):
        content = textwrap.dedent("""\
            ---
            title: Test
            source_url: https://example.com/dead
            related_articles:
              - https://example.com/dead
            ---
            본문
            """)
        self._write_file("content/test3.md", content)
        
        dead_links = [
            {"file": "content/test3.md", "target": "https://example.com/dead", "kind": "external"}
        ]
        
        housekeeping.apply_edits(self.root, dead_links, [])
        
        updated = self._read_file("content/test3.md")
        self.assertIn("source_url: https://example.com/dead", updated)
        self.assertNotIn("related_articles:", updated)

    def test_backfill_limits(self):
        content = "---\ntitle: Test\n---\n" + "기준금리\n" * 10
        self._write_file("content/test_backfill.md", content)
        
        backfills = [
            {"file": "content/test_backfill.md", "term": "기준금리", "slug": "base-rate", "line": i + 4} 
            for i in range(10)
        ]
        
        for f_idx in range(1, 9):
            path = f"content/file_{f_idx}.md"
            self._write_file(path, "---\ntitle: Test\n---\n" + f"단어_{f_idx}\n" * 5)
            backfills.extend([
                {"file": path, "term": f"단어_{f_idx}", "slug": f"slug-{f_idx}", "line": i + 4}
                for i in range(3)
            ])
            
        housekeeping.apply_edits(self.root, [], backfills)
        
        updated1 = self._read_file("content/test_backfill.md")
        self.assertEqual(updated1.count("[기준금리](/dictionary/base-rate/)"), 3)
        
        total_backfills_applied = 0
        for f_idx in range(1, 9):
            path = f"content/file_{f_idx}.md"
            cnt = self._read_file(path).count(f"(/dictionary/slug-{f_idx}/)")
            total_backfills_applied += cnt
            
        self.assertEqual(total_backfills_applied + 3, 20)

    def test_apply_edits_handles_error_dicts_safely(self):
        # Passing error dict or non-list should not raise exception
        housekeeping.apply_edits(self.root, {"error": True}, {"error": True})
        housekeeping.apply_edits(self.root, ["invalid"], ["invalid"])

    def test_backfill_masks_existing_links_code_headings(self):
        # Ensure terms inside existing links, code spans, headings, and comments are protected
        content = textwrap.dedent("""\
            ---
            title: 기준금리 분석
            ---
            ## 기준금리 헤더
            [한국의 기준금리 동향](/posts/123/)
            `기준금리`
            <!-- 기준금리 주석 -->
            본문에서 기준금리가 중요하다.
            """)
        self._write_file("content/masked_test.md", content)
        backfills = [{"file": "content/masked_test.md", "term": "기준금리", "slug": "base-rate"}]
        
        housekeeping.apply_edits(self.root, [], backfills)
        updated = self._read_file("content/masked_test.md")
        
        # Front matter title, header, code span, comment, and existing link must be unchanged!
        self.assertIn("title: 기준금리 분석", updated)
        self.assertIn("## 기준금리 헤더", updated)
        self.assertIn("[한국의 기준금리 동향](/posts/123/)", updated)
        self.assertIn("`기준금리`", updated)
        self.assertIn("<!-- 기준금리 주석 -->", updated)
        # Plain text should be backfilled
        self.assertIn("본문에서 [기준금리](/dictionary/base-rate/)가 중요하다.", updated)

    def test_render_report_handles_helper_errors(self):
        links = {"link": {"error": True}, "backfill": {"error": True}, "internal": None}
        idx = {"error": True}
        scan = {"quality": {"error": True}, "contracts": []}
        num = {"error": True}
        
        report = housekeeping.render_report("2026-08-13", links, idx, scan, num)
        self.assertIn("측정 불가", report)
        self.assertIn("⚠ 계약 위반 및 시스템 에러", report)

if __name__ == "__main__":
    unittest.main()
