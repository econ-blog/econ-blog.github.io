import os
import sys
import unittest
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import housekeeping

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
        # 1. 확정 사망 내부 링크 → 대상 없으면 `[기준금리](/x/)` → `기준금리` (앵커 텍스트 보존)
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
        # 2. `related_articles` 항목 제거 후 목록이 비면 **키 자체가 사라진다**(빈 리스트 금지)
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

    def test_source_url_never_changes(self):
        # 3. `source_url`은 죽어도 **바뀌지 않는다**
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
        # 4. 백필 적용이 문서당 3건·전체 20건에서 멈춘다
        # Single document max 3 test
        content = "---\ntitle: Test\n---\n" + "기준금리\n" * 10
        self._write_file("content/test_backfill.md", content)
        
        backfills = [
            {"file": "content/test_backfill.md", "term": "기준금리", "slug": "base-rate", "line": i + 4} 
            for i in range(10)
        ]
        
        # Test global limit of 20 using 8 files (each requesting 3 backfills = 24 candidates total)
        for f_idx in range(1, 9):
            path = f"content/file_{f_idx}.md"
            self._write_file(path, "---\ntitle: Test\n---\n" + f"단어_{f_idx}\n" * 5)
            backfills.extend([
                {"file": path, "term": f"단어_{f_idx}", "slug": f"slug-{f_idx}", "line": i + 4}
                for i in range(3)
            ])
            
        housekeeping.apply_edits(self.root, [], backfills)
        
        updated1 = self._read_file("content/test_backfill.md")
        # File 1 has local limit 3
        self.assertEqual(updated1.count("[기준금리](/dictionary/base-rate/)"), 3)
        
        total_backfills_applied = 0
        for f_idx in range(1, 9):
            path = f"content/file_{f_idx}.md"
            cnt = self._read_file(path).count(f"(/dictionary/slug-{f_idx}/)")
            total_backfills_applied += cnt
            
        # Total across files should be capped at 20 (including file 1's 3, so total 20)
        # file 1 (3) + files 1..8 = 20 total replacements
        self.assertEqual(total_backfills_applied + 3, 20)

if __name__ == "__main__":
    unittest.main()
