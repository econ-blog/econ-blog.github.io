"""seo_geo_audit 의 파싱·판정 단위 테스트.

렌더 산출물을 흉내 낸 최소 트리를 만들어 돌린다. 실제 `public/` 을 읽으면
콘텐츠가 바뀔 때마다 테스트가 깨져서 회귀 탐지력이 사라진다.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seo_geo_audit as S  # noqa: E402

POST = """<!DOCTYPE html><html lang="ko"><head>
<meta name="robots" content="index, follow">
<title>%(title)s | 쉽게 읽는 경제뉴스</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="https://econ-blog.github.io%(url)s">
<meta property="og:image" content="https://econ-blog.github.io/images/og-default.png" />
%(ld)s
</head><body><header class="post-header"><h1 class="post-title">%(title)s</h1></header>
<article class="post-single"><div class="post-content md-content">
<blockquote><p>핵심 요약</p></blockquote>
<p>%(lead)s</p>
<h2>%(h2)s</h2><p>본문.</p>
%(links)s
</div></article></body></html>
"""

BP = ('<script type="application/ld+json">{"@context":"https://schema.org",'
      '"@type":"BlogPosting","headline":"h","datePublished":"2026-08-01"}</script>')


def write(root, url, **kw):
    kw.setdefault("title", "제목")
    kw.setdefault("desc", "설명" * 40)
    kw.setdefault("lead", "2026년 8월 1일 지표가 3.4% 올랐습니다.")
    kw.setdefault("h2", "지표가 오른 이유")
    kw.setdefault("ld", BP)
    kw.setdefault("links", "")
    kw["url"] = url
    p = os.path.join(root, url.strip("/"), "index.html") if url != "/" \
        else os.path.join(root, "index.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(POST % kw)


class Tree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "robots.txt"), "w") as fh:
            fh.write("User-agent: *\nDisallow:\n\n"
                     "Sitemap: https://econ-blog.github.io/sitemap.xml\n")

    def tearDown(self):
        shutil.rmtree(self.root)

    def sitemap(self, urls):
        body = "".join("<url><loc>https://econ-blog.github.io%s</loc></url>" % u for u in urls)
        with open(os.path.join(self.root, "sitemap.xml"), "w") as fh:
            fh.write("<urlset>%s</urlset>" % body)

    def codes(self):
        return {f["code"]: f for f in S.audit(self.root)["findings"]}


class TestParsing(Tree):
    def test_h1_inside_post_header_is_found(self):
        # <header> 를 통째로 걷어내면 PaperMod 의 h1 이 사라진다 — 그 회귀를 잡는다.
        write(self.root, "/posts/a/", title="금리 인상")
        pg = S.Page(os.path.join(self.root, "posts/a/index.html"), self.root)
        self.assertEqual(pg.h1s, ["금리 인상"])

    def test_body_scoped_to_post_content(self):
        write(self.root, "/posts/a/")
        pg = S.Page(os.path.join(self.root, "posts/a/index.html"), self.root)
        self.assertIn("지표가 3.4% 올랐습니다", pg.lead)
        self.assertNotIn("쉽게 읽는 경제뉴스", pg.body_text)

    def test_title_head_strips_site_suffix(self):
        write(self.root, "/posts/a/", title="가계 빚 2000조")
        pg = S.Page(os.path.join(self.root, "posts/a/index.html"), self.root)
        self.assertEqual(pg.title_head, "가계 빚 2000조")

    def test_percent_encoded_link_resolves(self):
        # 한글 태그 URL 은 href 에서 퍼센트 인코딩돼 나온다. 디코드하지 않으면
        # 살아 있는 링크가 전부 "깨진 내부 링크" 로 잡힌다.
        self.assertEqual(S.normalize("/tags/%EA%B8%88%EB%A6%AC/", "/"), "/tags/금리/")

    def test_pagination_alias_not_counted_as_document(self):
        write(self.root, "/")
        write(self.root, "/posts/a/")
        write(self.root, "/posts/page/2/")
        self.sitemap(["/", "/posts/a/", "/posts/page/2/"])
        self.assertEqual(S.audit(self.root)["totals"]["posts"], 1)


class TestFindings(Tree):
    def test_clean_tree_has_no_high_severity(self):
        ld = BP.replace('"headline"', '"image":"x","citation":"y","headline"') + (
            '<script type="application/ld+json">{"@type":"FAQPage","mainEntity":[]}</script>')
        dt = ('<script type="application/ld+json">'
              '{"@type":"DefinedTerm","name":"기준금리"}</script>')
        write(self.root, "/posts/a/", title="금리가 오른 이유", ld=ld,
              links='<a href="/dictionary/t/">기준금리</a>'
                    '<a href="https://ecos.bok.or.kr/x">한국은행</a>')
        write(self.root, "/dictionary/t/", title="기준금리", ld=dt,
              desc="기준금리란 중앙은행이 정하는 금리입니다." * 3,
              lead="기준금리란 중앙은행이 정하는 기준선입니다.",
              links='<a href="/posts/a/">해설</a>')
        # 홈에서 두 문서로 나가는 크롬 링크(도달성용).
        write(self.root, "/", title="홈",
              links='<a href="/posts/a/">a</a><a href="/dictionary/t/">t</a>')
        self.sitemap(["/", "/posts/a/", "/dictionary/t/"])
        high = [c for c, f in self.codes().items() if f["severity"] == "high"]
        self.assertEqual(high, [], high)

    def test_missing_faq_is_high(self):
        write(self.root, "/")
        write(self.root, "/posts/a/")
        self.sitemap(["/", "/posts/a/"])
        self.assertEqual(self.codes()["S5"]["count"], 1)

    def test_legacy_headings_flagged(self):
        write(self.root, "/")
        write(self.root, "/posts/a/", h2="무슨 일이 있었나")
        self.sitemap(["/", "/posts/a/"])
        self.assertIn("A3", self.codes())

    def test_sitemap_gap_flagged(self):
        write(self.root, "/")
        write(self.root, "/posts/a/")
        self.sitemap(["/"])
        self.assertEqual(self.codes()["I1"]["items"], ["/posts/a/"])

    def test_llms_txt_coverage(self):
        write(self.root, "/")
        write(self.root, "/posts/a/")
        write(self.root, "/posts/b/")
        self.sitemap(["/", "/posts/a/", "/posts/b/"])
        with open(os.path.join(self.root, "llms.txt"), "w", encoding="utf-8") as fh:
            fh.write("# t\n- [a](https://econ-blog.github.io/posts/a/)\n")
        self.assertEqual(self.codes()["A5"]["items"], ["/posts/b/"])

        with open(os.path.join(self.root, "llms.txt"), "a", encoding="utf-8") as fh:
            fh.write("- [b](https://econ-blog.github.io/posts/b/)\n")
        self.assertNotIn("A5", self.codes())


if __name__ == "__main__":
    unittest.main()
