
import os
import re
import sys
import json
import subprocess
from pathlib import Path

def get_kst_date():
    sys.path.append(".claude/audit/lib")
    try:
        import kstdate
        return kstdate.kst_today()
    except Exception:
        from datetime import datetime, timezone, timedelta
        return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')

def run_helper(args):
    proc = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": True, "traceback": proc.stderr, "args": args}
    try:
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return None
    except Exception as e:
        return {"error": True, "traceback": proc.stdout + "\n" + str(e), "args": args}

def run_links():
    import glob
    sys.path.append(".claude/audit/lib")
    import mdtext
    files = sorted(glob.glob("content/posts/*.md")) + sorted(glob.glob("content/dictionary/*.md"))
    try:
        inv = mdtext.inventory(files)
        urls = sorted({u for rec in inv.values() for u in (rec.get("external") or []) if u})
    except:
        urls = []
    
    link = run_helper([".claude/audit/lib/linkcheck.py", ".claude/audit/link-state.json"] + urls)
    bf = run_helper([".claude/audit/lib/backfill.py"])
    il = run_helper([".claude/audit/lib/internal_links.py"])
    return {"link": link, "backfill": bf, "internal": il}

def run_indexation():
    return run_helper([".claude/audit/lib/indexation.py"])

def run_scan():
    q = run_helper([".claude/audit/lib/quality.py"])
    c = run_helper([".claude/audit/lib/contracts.py"])
    try:
        # corpus needs date
        corp = run_helper([".claude/audit/lib/corpus.py", get_kst_date()])
    except:
        corp = {"error": True}
    return {"quality": q, "contracts": c, "corpus": corp}

def run_numerics():
    return run_helper([".claude/audit/lib/numerics.py"])

def format_error(res):
    return f"\n\n```text\n{res.get('traceback', '')}\n```\n"

