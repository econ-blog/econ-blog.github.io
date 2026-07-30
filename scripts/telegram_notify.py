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
                    return f"발행 전 검사: {re.sub(r'^[-*\s]+', '', nl)}"
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

def format_audit_notification(title: str, body: str, branch: str, url: str) -> str:
    token = extract_verdict_token(branch, "audit")
    
    lines = body.splitlines()
    filtered_lines = []
    keywords = ["계약 위반", "확정 사망 링크", "데이터 충분성", "색인 건전성", "소견", "새 가설 제안", "결정 필요", "주간 감사", "Audit Summary"]
    for l in lines:
        l_str = l.strip()
        if not l_str or l_str.startswith("PR:"):
            continue
        if any(k in l_str for k in keywords) or l_str.startswith("*") or l_str.startswith("-"):
            filtered_lines.append(l_str)
            
    summary_block = "\n".join(filtered_lines[:10]) if filtered_lines else (lines[0] if lines else "요약 정보 없음")
    return (
        f"{token} 주간 감사\n\n"
        f"{summary_block}\n\n"
        f"PR: {url}\n\n"
        f"승인 / 반려 로 답장."
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

def main():
    creds_json = os.environ.get("CREDENTIALS_JSON")
    if not creds_json:
        print("Error: CREDENTIALS_JSON missing", file=sys.stderr)
        sys.exit(1)
    creds = json.loads(creds_json)
    bot_token = creds["telegram"]["bot_token"]
    chat_id = creds["telegram"]["chat_id"]
    
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

if __name__ == "__main__":
    main()
