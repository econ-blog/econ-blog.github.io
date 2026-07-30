import os
import re
import sys
import json
import base64
import requests

APPROVED_SET = {"승인", "발행", "게시", "ok", "okay", "go"}
REJECTED_SET = {"반려", "보류", "취소", "폐기", "no"}
NEGATION_WORDS = {"안", "않", "못", "금지", "no", "not"}

def parse_verdict(text: str) -> str:
    cleaned = re.sub(r'#([paPA])\d{4}', '', text).strip().lower()
    if cleaned in APPROVED_SET:
        return "APPROVED"
    if cleaned in REJECTED_SET:
        return "REJECTED"
    return "AMBIGUOUS"

def match_target_pr(update: dict, open_prs: list) -> tuple:
    msg = update.get("message", {})
    text = msg.get("text", "")
    reply_text = msg.get("reply_to_message", {}).get("text", "")
    
    # 1. Check reply token
    reply_match = re.search(r'#([paPA])(\d{4})', reply_text)
    token_match = reply_match or re.search(r'#([paPA])(\d{4})', text)
    
    if token_match:
        prefix = token_match.group(1).upper()
        mmdd = token_match.group(2)
        pr_prefix = "auto/post-" if prefix == "P" else "auto/audit-"
        target_date_str = f"-{mmdd[:2]}-{mmdd[2:]}"
        for pr in open_prs:
            ref = pr["head"]["ref"]
            if ref.startswith(pr_prefix) and target_date_str in ref:
                return (pr, "TOKEN_MATCH")
        return (None, "TOKEN_NOT_FOUND")
        
    if len(open_prs) == 1:
        return (open_prs[0], "SINGLE_PR_FALLBACK")
    elif len(open_prs) == 0:
        return (None, "NO_OPEN_PRS")
    else:
        return (None, "MULTIPLE_PRS_NEED_TOKEN")