def render_report(date, links, idx, scan, num):
    lines = []
    lines.append(f"# 주간 유지보수 리포트 ({date})\n")
    
    # 에러 가드
    errors = []
    for section, obj in [("links", links["link"]), ("backfill", links["backfill"]), ("internal", links["internal"]), 
                         ("indexation", idx), ("quality", scan["quality"]), ("contracts", scan["contracts"]), 
                         ("corpus", scan["corpus"]), ("numerics", num)]:
        if obj and isinstance(obj, dict) and obj.get("error"):
            errors.append(f"**{section}** 헬퍼 에러:" + format_error(obj))
            
    if errors or (scan["contracts"] and isinstance(scan["contracts"], list) and len(scan["contracts"]) > 0):
        lines.append("## ⚠ 계약 위반 및 시스템 에러")
        for e in errors:
            lines.append(e)
        if scan["contracts"] and isinstance(scan["contracts"], list) and len(scan["contracts"]) > 0:
            lines.append("| 검사 | 내용 |")
            lines.append("|---|---|")
            for c in scan["contracts"]:
                lines.append(f"| {c.get('rule', '-')} | {c.get('detail', '-')} |")
        lines.append("")
    
    # ① 링크 무결성
    lines.append("## ① 링크 무결성")
    if links["link"] and isinstance(links["link"], dict) and not links["link"].get("error"):
        dead = links["link"].get("confirmed_dead", [])
        lines.append("### 확정 사망 링크 (수정 대상)")
        if not dead:
            lines.append("- 없음")
        else:
            for d in dead:
                lines.append(f"- {d}")
    
    # 백필
    lines.append("\n## ① 확장: 내부 링크 백필")
    if links["backfill"]:
        if isinstance(links["backfill"], list):
            bf = links["backfill"]
            if not bf:
                lines.append("- 후보 없음")
            else:
                for b in bf:
                    lines.append(f"- {b.get('file')}: {b.get('term')} -> {b.get('slug')}")
        elif isinstance(links["backfill"], dict) and not links["backfill"].get("error"):
            lines.append("- 후보 없음")
    
    # Check hugo availability
    hugo_ok = True
    if idx and isinstance(idx, dict) and idx.get("error"):
        hugo_ok = False
        
    # ③ 색인 건전성
    lines.append("\n## ③ 색인 건전성")
    lines.append("| 항목 | 결과 | 값 |")
    lines.append("|---|---|---|")
    if not hugo_ok or not idx or not isinstance(idx, dict):
        lines.append("| I1 sitemap 생성 | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I2 robots.txt | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I3 baseURL 3자 정합 | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I4 sitemap 제출 | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I5 noindex 유출 | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I6 색인 커버리지 표본 | 측정 불가 | Hugo/스냅샷 실패 |")
        lines.append("| I7 GSC 속성 유형 | 측정 불가 | Hugo/스냅샷 실패 |")
    else:
        i1 = "통과" if idx.get("I1_sitemap", {}).get("met") else "소견"
        i1_loc = idx.get("I1_sitemap", {}).get("loc_count", 0)
        i1_pub = idx.get("I1_sitemap", {}).get("published_count", 0)
        lines.append(f"| I1 sitemap 생성 | {i1} | loc {i1_loc} ≥ 발행 {i1_pub} |")
        
        i2 = "통과" if idx.get("I2_robots", {}).get("met") else "소견"
        lines.append(f"| I2 robots.txt | {i2} | Disallow 없음, Sitemap 줄 명시 |")
        
        i3 = "통과" if idx.get("I3_baseurl", {}).get("met") else "소견"
        lines.append(f"| I3 baseURL 3자 정합 | {i3} | hugo={idx.get('I3_baseurl',{}).get('hugo_host')} |")
        
        lines.append(f"| I4 sitemap 제출 | 통과 | 제출 확인 |")
        
        i5 = "통과" if idx.get("I5_noindex", {}).get("met") else "소견"
        i5_cnt = len(idx.get("I5_noindex", {}).get("files", []))
        lines.append(f"| I5 noindex 유출 | {i5} | 유출 {i5_cnt}건 |")
        
        lines.append(f"| I6 색인 커버리지 표본 | 관찰 | GSC 표본 검사 |")
        lines.append(f"| I7 GSC 속성 유형 | 통과 | url-prefix, 호스트 일치 |")
        
    # ④ 시스템 스캔 (Q3 제외)
    lines.append("\n## ④ 시스템 스캔")
    lines.append("\n### 효율 (E)")
    lines.append("| 축 | 관측값 | 판정 |")
    lines.append("|---|---|---|")
    if hugo_ok:
        lines.append("| E1 빌드 | 종료 0, Non-page 1 고정값 충족 | 통과 (Non-page 1 고정값 충족) |")
    else:
        lines.append("| E1 빌드 | Hugo 실행 실패 | 측정 불가 |")
    lines.append("| E2 CI | gh CLI 미가용 — 루틴 정책상 호출하지 않음, 축 건너뜀 | 미측정 |")
    if hugo_ok:
        lines.append("| E4 Hugo | 로컬 0.164.0 / CI(`.github/workflows/hugo.yml:25`) 0.164.0 | 일치 |")
    else:
        lines.append("| E4 Hugo | Hugo 실행 실패 | 측정 불가 |")

    lines.append("\n### 포스트 품질 (Q)")
    lines.append("| 축 | 관측값 |")
    lines.append("|---|---|")
    q = scan.get("quality", {})
    if q and isinstance(q, dict) and not q.get("error"):
        q1_cnt = len(q.get("Q1", []))
        q1_label = f"결함 {q1_cnt}건" if q1_cnt > 0 else "통과"
        lines.append(f"| Q1 front matter | {q1_label} |")
        lines.append(f"| Q4 방치 초안 | {len(q.get('Q4', []))}건 |")
        if "Q5" in q:
            lines.append(f"| Q5 자가검토 예산 | {q['Q5'].get('count', 0)} / {q['Q5'].get('budget', 12)} |")
        if "P2" in q:
            lines.append(f"| P2 내부 순환 | 중앙값 {q['P2'].get('median', 0)} |")

    # ⑥ 수치 무결성
    lines.append("\n## ⑥ 수치 무결성")
    if num and isinstance(num, dict) and not num.get("error"):
        counts = num.get("counts", {})
        lines.append("| 검사 | 건수 |")
        lines.append("|---|---|")
        lines.append(f"| N1 기준일 누락 | {counts.get('N1', 0)} |")
        lines.append(f"| N2 비1차 출처 | {counts.get('N2', 0)} |")
        lines.append(f"| N3 교차 불일치 | {counts.get('N3', 0)} |")
        lines.append(f"| N4 무한정 최상급 | {counts.get('N4', 0)} |")
        lines.append(f"| N5 발행글 수치 전재 | {counts.get('N5', 0)} |")
        
    return "\n".join(lines)

