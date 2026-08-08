import os
import re
import sys
import json
import time
import base64
import requests

from telegram_notify import extract_verdict_token

APPROVED_SET = {"승인", "발행", "게시", "ok", "okay", "go"}
REJECTED_SET = {"반려", "보류", "취소", "폐기", "no"}

# 토큰 없는 답장은 대기 PR이 **2건**부터 매칭에 실패한다(MULTIPLE_PRS_NEED_TOKEN).
# 경보를 3건에 두면 이미 하루치 판정을 날린 뒤에 울린다.
BACKLOG_ALERT_THRESHOLD = 2

# 답장이 실제로 처리되기까지 얼마나 걸리는지 사람에게 알려 주는 문장.
# 이 루프는 웹훅이 아니라 폴링이다 — 답장 직후에 아무 일도 일어나지 않는 것이
# 정상인데, 그걸 모르면 "인식되지 않았다"고 읽고 같은 답장을 다시 보낸다.
POLL_NOTE = "답장은 15분마다 한 번씩 처리됩니다 — 보낸 직후 조용한 것은 정상입니다."

# 병합 방식 우선순위. 저장소가 squash를 막아 두면 405가 영구로 돌아오므로 다음 방식으로 내린다.
MERGE_METHODS = ("squash", "merge")
# GitHub는 `mergeable`을 비동기로 계산한다. 방금 커밋을 민 직후에는 null이고,
# 그 상태의 PUT /merge는 멀쩡한 PR에도 405를 준다.
MERGEABLE_POLL_ATTEMPTS = 8
MERGEABLE_POLL_DELAY = 3
MERGE_RETRY_ATTEMPTS = 3
MERGE_RETRY_DELAY = 3

def log(msg: str):
    """실행 로그. 이 스크립트는 오랫동안 아무것도 출력하지 않았고, 그래서
    '판정이 왜 처리되지 않았나'를 Actions 로그만으로는 답할 수 없었다 —
    성공한 회차와 업데이트가 0건이던 회차가 로그상 구분되지 않았다."""
    print(msg, flush=True)


def parse_verdict(text: str) -> str:
    cleaned = re.sub(r'#([paPA])\d{4}', '', text).strip().lower()
    if cleaned in APPROVED_SET:
        return "APPROVED"
    if cleaned in REJECTED_SET:
        return "REJECTED"
    return "AMBIGUOUS"

def pr_token(pr: dict) -> str:
    """대기 PR의 판정 토큰. 형식은 알림을 만드는 함수에서 그대로 가져온다 —
    여기서 다시 만들면 사람이 알림에서 본 토큰과 갈린다."""
    ref = pr["head"]["ref"]
    return extract_verdict_token(ref, "post" if ref.startswith("auto/post-") else "audit")


def pending_pr_lines(open_prs: list) -> str:
    """대기 PR을 토큰과 함께 나열한다. 토큰 형식만 알려 주고 목록을 빼면 사람이
    어느 토큰을 써야 하는지 알 수 없어 왕복이 하루씩 늘어난다."""
    lines = []
    for pr in open_prs:
        ref = pr["head"]["ref"]
        kind = "포스트" if ref.startswith("auto/post-") else "감사"
        lines.append(f"{pr_token(pr)} — {kind} PR #{pr['number']} ({ref})")
    return "\n".join(lines)


def match_target_pr(update: dict, open_prs: list) -> tuple:
    msg = update.get("message", {})
    text = msg.get("text", "")
    reply_text = msg.get("reply_to_message", {}).get("text", "")

    # 1. Check reply token
    # 사람이 직접 친 토큰이 답장 대상의 토큰을 이긴다. 대기 목록 안내 메시지에는
    # 토큰이 여러 개 실려 있어서, 거기에 답장하며 토큰을 치면 답장 우선일 때
    # 목록의 첫 토큰(= 다른 글)이 병합된다.
    text_match = re.search(r'#([paPA])(\d{4})', text)
    token_match = text_match or re.search(r'#([paPA])(\d{4})', reply_text)

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
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return [pr for pr in resp.json() if pr["head"]["ref"].startswith("auto/")]