def send_telegram(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        err_msg = str(e)
        if bot_token:
            err_msg = err_msg.replace(bot_token, "[MASKED_BOT_TOKEN]")
        print(f"Telegram API error: {err_msg}", file=sys.stderr)

def get_open_prs(repo: str, pat: str) -> list:
    url = f"https://api.github.com/repos/{repo}/pulls?state=open"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return [pr for pr in resp.json() if pr["head"]["ref"].startswith("auto/")]

def check_pr_open(pr: dict, repo: str, pat: str) -> bool:
    if pr.get("state") != "open":
        return False
    pr_num = pr["number"]
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("state") == "open"
    return False

def update_telegram_offset(repo: str, pat: str, offset: int):
    url = f"https://api.github.com/repos/{repo}/actions/variables/TELEGRAM_OFFSET"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.patch(url, headers=headers, json={"name": "TELEGRAM_OFFSET", "value": str(offset)})
    if resp.status_code == 404:
        url_create = f"https://api.github.com/repos/{repo}/actions/variables"
        resp_create = requests.post(url_create, headers=headers, json={"name": "TELEGRAM_OFFSET", "value": str(offset)})
        resp_create.raise_for_status()
    else:
        resp.raise_for_status()

def execute_approved_post(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    pr_num = pr["number"]
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    
    # 1. Fetch files modified by PR
    files_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files"
    f_resp = requests.get(files_url, headers=headers)
    f_resp.raise_for_status()
    
    post_files = [
        f for f in f_resp.json()
        if f["filename"].startswith("content/posts/") and f.get("status") != "removed"
    ]
    
    # 2. Flip draft: true -> draft: false on modified post files
    for pf in post_files:
        fn = pf["filename"]
        contents_url = f"https://api.github.com/repos/{repo}/contents/{fn}?ref={pr['head']['ref']}"
        c_resp = requests.get(contents_url, headers=headers)
        c_resp.raise_for_status()
        c_json = c_resp.json()
        
        file_content = base64.b64decode(c_json["content"]).decode("utf-8")
        updated_content = file_content.replace("draft: true", "draft: false")
        
        put_url = f"https://api.github.com/repos/{repo}/contents/{fn}"
        put_payload = {
            "message": f"chore: publish post {fn}",
            "content": base64.b64encode(updated_content.encode("utf-8")).decode("utf-8"),
            "sha": c_json["sha"],
            "branch": pr["head"]["ref"]
        }
        p_resp = requests.put(put_url, headers=headers, json=put_payload)
        p_resp.raise_for_status()
        
    # 3. Merge PR to main (triggers hugo.yml)
    merge_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/merge"
    m_resp = requests.put(merge_url, headers=headers, json={"merge_method": "squash"})
    m_resp.raise_for_status()
    
    # 4. Delete branch
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{pr['head']['ref']}"
    requests.delete(ref_url, headers=headers)
    return True

def execute_approved_audit(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    pr_num = pr["number"]
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    merge_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/merge"
    m_resp = requests.put(merge_url, headers=headers, json={"merge_method": "squash"})
    m_resp.raise_for_status()
    return True

def execute_rejected(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    pr_num = pr["number"]
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    close_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    c_resp = requests.patch(close_url, headers=headers, json={"state": "closed"})
    c_resp.raise_for_status()
    return True

def main():
    creds_json = os.environ.get("CREDENTIALS_JSON")
    pat = os.environ.get("PAT")
    repo = os.environ.get("REPO")
    offset_val = int(os.environ.get("TELEGRAM_OFFSET", "0"))
    
    if not creds_json or not pat or not repo:
        print("Missing required environment variables", file=sys.stderr)
        sys.exit(1)
        
    creds = json.loads(creds_json)
    bot_token = creds["telegram"]["bot_token"]
    chat_id = creds["telegram"]["chat_id"]
    
    # Check open PRs
    open_prs = get_open_prs(repo, pat)
    if len(open_prs) >= 3:
        send_telegram(bot_token, chat_id, f"⚠️ 대기 중인 PR이 {len(open_prs)}건 적체되어 있습니다.")
        
    # Poll Telegram updates (timeout 0)
    updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset_val}&allowed_updates=[\"message\"]"
    u_resp = requests.get(updates_url, timeout=10)
    u_resp.raise_for_status()
    updates = u_resp.json().get("result", [])
    
    last_offset = offset_val
    for up in updates:
        up_id = up["update_id"]
        last_offset = max(last_offset, up_id + 1)
        msg_text = up.get("message", {}).get("text", "")
        
        verdict = parse_verdict(msg_text)
        if verdict == "AMBIGUOUS":
            send_telegram(bot_token, chat_id, f"판정불가: '{msg_text[:40]}' — 승인 또는 반려 로 재답장하세요.")
            continue
            
        target_pr, match_status = match_target_pr(up, open_prs)
        if not target_pr:
            if match_status == "NO_OPEN_PRS":
                send_telegram(bot_token, chat_id, "대기 중인 PR이 없습니다.")
            elif match_status in ["MULTIPLE_PRS_NEED_TOKEN", "TOKEN_NOT_FOUND"]:
                send_telegram(bot_token, chat_id, "대기 중인 PR이 여러 건입니다. 판정 토큰(#PMMDD / #AMMDD)을 포함해 답장하세요.")
            continue
            
        # Execute verdict
        try:
            is_post = target_pr["head"]["ref"].startswith("auto/post-")
            success = False
            if verdict == "APPROVED":
                if is_post:
                    success = execute_approved_post(target_pr, repo, pat)
                    if success:
                        send_telegram(bot_token, chat_id, f"PR #{target_pr['number']} 승인 처리 완료 — 포스트가 게시 및 배포되었습니다.")
                else:
                    success = execute_approved_audit(target_pr, repo, pat)
                    if success:
                        send_telegram(bot_token, chat_id, f"PR #{target_pr['number']} 감사 승인 병합 완료.")
            elif verdict == "REJECTED":
                success = execute_rejected(target_pr, repo, pat)
                if success:
                    send_telegram(bot_token, chat_id, f"PR #{target_pr['number']} 반려 처리 완료 — PR이 닫혔습니다.")
            
            if success:
                open_prs = [p for p in open_prs if p["number"] != target_pr["number"]]
        except Exception as err:
            send_telegram(bot_token, chat_id, f"❌ PR #{target_pr['number']} 처리 중 오류 발생: {err}")
            sys.exit(1)
            
    if last_offset > offset_val:
        update_telegram_offset(repo, pat, last_offset)

if __name__ == "__main__":
    main()
