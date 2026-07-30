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
    for line in body.splitlines():
        if "발행 전 검사:" in line:
            return line.strip()
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
    for l in lines:
        if any(k in l for k in ["계약 위반:", "확정 사망 링크:", "데이터 충분성:", "색인 건전성:", "소견:", "새 가설 제안:", "─ 결정 필요 ─"]):
            filtered_lines.append(l)
            
    summary_block = "\n".join(filtered_lines) if filtered_lines else "요약 정보 없음"
    return (
        f"{token} 주간 감사\n\n"
        f"{summary_block}\n"
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