def check_pr_open(pr: dict, repo: str, pat: str) -> bool:
    if pr.get("state") != "open":
        return False
    pr_num = pr["number"]
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("state") == "open"
    return False

def api_error_detail(resp) -> str:
    """GitHub가 준 이유를 살려 둔다. raise_for_status()는 상태줄만 남기고 본문을 버린다."""
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    message = payload.get("message", "") if isinstance(payload, dict) else ""
    return f"{resp.status_code} {message}".strip()


def merge_method_rejected(detail: str) -> bool:
    """405가 '이 방식은 이 저장소에서 못 쓴다'인지, '아직 병합 가능하지 않다'인지 가른다."""
    lowered = detail.lower()
    return "merges are not allowed" in lowered or "merge method" in lowered


def wait_until_mergeable(repo: str, pr_num: int, pat: str, sleep=time.sleep) -> tuple:
    """(상태, 사유, PR) — 상태는 READY · BLOCKED · UNKNOWN."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    pr = None
    for attempt in range(MERGEABLE_POLL_ATTEMPTS):
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        pr = resp.json()
        if pr.get("state") != "open":
            return ("BLOCKED", f"PR이 열려 있지 않다 (state={pr.get('state')})", pr)
        mergeable = pr.get("mergeable")
        if mergeable is True:
            return ("READY", "", pr)
        if mergeable is False:
            return ("BLOCKED", f"병합 불가 (mergeable_state={pr.get('mergeable_state')})", pr)
        if attempt < MERGEABLE_POLL_ATTEMPTS - 1:
            sleep(MERGEABLE_POLL_DELAY)
    return ("UNKNOWN", "mergeable 계산이 끝나지 않았다", pr)


def merge_pr(repo: str, pr_num: int, pat: str, sleep=time.sleep):
    """PR을 병합한다. 실패하면 GitHub가 준 사유를 담아 RuntimeError를 낸다."""
    status, reason, pr = wait_until_mergeable(repo, pr_num, pat, sleep=sleep)
    if status == "BLOCKED":
        raise RuntimeError(f"PR #{pr_num} 병합 중단: {reason}")

    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    merge_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/merge"
    head_sha = (pr or {}).get("head", {}).get("sha")
    last_detail = reason or "사유 없음"

    for method in MERGE_METHODS:
        for attempt in range(MERGE_RETRY_ATTEMPTS):
            payload = {"merge_method": method}
            if head_sha:
                payload["sha"] = head_sha
            resp = requests.put(merge_url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                return
            last_detail = api_error_detail(resp)
            if resp.status_code == 409:
                # 우리가 본 것과 다른 head다. 다시 읽어 그 sha로 재시도한다.
                status, reason, pr = wait_until_mergeable(repo, pr_num, pat, sleep=sleep)
                if status == "BLOCKED":
                    raise RuntimeError(f"PR #{pr_num} 병합 중단: {reason}")
                head_sha = (pr or {}).get("head", {}).get("sha")
                continue
            if resp.status_code == 405:
                if merge_method_rejected(last_detail):
                    break  # 다음 병합 방식으로
                if attempt < MERGE_RETRY_ATTEMPTS - 1:
                    sleep(MERGE_RETRY_DELAY)
                continue
            raise RuntimeError(f"PR #{pr_num} 병합 실패: {last_detail}")

    raise RuntimeError(f"PR #{pr_num} 병합 실패: {last_detail}")


def update_telegram_offset(repo: str, pat: str, offset: int):
    url = f"https://api.github.com/repos/{repo}/actions/variables/TELEGRAM_OFFSET"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.patch(url, headers=headers, json={"name": "TELEGRAM_OFFSET", "value": str(offset)}, timeout=10)
    if resp.status_code == 404:
        url_create = f"https://api.github.com/repos/{repo}/actions/variables"
        resp_create = requests.post(url_create, headers=headers, json={"name": "TELEGRAM_OFFSET", "value": str(offset)}, timeout=10)
        resp_create.raise_for_status()
    else:
        resp.raise_for_status()

def flip_front_matter_draft(content: str) -> str:
    def replace_draft(match):
        fm = match.group(1)
        fm_updated = re.sub(r'(?m)^draft:\s*true\b', 'draft: false', fm)
        return f"---\n{fm_updated}\n---"
    return re.sub(r'^---\s*\n(.*?)\n---', replace_draft, content, count=1, flags=re.DOTALL)

def execute_approved_post(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    pr_num = pr["number"]
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    
    # 1. Fetch files modified by PR under content/posts/ or content/dictionary/
    files_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}/files"
    f_resp = requests.get(files_url, headers=headers, timeout=10)
    f_resp.raise_for_status()
    
    target_files = [
        f for f in f_resp.json()
        if (f["filename"].startswith("content/posts/") or f["filename"].startswith("content/dictionary/"))
        and f["filename"].endswith(".md")
        and f.get("status") != "removed"
    ]
    
    # 2. Flip draft: true -> draft: false in front matter for modified post & dictionary files
    for pf in target_files:
        fn = pf["filename"]
        contents_url = f"https://api.github.com/repos/{repo}/contents/{fn}?ref={pr['head']['ref']}"
        c_resp = requests.get(contents_url, headers=headers, timeout=10)
        c_resp.raise_for_status()
        c_json = c_resp.json()
        
        file_content = base64.b64decode(c_json["content"]).decode("utf-8")
        updated_content = flip_front_matter_draft(file_content)
        
        put_url = f"https://api.github.com/repos/{repo}/contents/{fn}"
        put_payload = {
            "message": f"chore: publish {fn}",
            "content": base64.b64encode(updated_content.encode("utf-8")).decode("utf-8"),
            "sha": c_json["sha"],
            "branch": pr["head"]["ref"]
        }
        p_resp = requests.put(put_url, headers=headers, json=put_payload, timeout=10)
        p_resp.raise_for_status()
        
    # 3. Merge PR to main (triggers hugo.yml)
    merge_pr(repo, pr_num, pat)

    # 4. Delete branch
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{pr['head']['ref']}"
    requests.delete(ref_url, headers=headers, timeout=10)
    return True

def execute_approved_audit(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    merge_pr(repo, pr["number"], pat)
    return True

def execute_rejected(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    pr_num = pr["number"]
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    close_url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
    c_resp = requests.patch(close_url, headers=headers, json={"state": "closed"}, timeout=10)
    c_resp.raise_for_status()
    return True

def handle_update(up: dict, open_prs: list, repo: str, pat: str, bot_token: str, chat_id: str) -> list:
    """업데이트 1건을 처리하고 갱신된 대기 PR 목록을 돌려준다.

    실행이 실패하면 예외를 올린다 — 호출자가 그 업데이트를 소비하지 않고 멈춘다.
    """
    msg_obj = up.get("message", {})
    up_chat_id = msg_obj.get("chat", {}).get("id")

    # C1: Strict Chat ID validation
    # 조용히 버리되 로그에는 남긴다 — 설정된 chat_id가 틀리면 모든 답장이
    # 아무 반응 없이 사라지고, 로그가 없으면 그 사실을 알 방법이 없다.
    if str(up_chat_id) != str(chat_id):
        log(f"  update {up.get('update_id')}: chat_id 불일치 — 무시")
        return open_prs

    msg_text = msg_obj.get("text", "")

    verdict = parse_verdict(msg_text)
    log(f"  update {up.get('update_id')}: text={msg_text[:40]!r} verdict={verdict}")
    if verdict == "AMBIGUOUS":
        send_telegram(bot_token, chat_id, f"판정불가: '{msg_text[:40]}' — 승인 또는 반려 로 재답장하세요.")
        return open_prs

    target_pr, match_status = match_target_pr(up, open_prs)
    log(f"  update {up.get('update_id')}: match={match_status} "
        f"pr={target_pr['number'] if target_pr else None}")
    if not target_pr:
        if match_status == "NO_OPEN_PRS":
            send_telegram(bot_token, chat_id, "대기 중인 PR이 없습니다.")
        elif match_status == "TOKEN_NOT_FOUND":
            # 토큰이 붙어 있으면 대기 PR이 0건이어도 이 분기로 온다 — 목록이 비면
            # 헤더만 남아 "대기 중:" 뒤가 공백인 메시지가 나간다.
            tail = f"\n\n대기 중:\n{pending_pr_lines(open_prs)}" if open_prs else ""
            send_telegram(bot_token, chat_id,
                          f"지정한 토큰과 일치하는 대기 PR이 없습니다.{tail}")
        elif match_status == "MULTIPLE_PRS_NEED_TOKEN":
            send_telegram(bot_token, chat_id,
                          f"대기 중인 PR이 {len(open_prs)}건입니다. 아래 토큰 중 하나를 붙여 다시 보내세요.\n\n"
                          f"{pending_pr_lines(open_prs)}\n\n"
                          f"예: 승인 {pr_token(open_prs[0])} / 반려 {pr_token(open_prs[0])}\n\n"
                          f"{POLL_NOTE}")
        return open_prs

    is_post = target_pr["head"]["ref"].startswith("auto/post-")
    success = False
    try:
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
    except Exception as err:
        raise RuntimeError(f"PR #{target_pr['number']} — {err}") from err

    if success:
        return [p for p in open_prs if p["number"] != target_pr["number"]]
    return open_prs


def main():
    creds_json = os.environ.get("CREDENTIALS_JSON")
    pat = os.environ.get("PAT")
    repo = os.environ.get("REPO")
    raw_offset = os.environ.get("TELEGRAM_OFFSET", "").strip()
    offset_val = int(raw_offset) if raw_offset.isdigit() else 0
    
    if not creds_json or not pat or not repo:
        print("Missing required environment variables", file=sys.stderr)
        sys.exit(1)
        
    creds = json.loads(creds_json)
    bot_token = creds["telegram"]["bot_token"]
    chat_id = creds["telegram"]["chat_id"]
    
    # 적체 경보는 하루 한 번 도는 호출자(daily-collect)만 켠다. 15분 폴링이
    # 같은 경보를 내면 하루 96통이 되어 사람이 읽기를 그만둔다.
    alert_backlog = os.environ.get("ALERT_BACKLOG", "").strip().lower() in ("1", "true", "yes")

    # Check open PRs
    open_prs = get_open_prs(repo, pat)
    log(f"open auto/* PRs: {len(open_prs)} → {[p['number'] for p in open_prs]}")
    if alert_backlog and len(open_prs) >= BACKLOG_ALERT_THRESHOLD:
        send_telegram(bot_token, chat_id,
                      f"⚠️ 대기 중인 PR이 {len(open_prs)}건 적체되어 있습니다. "
                      "이제부터는 토큰 없는 답장이 처리되지 않습니다.\n\n"
                      f"{pending_pr_lines(open_prs)}\n\n"
                      f"{POLL_NOTE}")

    # Poll Telegram updates (timeout 10)
    try:
        updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset_val}&allowed_updates=[\"message\"]"
        u_resp = requests.get(updates_url, timeout=10)
        u_resp.raise_for_status()
        updates = u_resp.json().get("result", [])
        log(f"getUpdates offset={offset_val} → {len(updates)}건")
    except Exception as e:
        err_msg = str(e)
        if bot_token:
            err_msg = err_msg.replace(bot_token, "[MASKED_BOT_TOKEN]")
        print(f"Telegram API getUpdates failed: {err_msg}", file=sys.stderr)
        sys.exit(1)
    
    last_offset = offset_val
    failed = False
    try:
        for up in updates:
            up_id = up["update_id"]
            try:
                open_prs = handle_update(up, open_prs, repo, pat, bot_token, chat_id)
            except Exception as err:
                err_str = str(err)
                if bot_token:
                    err_str = err_str.replace(bot_token, "[MASKED_BOT_TOKEN]")
                send_telegram(bot_token, chat_id, f"❌ 판정 처리 중 오류 발생: {err_str}")
                # 이 업데이트는 소비하지 않는다 — 오프셋을 넘기면 판정이 통째로 사라진다.
                failed = True
                break
            last_offset = max(last_offset, up_id + 1)
    finally:
        if last_offset > offset_val:
            log(f"offset {offset_val} → {last_offset}")
            update_telegram_offset(repo, pat, last_offset)
        else:
            log(f"offset 유지 {offset_val} (소비한 업데이트 없음)")
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()

