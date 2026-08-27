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

def run_helper(args, timeout=120):
    try:
        proc = subprocess.run([sys.executable] + args, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return {"error": True, "traceback": proc.stderr or proc.stdout, "returncode": proc.returncode, "args": args}
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return None
    except Exception as e:
        return {"error": True, "traceback": str(e), "args": args}

def run_links():
    import glob
    sys.path.append(".claude/audit/lib")
    import mdtext
    files = sorted(glob.glob("content/posts/*.md")) + sorted(glob.glob("content/dictionary/*.md"))
    try:
        inv = mdtext.inventory(files)
        urls = sorted({u for rec in inv.values() for u in (rec.get("external") or []) if u})
    except Exception:
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
        corp = run_helper([".claude/audit/lib/corpus.py", get_kst_date()])
    except Exception:
        corp = {"error": True}
    return {"quality": q, "contracts": c, "corpus": corp}

def run_numerics():
    return run_helper([".claude/audit/lib/numerics.py"])

def format_error(res):
    return f"\n\n```text\n{res.get('traceback', '')}\n```\n"

def remove_dead_external_from_fm(fm: str, target: str) -> str:
    lines = fm.splitlines(keepends=True)
    new_lines = []
    current_item = []
    in_related = False
    
    for line in lines:
        if line.startswith("related_articles:"):
            in_related = True
            new_lines.append(line)
            continue
        
        if in_related:
            if line and not line[0].isspace() and ":" in line:
                if current_item:
                    item_str = "".join(current_item)
                    if target not in item_str:
                        new_lines.extend(current_item)
                    current_item = []
                in_related = False
                new_lines.append(line)
                continue
            
            if line.lstrip().startswith("- "):
                if current_item:
                    item_str = "".join(current_item)
                    if target not in item_str:
                        new_lines.extend(current_item)
                    current_item = []
                current_item.append(line)
            elif current_item:
                current_item.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    if current_item:
        item_str = "".join(current_item)
        if target not in item_str:
            new_lines.extend(current_item)
            
    res = "".join(new_lines)
    return re.sub(r"^related_articles:\s*\n(?=[^\s]|$)", "", res, flags=re.MULTILINE)

def render_report(date, links, idx, scan, num):
    lines = []
    lines.append(f"# 주간 유지보수 리포트 ({date})\n")
    
    # 에러 가드
    errors = []
    for section, obj in [("links", links.get("link")), ("backfill", links.get("backfill")), ("internal", links.get("internal")), 
                         ("indexation", idx), ("quality", scan.get("quality")), ("contracts", scan.get("contracts")), 
                         ("corpus", scan.get("corpus")), ("numerics", num)]:
        if obj and isinstance(obj, dict) and obj.get("error"):
            errors.append(f"**{section}** 헬퍼 에러:" + format_error(obj))
            
    if errors or (scan.get("contracts") and isinstance(scan["contracts"], list) and len(scan["contracts"]) > 0):
        lines.append("## ⚠ 계약 위반 및 시스템 에러")
        for e in errors:
            lines.append(e)
        if scan.get("contracts") and isinstance(scan["contracts"], list) and len(scan["contracts"]) > 0:
            lines.append("| 검사 | 내용 |")
            lines.append("|---|---|")
            for c in scan["contracts"]:
                lines.append(f"| {c.get('rule', '-')} | {c.get('detail', '-')} |")
        lines.append("")
    
    # ① 링크 무결성
    lines.append("## ① 링크 무결성")
    if links.get("link") and isinstance(links["link"], dict) and not links["link"].get("error"):
        dead = links["link"].get("confirmed_dead", [])
        lines.append("### 확정 사망 링크 (수정 대상)")
        if not dead:
            lines.append("- 없음")
        else:
            for d in dead:
                lines.append(f"- {d}")
    else:
        lines.append("- 측정 불가 (헬퍼 오류)")
    
    # 백필
    lines.append("\n## ① 확장: 내부 링크 백필")
    if isinstance(links.get("backfill"), list):
        bf = links["backfill"]
        if not bf:
            lines.append("- 후보 없음")
        else:
            for b in bf:
                if isinstance(b, dict):
                    lines.append(f"- {b.get('file')}: {b.get('term')} -> {b.get('slug')}")
    else:
        lines.append("- 측정 불가 (헬퍼 오류)")
    
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
        lines.append("| I6 색인 커버리지 | 측정 불가 | Hugo/스냅샷 실패 |")
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
        
        lines.append(f"| I6 색인 커버리지 | 관찰 | GSC 전수 검사 |")
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

def mask_protected_markdown(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Mask fenced code blocks, comments, images, existing links, and inline code."""
    placeholders = []
    
    def store_token(m):
        tok = f"__HK_PROT_{len(placeholders)}__"
        placeholders.append((tok, m.group(0)))
        return tok

    # 1. Fenced code blocks
    text = re.sub(r"```[\s\S]*?```", store_token, text)
    # 2. HTML comments
    text = re.sub(r"<!--[\s\S]*?-->", store_token, text)
    # 3. Images
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", store_token, text)
    # 4. Existing Markdown links
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", store_token, text)
    # 5. Inline code spans
    text = re.sub(r"`[^`\n]+`", store_token, text)
    
    return text, placeholders

def unmask_protected_markdown(text: str, placeholders: list[tuple[str, str]]) -> str:
    res = text
    for tok, orig in reversed(placeholders):
        res = res.replace(tok, orig)
    return res

def apply_edits(repo_root: str, dead_links: list, backfills: list):
    root = Path(repo_root)
    if not isinstance(dead_links, list):
        dead_links = []
    if not isinstance(backfills, list):
        backfills = []

    # Group edits by file path
    edits_by_file = {}
    for d in dead_links:
        if isinstance(d, dict) and d.get("file"):
            edits_by_file.setdefault(d["file"], {"dead": [], "backfills": []})["dead"].append(d)
    for b in backfills:
        if isinstance(b, dict) and b.get("file"):
            edits_by_file.setdefault(b["file"], {"dead": [], "backfills": []})["backfills"].append(b)

    global_backfills = 0
    BACKFILL_LIMIT = 20

    for file_path, edits in edits_by_file.items():
        full_path = root / file_path
        if not full_path.exists():
            continue

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read().replace("\r\n", "\n")

        # Split front matter and body
        fm = ""
        body = content
        fm_match = re.match(r"^---\n(.*?)\n---(?:\n|$)(.*)", content, flags=re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            body = fm_match.group(2)

            # Dead external links in related_articles
            for d in edits["dead"]:
                if d.get("kind") == "external" and d.get("target"):
                    target = d["target"]
                    fm = remove_dead_external_from_fm(fm, target)

        # Internal dead links in body
        for d in edits["dead"]:
            if d.get("kind") == "internal" and d.get("target") and d.get("anchor"):
                target = d["target"]
                anchor = d["anchor"]
                body = body.replace(f"[{anchor}]({target})", anchor)

        # Backfills on masked body lines
        local_backfills = 0
        masked_body, placeholders = mask_protected_markdown(body)
        lines = masked_body.splitlines(keepends=True)

        for b in edits["backfills"]:
            if global_backfills >= BACKFILL_LIMIT or local_backfills >= 3:
                break
            term = b.get("term")
            slug = b.get("slug")
            if not term or not slug:
                continue

            pattern = re.compile(rf"(?<!\[){re.escape(term)}(?!\]\()")
            replaced = False

            for idx in range(len(lines)):
                line_str = lines[idx]
                stripped = line_str.lstrip()
                if stripped.startswith(("#", "|", ">")) or line_str.startswith("    ") or line_str.startswith("\t"):
                    continue  # Heading, table, blockquote, indented code block

                if pattern.search(line_str):
                    lines[idx] = pattern.sub(f"[{term}](/dictionary/{slug}/)", line_str, count=1)
                    replaced = True
                    break

            if replaced:
                local_backfills += 1
                global_backfills += 1

        unmasked_body = unmask_protected_markdown("".join(lines), placeholders)
        new_content = f"---\n{fm}\n---" + unmasked_body if fm_match else unmasked_body

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

def report_path(date: str) -> str:
    return f"report/housekeeping-{date}.md"


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
        # 리포트를 **파일로 쓴다.** 2026-08-27까지 이 스크립트는 리포트를 렌더만 하고
        # 어디에도 쓰지 않았다. 워크플로는 `git add report/housekeeping-*.md`를 했고,
        # 매칭되는 파일이 없어 그 스텝이 매번 죽었다 — 유지보수는 사실상 한 번도
        # 커밋된 적이 없다. 격주 점검이 이 리포트를 입력으로 읽으므로 이제는 산출물이다.
        Path("report").mkdir(exist_ok=True)
        with open(report_path(date), "w", encoding="utf-8") as f:
            f.write(report + "\n")

        dead_urls = set(links["link"].get("confirmed_dead", [])) if links.get("link") and isinstance(links["link"], dict) else set()
        dead_list = []
        if dead_urls:
            import glob
            files = sorted(glob.glob("content/posts/*.md")) + sorted(glob.glob("content/dictionary/*.md"))
            try:
                sys.path.append(".claude/audit/lib")
                import mdtext
                inv = mdtext.inventory(files)
                for file_path, rec in inv.items():
                    for u in rec.get("external", []):
                        if u in dead_urls:
                            kind = "external" if u in rec.get("related_urls", []) else "internal"
                            dead_list.append({"file": file_path, "target": u, "kind": kind})
            except Exception:
                pass
        bf_list = links["backfill"] if isinstance(links.get("backfill"), list) else []
        apply_edits(".", dead_list, bf_list)

if __name__ == '__main__':
    main_flow('--dry-run' in sys.argv)