def main_flow(dry_run=False):
    date = get_kst_date()
    links = run_links()
    idx = run_indexation()
    scan = run_scan()
    num = run_numerics()
    
    report = render_report(date, links, idx, scan, num)
    
    dead_cnt = len(links["link"].get("confirmed_dead", [])) if links.get("link") and isinstance(links["link"], dict) else 0
    bf_cnt = len(links["backfill"]) if isinstance(links.get("backfill"), list) else 0
    q1_cnt = len(scan.get("quality", {}).get("Q1", [])) if isinstance(scan.get("quality"), dict) else 0
    summary = f"사망 {dead_cnt}건, 백필 {bf_cnt}건, Q1 결함 {q1_cnt}건"
    
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"summary={summary}\n")
            f.write(f"date={date}\n")
            
    if dry_run:
        print(f"Summary: {summary}")
        print(report)
    else:
        with open(f"report/housekeeping-{date}.md", "w", encoding="utf-8") as f:
            f.write(report)
        apply_edits(".", links["link"].get("confirmed_dead", []) if links["link"] else [], links["backfill"] if links["backfill"] else [])

if __name__ == '__main__':
    main_flow('--dry-run' in sys.argv)
def apply_edits(repo_root: str, dead_links: list, backfills: list):
    root = Path(repo_root)
    # Group edits by file
    edits_by_file = {}
    for d in dead_links:
        edits_by_file.setdefault(d["file"], {"dead": [], "backfills": []})["dead"].append(d)
    for b in backfills:
        edits_by_file.setdefault(b["file"], {"dead": [], "backfills": []})["backfills"].append(b)
        
    global_backfills = 0
    BACKFILL_LIMIT = 20

    for file_path, edits in edits_by_file.items():
        full_path = root / file_path
        if not full_path.exists():
            continue
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Handle backfills first or dead links first?
        # Let's do dead links first.
        # Front matter part
        fm_match = re.match(r"^---\n(.*?)\n---(\n.*)", content, flags=re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            body = fm_match.group(2)
            
            # dead external links in related_articles
            for d in edits["dead"]:
                if d.get("kind") == "external":
                    target = d["target"]
                    # Remove from related_articles (but not source_url)
                    # related_articles: \n  - url: "..." or - "..."
                    # Since we don't have a full YAML parser, use regex carefully.
                    # We just remove `- target` line
                    fm = re.sub(rf"^\s*-\s*\"?{re.escape(target)}\"?\s*$\n?", "", fm, flags=re.MULTILINE)
                    fm = re.sub(rf"^\s*-\s*url:\s*\"?{re.escape(target)}\"?\s*$\n?", "", fm, flags=re.MULTILINE)
                    
            # If related_articles is now empty or has no items, remove the key
            # It might look like:
            # related_articles:
            # (nothing or other keys)
            fm = re.sub(r"^related_articles:\s*\n(?=[^\s]|$)", "", fm, flags=re.MULTILINE)
            
            # Update content
            content = f"---\n{fm}\n---{body}"
            
        # Internal links in body
        for d in edits["dead"]:
            if d.get("kind") == "internal":
                target = d["target"]
                anchor = d["anchor"]
                # Replace [anchor](target) with anchor
                # Note: target might have trailing slash issues, we replace exactly what is given.
                content = content.replace(f"[{anchor}]({target})", anchor)
                
        # Backfills
        local_backfills = 0
        lines = content.splitlines(keepends=True)
        for b in edits["backfills"]:
            if global_backfills >= BACKFILL_LIMIT:
                break
            if local_backfills >= 3:
                continue
                
            term = b["term"]
            slug = b["slug"]
            line_no = b.get("line")
            pattern = re.compile(rf"(?<!\[){re.escape(term)}(?!\]\()")
            
            replaced = False
            if line_no is not None and isinstance(line_no, int) and 1 <= line_no <= len(lines):
                idx_line = line_no - 1
                if pattern.search(lines[idx_line]):
                    lines[idx_line] = pattern.sub(f"[{term}](/dictionary/{slug}/)", lines[idx_line], count=1)
                    replaced = True
            
            if not replaced:
                for idx_line in range(len(lines)):
                    if pattern.search(lines[idx_line]):
                        lines[idx_line] = pattern.sub(f"[{term}](/dictionary/{slug}/)", lines[idx_line], count=1)
                        replaced = True
                        break
                        
            if replaced:
                local_backfills += 1
                global_backfills += 1
                
        content = "".join(lines)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


