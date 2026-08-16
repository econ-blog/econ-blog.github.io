import os
import re
import sys
import json
import requests

def extract_verdict_token(branch_name: str, pr_type: str) -> str:
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', branch_name)
    mmdd = (match.group(2) + match.group(3)) if match else "0000"
    prefix = "P" if pr_type == "post" else "A"
    return f"#{prefix}{mmdd}"

LEADING_BULLET = re.compile(r'^[-*\s]+')


def extract_inspection_line(body: str) -> str:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        clean = line.strip()
        m = re.search(r'(?:#+\s*)?발행\s*전\s*검사:\s*(.+)', clean)
        if m and m.group(1).strip():
            return f"발행 전 검사: {m.group(1).strip()}"
        
        if re.search(r'#+\s*발행\s*전\s*검사', clean):
            for next_line in lines[i+1:]:
                nl = next_line.strip()
                if nl:
                    # f-string 표현식 안에 백슬래시를 두면 Python 3.11에서
                    # SyntaxError다(3.12의 PEP 701부터 허용). 워크플로는 3.12라
                    # 통과했지만 로컬 .venv(3.11)에서는 import 자체가 깨져
                    # test_automation.py 전체가 실패했다. 치환을 밖으로 뺀다.
                    stripped = LEADING_BULLET.sub('', nl)
                    return f"발행 전 검사: {stripped}"
            return "발행 전 검사: 진행됨"
    return "발행 전 검사: 검사 불가"

def format_post_notification(title: str, body: str, branch: str, url: str) -> str:
    token = extract_verdict_token(branch, "post")
    inspection = extract_inspection_line(body)
    
    clean_body = re.sub(r'#.*?(?:\n|$)', '', body)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_body) if s.strip()]
    summary = " ".join(sentences[:2]) if len(sentences) >= 2 else (sentences[0] if sentences else "")
    
    return (
        f"{token} 오늘의 포스트\n\n"
        f"{title}\n"
        f"{summary}\n\n"
        f"{inspection}\n"
        f"PR: {url}\n\n"
        f"승인 / 반려 로 답장."
    )

# weekly-audit.md §9-1이 PR 본문에 쓰기로 한 여섯 줄의 키. `키:` 형태만 받는다.
# 리포트 본문의 H2(`## ⚠ 계약 위반`)는 콜론이 없어 의도적으로 탈락한다 — 리포트를
# 통째로 복사하면 값이 빠진 헤딩만 늘어서 요약처럼 보이는 빈 메시지가 된다.
SUMMARY_KEYS = ("계약 위반", "확정 사망 링크", "데이터 충분성",
                "색인 건전성", "소견", "front matter 수정", "새 가설 제안")
SUMMARY_LINE = re.compile(r'^(?:' + '|'.join(SUMMARY_KEYS) + r')\s*:\s*\S')
DECISION_DIVIDER = re.compile(r'^[─-]+\s*결정 필요\s*[─-]*$')


def summarize_audit_body(body: str) -> str:
    """§9-1 블록에서 알림에 실을 줄만 남긴다.

    PR 경로(`auto/audit-*`)와 리포트 경로(`main` 직행) 둘이 같은 커밋 메시지
    계약을 쓰므로 필터도 하나다. 한쪽만 고치면 두 알림의 요약이 갈린다.
    """
    filtered_lines = []
    in_decision_block = False
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if DECISION_DIVIDER.match(line):
            in_decision_block = True
            filtered_lines.append(line)
        elif SUMMARY_LINE.match(line):
            filtered_lines.append(line)
        elif in_decision_block and line[:1] in ("*", "-"):
            # 결정 필요 블록 안의 항목만 싣는다. 블록 밖의 불릿은 리포트 산문이다.
            filtered_lines.append(line)

    # 계약을 지키지 않은 본문은 조용히 반쪽 요약을 내지 않고 그렇다고 말한다.
    # 링크는 아래에 그대로 붙으므로 사람이 열어볼 경로는 남는다.
    return "\n".join(filtered_lines[:12]) if filtered_lines else "요약 정보 없음"


def format_audit_notification(title: str, body: str, branch: str, url: str) -> str:
    token = extract_verdict_token(branch, "audit")
    return (
        f"{token} 주간 감사\n\n"
        f"{summarize_audit_body(body)}\n\n"
        f"PR: {url}\n\n"
        f"승인 / 반려 로 답장."
    )


def format_audit_report_notification(body: str, report_path: str, url: str) -> str:
    """감사 리포트가 `main`에 올라갔을 때의 알림.

    **판정 토큰(`#A0808`)을 넣지 않고 승인/반려를 묻지도 않는다.** 리포트와
    원장은 2026-08-01 결정에 따라 승인 없이 `main`으로 직행하는 관측치라
    사람이 반려할 대상이 아니다. 토큰을 넣으면 사용자가 무심코 답장했을 때
    `process_inbox.py`가 열려 있지도 않은 `auto/audit-*` PR을 찾는다.

    콘텐츠 수정이 딸린 주에는 이 알림과 별개로 `auto/audit-*` PR 알림
    (`format_audit_notification`)이 따로 가며, 승인 대상은 그쪽뿐이다.
    """
    name = os.path.basename(report_path) if report_path else "audit report"
    return (
        f"📋 주간 감사 리포트 — {name}\n\n"
        f"{summarize_audit_body(body)}\n\n"
        f"리포트: {url}\n\n"
        f"확인만 하면 된다 — 승인 대상이 아니다."
    )


def format_automation_alert(workflow: str, reason: str, detail: str, run_url: str) -> str:
    """수집 워크플로 실패 경보. §9-1 PR 본문 계약과 무관한 별개 경로다.

    SUMMARY_LINE 매처에 걸리지 않도록 'X: Y' 형태의 줄을 만들지 않는다.
    """
    return (
        f"⚠ 자동화 경보 [{workflow}]\n\n"
        f"{reason}\n"
        f"{detail}\n\n"
        f"실행 로그 {run_url}"
    )


def send_telegram_message(bot_token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        err_msg = str(e)
        if bot_token:
            err_msg = err_msg.replace(bot_token, "[MASKED_BOT_TOKEN]")
        print(f"Telegram API send failed: {err_msg}", file=sys.stderr)
        sys.exit(1)


# 텔레그램 텍스트 메시지 상한은 4096자다. UTF-8 바이트가 아니라 문자 수이며,
# 넘기면 400 Bad Request로 통째로 실패한다 — 잘라 보내는 쪽이 낫다.
TELEGRAM_TEXT_LIMIT = 3500


def strip_front_matter(raw: str) -> str:
    """본문만 남긴다. 초안 알림에서 front matter는 읽을 가치가 없다."""
    return re.sub(r'^---\s*\n.*?\n---\s*\n?', '', raw, count=1, flags=re.DOTALL)


def chunk_text(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list:
    """문단 경계를 우선 지키고, 한 문단이 상한을 넘으면 그 문단만 강제로 자른다."""
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(para) > limit:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(para), limit):
                chunks.append(para[i:i + limit])
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > limit:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def send_telegram_document(bot_token: str, chat_id: str, path: str, caption: str = ""):
    """초안 파일을 첨부한다. 실패해도 죽지 않는다 — 요약 메시지는 이미 갔고,
    첨부는 편의 기능이라 이것 때문에 워크플로를 실패시키면 PR 코멘트 폴백이
    '알림 전송 실패'라고 거짓말을 하게 된다."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(path, "rb") as fh:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": (os.path.basename(path), fh, "text/markdown")},
                timeout=30,
            )
        resp.raise_for_status()
        return True
    except Exception as e:
        err_msg = str(e)
        if bot_token:
            err_msg = err_msg.replace(bot_token, "[MASKED_BOT_TOKEN]")
        print(f"Telegram document send failed ({path}): {err_msg}", file=sys.stderr)
        return False


def send_draft_files(bot_token: str, chat_id: str, paths: list):
    """포스트 초안을 본문(인라인) + 파일(첨부) 두 형태로 보낸다.

    인라인이 주다 — 텔레그램은 .md를 다운로드 카드로만 그려서 모바일에서 바로
    읽히지 않는다. 첨부는 원문 확인·보관용이다.
    """
    for path in paths:
        if not os.path.isfile(path):
            print(f"draft file not found, skipping: {path}", file=sys.stderr)
            continue
        raw = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        body = strip_front_matter(raw).strip()
        chunks = chunk_text(body)
        for i, chunk in enumerate(chunks, 1):
            header = f"📄 {name}" + (f" ({i}/{len(chunks)})" if len(chunks) > 1 else "")
            send_telegram_message(bot_token, chat_id, f"{header}\n\n{chunk}")
        send_telegram_document(bot_token, chat_id, path, caption=name)

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (bot_token and chat_id):
        creds_json = os.environ.get("CREDENTIALS_JSON")
        if not creds_json:
            print("Error: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or CREDENTIALS_JSON missing", file=sys.stderr)
            sys.exit(1)
        creds = json.loads(creds_json)
        bot_token = creds["telegram"]["bot_token"]
        chat_id = creds["telegram"]["chat_id"]
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "alert":
        workflow, reason, detail, run_url = sys.argv[2:6]
        send_telegram_message(bot_token, chat_id,
                              format_automation_alert(workflow, reason, detail, run_url))
        return

    if mode == "audit-report":
        # `main` 직행 리포트 경로. PR이 없으므로 PR_* 환경변수를 쓰지 않는다.
        send_telegram_message(bot_token, chat_id, format_audit_report_notification(
            os.environ.get("COMMIT_BODY", ""),
            os.environ.get("REPORT_PATH", ""),
            os.environ.get("REPORT_URL", ""),
        ))
        return

    branch = os.environ.get("PR_BRANCH", "")
    title = os.environ.get("PR_TITLE", "")
    body = os.environ.get("PR_BODY", "")
    url = os.environ.get("PR_URL", "")
    
    if "auto/post-" in branch:
        msg = format_post_notification(title, body, branch, url)
    elif "auto/audit-" in branch:
        msg = format_audit_notification(title, body, branch, url)
    else:
        sys.exit(0)

    send_telegram_message(bot_token, chat_id, msg)

    # 초안 본문·파일 전송. 포스트 PR에만 붙인다 — 감사 PR은 리포트가 길고
    # 요약이 이미 판정에 필요한 것을 다 담는다.
    if "auto/post-" in branch:
        paths = [p.strip() for p in os.environ.get("PR_FILES", "").splitlines() if p.strip()]
        if paths:
            send_draft_files(bot_token, chat_id, paths)

if __name__ == "__main__":
    main()
