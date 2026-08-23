import os
import re
import sys
import json
import time
import base64
import requests

from datetime import datetime, timedelta, timezone

from telegram_notify import extract_verdict_token

APPROVED_SET = {"승인", "발행", "게시", "ok", "okay", "go"}
REJECTED_SET = {"반려", "보류", "취소", "폐기", "no"}

# 토큰 없는 답장은 대기 PR이 **2건**부터 매칭에 실패한다(MULTIPLE_PRS_NEED_TOKEN).
BACKLOG_ALERT_THRESHOLD = 2

# 답장이 실제로 처리되기까지 얼마나 걸리는지 사람에게 알려 주는 문장.
# 이 루프는 웹훅이 아니라 폴링이다 — 답장 직후에 아무 일도 일어나지 않는 것이
# 정상인데, 그걸 모르면 "인식되지 않았다"고 읽고 같은 답장을 다시 보낸다.
POLL_NOTE = "판정은 하루 한 번 새벽 정기 실행에서 처리됩니다 — 보낸 직후 조용한 것은 정상입니다."

# 스냅샷·재질의 판정은 언제나 KST 기준이다. 워크플로가 UTC 16시대에 도는데
# UTC 날짜를 쓰면 하루가 어긋난다.
KST = timezone(timedelta(hours=9))

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


def mask(text: str, bot_token: str) -> str:
    """봇 토큰이 오류 문자열을 타고 텔레그램·로그로 새어 나가지 않게 한다."""
    return text.replace(bot_token, "[MASKED_BOT_TOKEN]") if bot_token else text


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


def pr_created_at(pr: dict):
    """PR 생성 시각(UTC). 읽을 수 없으면 None."""
    raw = (pr.get("created_at") or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def overdue_prs(open_prs: list, now=None) -> list:
    """어제(KST) 이전에 만들어졌는데 새벽 회차가 끝난 뒤에도 열려 있는 PR.

    설계상 하루가 한 방향으로 흐르므로(글 PR 05:00 생성 → 사람 답장 → 다음 새벽
    회차가 병합) 그 회차 직후에도 어제 PR이 열려 있으면 정상 상태가 아니다.
    답장이 없었거나 텔레그램 큐에서 유실됐거나인데, 시스템은 둘을 구분할 수 없다 —
    유실된 경우 사람은 답했다고 기억하므로 먼저 물어보지 않으면 아무도 말을
    꺼내지 않는다. 그래서 구분하지 않고 그냥 다시 묻는다.

    **나이(N시간)가 아니라 KST 날짜 경계로 가른다.** 재질의는 새벽 01:3x에 도는데
    어제 05:00에 만들어진 PR은 그 시점에 20시간대다 — "24시간 경과" 규칙을 쓰면
    정작 물어야 할 그 PR이 걸러져 하루 더 밀린다. 반대로 날짜 경계는 오늘 05:00
    루틴이 만든 PR을 같은 날 어떤 시각에 돌려도 건드리지 않는다(수동 실행 포함).
    """
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date()
    out = []
    for pr in open_prs:
        created = pr_created_at(pr)
        # 생성 시각을 못 읽으면 재질의 대상에 넣는다 — 빠뜨리는 쪽이 더 나쁘다.
        if created is None or created.astimezone(KST).date() < today:
            out.append(pr)
    return out


def reask_message(prs: list) -> str:
    """미결 판정 재질의문. 토큰을 반드시 싣는다 — 형식만 알려 주고 목록을 빼면
    어느 토큰을 써야 하는지 알 수 없어 왕복이 하루씩 늘어난다."""
    if len(prs) == 1:
        how = "승인 또는 반려 로 답장하세요."
    else:
        how = ("2건 이상이라 토큰이 필요합니다.\n"
               f"예: 승인 {pr_token(prs[0])} / 반려 {pr_token(prs[0])}")
    return ("⚠️ 하루가 지나도 판정되지 않은 PR이 있습니다. "
            "앞서 답장을 보내셨다면 전달되지 못하고 유실된 것입니다 — 다시 보내주세요.\n\n"
            f"{pending_pr_lines(prs)}\n\n"
            f"{how}\n\n{POLL_NOTE}")


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
        print(f"Telegram API error: {mask(str(e), bot_token)}", file=sys.stderr)

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


def set_repo_variable(repo: str, pat: str, name: str, value: str):
    """저장소 Actions 변수를 쓴다. 없으면 만든다."""
    url = f"https://api.github.com/repos/{repo}/actions/variables/{name}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.patch(url, headers=headers, json={"name": name, "value": value}, timeout=10)
    if resp.status_code == 404:
        url_create = f"https://api.github.com/repos/{repo}/actions/variables"
        resp_create = requests.post(url_create, headers=headers, json={"name": name, "value": value}, timeout=10)
        resp_create.raise_for_status()
    else:
        resp.raise_for_status()


def get_repo_variable(repo: str, pat: str, name: str) -> str:
    """저장소 Actions 변수를 읽는다. 없으면 빈 문자열."""
    url = f"https://api.github.com/repos/{repo}/actions/variables/{name}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        return ""
    resp.raise_for_status()
    return resp.json().get("value", "")


def update_telegram_offset(repo: str, pat: str, offset: int):
    set_repo_variable(repo, pat, "TELEGRAM_OFFSET", str(offset))


# ── 미집행 판정 원장 ───────────────────────────────────────────────────────
# 집행에 실패한 판정을 텔레그램 큐 **바깥에** 적어 둔다.
#
# 원래 설계는 "실패하면 오프셋을 넘기지 않는다"였고 의도대로 동작했지만, 이 루프는
# 하루 한 번 돈다. 텔레그램은 확인되지 않은 업데이트를 24시간만 보관하므로 재시도
# 기회가 오는 시점에는 보존해 둔 그 업데이트가 이미 삭제돼 있다 — 안전장치가 구조적으로
# 한 번도 성립할 수 없었다. 2026-08-20 회차의 '승인 #P0819'가 정확히 그렇게 사라졌다.
#
# 그래서 판정을 저장소 변수에 옮겨 적고 오프셋은 정상적으로 소비한다. 다음 회차가
# 텔레그램과 무관하게 원장을 먼저 재집행한다.
PENDING_VERDICTS_VAR = "PENDING_VERDICTS"


class VerdictExecutionError(Exception):
    """집행 단계에서 실패한 판정. 어느 PR의 어떤 판정이었는지를 들고 다닌다 —
    메시지 문자열에서 다시 파싱하면 원장에 적을 수 없다."""

    def __init__(self, pr: dict, verdict: str, detail: str):
        super().__init__(f"PR #{pr.get('number')} — {detail}")
        self.pr = pr
        self.verdict = verdict
        self.detail = detail


def load_pending_verdicts(repo: str, pat: str) -> list:
    raw = (get_repo_variable(repo, pat, PENDING_VERDICTS_VAR) or "").strip()
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except ValueError:
        # 읽을 수 없는 원장은 버리지 않고 비운 뒤 알린다 — 조용히 무시하면
        # 승인이 또 사라진 것과 구분되지 않는다.
        log(f"  원장을 해석할 수 없다 (내용 {raw[:80]!r}) — 빈 원장으로 시작한다")
        return []
    return entries if isinstance(entries, list) else []


def save_pending_verdicts(repo: str, pat: str, entries: list):
    set_repo_variable(repo, pat, PENDING_VERDICTS_VAR, json.dumps(entries, ensure_ascii=False))


def record_pending_verdict(entries: list, pr: dict, verdict: str, detail: str, now=None) -> list:
    """실패한 판정을 원장에 적는다. 같은 PR이 이미 있으면 시도 횟수만 올린다."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    found = False
    for e in entries:
        if e.get("pr") == pr.get("number"):
            found = True
            out.append({**e,
                        "verdict": verdict,
                        "attempts": int(e.get("attempts", 1)) + 1,
                        "last_error": detail,
                        "last_failed_at": stamp})
        else:
            out.append(e)
    if not found:
        out.append({"pr": pr.get("number"),
                    "branch": pr.get("head", {}).get("ref", ""),
                    "verdict": verdict,
                    "attempts": 1,
                    "last_error": detail,
                    "first_failed_at": stamp,
                    "last_failed_at": stamp})
    return out


def drop_settled_verdicts(entries: list, open_prs: list) -> list:
    """열려 있지 않은 PR의 원장 항목은 버린다 — 사람이 손으로 병합·반려했을 수 있다."""
    open_numbers = {p["number"] for p in open_prs}
    return [e for e in entries if e.get("pr") in open_numbers]


def resolve_terms_conflict(content: str) -> str | None:
    """git 충돌 마커를 해소하고 양쪽 버전을 합친다. 
    만약 슬러그가 중복되면 None을 반환해 병합을 거부한다."""
    lines = content.splitlines()
    out = []
    
    for line in lines:
        if line.startswith("<<<<<<< "): continue
        if line.startswith("======="): continue
        if line.startswith(">>>>>>> "): continue
        out.append(line)
        
    # 중복 키 검사
    seen = set()
    for line in out:
        m = re.match(r"^([a-z0-9][a-z0-9-]*):\s*$", line)
        if m:
            if m.group(1) in seen:
                return None
            seen.add(m.group(1))
            
    # 표제어 사이 빈 줄 규약 복원
    text = "\n".join(out)
    text = re.sub(r'\n+([a-z0-9][a-z0-9-]*:\s*\n)', r'\n\n\1', text)
    return text.strip() + "\n"

def auto_resolve_terms_conflict_git(repo: str, pr: dict, pat: str) -> bool:
    import tempfile
    import subprocess
    import os
    branch = pr["head"]["ref"]
    remote_url = f"https://x-access-token:{pat}@github.com/{repo}.git"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # `--depth=1`을 쓰면 안 된다. 브랜치와 main을 각각 깊이 1로 받으면 두 히스토리에
        # 공통 조상이 없어 `git merge`가 "refusing to merge unrelated histories"로 죽는다.
        # 병합이 시작조차 못 하므로 충돌 파일이 스테이지되지 않고, 아래 `--diff-filter=U`가
        # 빈 목록을 돌려줘 이 함수가 조용히 False를 반환한다 — 정작 해소 가능한 충돌인데도.
        # 2026-08-20 회차의 PR #25가 그렇게 막혔고, 보존된 판정이 다음 회차까지 살지 못해
        # 승인이 통째로 증발했다. blob은 lazy로 받아 전송량은 얕은 클론 수준으로 유지한다.
        subprocess.run(["git", "clone", "--filter=blob:none", "--branch", branch, remote_url, tmpdir], check=True, capture_output=True)
        subprocess.run(["git", "remote", "set-branches", "origin", "main"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "fetch", "origin", "main"], cwd=tmpdir, check=True, capture_output=True)

        subprocess.run(["git", "config", "user.name", "bjh7790"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "bjh7790@gmail.com"], cwd=tmpdir, check=True)

        # 공통 조상을 실제로 확인한다. 없으면 병합이 아니라 클론 방식이 잘못된 것이므로
        # 조용히 포기하지 말고 이유를 남긴다 — 위 버그가 3일 동안 안 보였던 이유가 침묵이었다.
        base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=tmpdir, capture_output=True, text=True)
        if base.returncode != 0:
            log(f"  자동 해소 포기: HEAD와 origin/main의 공통 조상을 찾지 못했다 ({base.stderr.strip()})")
            return False

        res = subprocess.run(["git", "merge", "origin/main", "--no-commit", "--no-ff"], cwd=tmpdir, capture_output=True, text=True)
        if res.returncode != 0:
            conflicts = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=tmpdir, capture_output=True, text=True, check=True).stdout.splitlines()
            if conflicts != ["content/dictionary/_terms.yaml"]:
                log(f"  자동 해소 포기: _terms.yaml 외의 충돌 {conflicts or '(없음 — 병합이 시작되지 못했다)'}"
                    f" / git: {res.stderr.strip()}")
                return False

            terms_path = os.path.join(tmpdir, "content/dictionary/_terms.yaml")
            with open(terms_path, "r", encoding="utf-8") as f:
                content = f.read()

            resolved = resolve_terms_conflict(content)
            if not resolved:
                log("  자동 해소 포기: 양쪽에 같은 슬러그가 있어 합칠 수 없다")
                return False

            with open(terms_path, "w", encoding="utf-8") as f:
                f.write(resolved)

            subprocess.run(["git", "add", "content/dictionary/_terms.yaml"], cwd=tmpdir, check=True)

        # 스테이지가 비어 있으면(이미 main을 담고 있는 브랜치) commit이 check=True에 걸려
        # 죽는다. 그건 충돌이 아니라 애초에 병합할 것이 없었던 경우다.
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=tmpdir)
        if staged.returncode == 0:
            log("  자동 해소 포기: 병합할 변경이 없다 (dirty의 원인이 _terms.yaml이 아니다)")
            return False

        subprocess.run(["git", "commit", "-m", "chore: auto-resolve _terms.yaml conflict"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", branch], cwd=tmpdir, check=True, capture_output=True)
        log(f"  _terms.yaml 충돌 자동 해소 완료 — {branch} 푸시함")
        return True

def flip_front_matter_draft(content: str) -> str:
    def replace_draft(match):
        fm = match.group(1)
        fm_updated = re.sub(r'(?m)^draft:\s*true\b', 'draft: false', fm)
        return f"---\n{fm_updated}\n---"
    return re.sub(r'^---\s*\n(.*?)\n---', replace_draft, content, count=1, flags=re.DOTALL)

def execute_approved_post(pr: dict, repo: str, pat: str, bot_token: str, chat_id: str) -> bool:
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
    try:
        merge_pr(repo, pr_num, pat)
    except RuntimeError as err:
        if "dirty" in str(err) and auto_resolve_terms_conflict_git(repo, pr, pat):
            send_telegram(bot_token, chat_id, f"PR #{pr_num} _terms.yaml 충돌 자동 해소됨 — 병합 재시도")
            merge_pr(repo, pr_num, pat)
        else:
            raise err

    # 4. Delete branch
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{pr['head']['ref']}"
    requests.delete(ref_url, headers=headers, timeout=10)
    return True

def execute_approved_audit(pr: dict, repo: str, pat: str) -> bool:
    if not check_pr_open(pr, repo, pat):
        print(f"PR #{pr.get('number')} is not open; skipping execution.", file=sys.stderr)
        return False
    merge_pr(repo, pr["number"], pat)
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{pr['head']['ref']}"
    requests.delete(ref_url, headers=headers, timeout=10)
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
    ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{pr['head']['ref']}"
    requests.delete(ref_url, headers=headers, timeout=10)
    return True

def execute_verdict(pr: dict, verdict: str, repo: str, pat: str, bot_token: str, chat_id: str) -> bool:
    """판정 하나를 집행한다. 텔레그램에서 갓 읽은 판정과 원장에서 재시도하는 판정이
    같은 경로를 타야 한다 — 갈라 두면 재시도만 조용히 다르게 동작한다.

    실패하면 VerdictExecutionError를 올린다(호출자가 원장에 적는다)."""
    is_post = pr["head"]["ref"].startswith("auto/post-")
    try:
        if verdict == "APPROVED":
            if is_post:
                if execute_approved_post(pr, repo, pat, bot_token, chat_id):
                    send_telegram(bot_token, chat_id, f"PR #{pr['number']} 승인 처리 완료 — 포스트가 게시 및 배포되었습니다.")
                    return True
            else:
                if execute_approved_audit(pr, repo, pat):
                    send_telegram(bot_token, chat_id, f"PR #{pr['number']} 감사 승인 병합 완료.")
                    return True
        elif verdict == "REJECTED":
            if execute_rejected(pr, repo, pat):
                send_telegram(bot_token, chat_id, f"PR #{pr['number']} 반려 처리 완료 — PR이 닫혔습니다.")
                return True
    except Exception as err:
        raise VerdictExecutionError(pr, verdict, str(err)) from err
    return False


def retry_pending_verdicts(entries: list, open_prs: list, repo: str, pat: str,
                           bot_token: str, chat_id: str) -> tuple:
    """원장에 남은 판정을 텔레그램과 무관하게 재집행한다.

    (남은 원장, 갱신된 대기 PR 목록, 실패 여부)를 돌려준다."""
    by_number = {p["number"]: p for p in open_prs}
    remaining = []
    failed = False
    for entry in entries:
        pr = by_number.get(entry.get("pr"))
        if pr is None:
            continue  # drop_settled_verdicts가 이미 걸렀어야 하지만 방어적으로 둔다
        verdict = entry.get("verdict", "APPROVED")
        log(f"  원장 재집행: PR #{pr['number']} {verdict} (시도 {entry.get('attempts', 1)}회차)")
        try:
            if execute_verdict(pr, verdict, repo, pat, bot_token, chat_id):
                open_prs = [p for p in open_prs if p["number"] != pr["number"]]
                log(f"  원장 재집행 성공: PR #{pr['number']} — 원장에서 제거")
                continue
            remaining.append(entry)
        except VerdictExecutionError as err:
            failed = True
            detail = mask(str(err.detail), bot_token)
            remaining = record_pending_verdict(remaining + [entry], pr, verdict, detail)
            attempts = next((e.get("attempts") for e in remaining if e.get("pr") == pr["number"]), "?")
            send_telegram(bot_token, chat_id,
                          f"❌ PR #{pr['number']} 판정 재집행 실패 ({attempts}회차): {detail}\n\n"
                          f"판정은 원장에 남아 있어 다음 회차에 다시 시도합니다. "
                          f"계속 실패하면 사람이 직접 처리해야 합니다.")
    return remaining, open_prs, failed


def handle_update(up: dict, open_prs: list, repo: str, pat: str, bot_token: str, chat_id: str) -> list:
    """업데이트 1건을 처리하고 갱신된 대기 PR 목록을 돌려준다.

    집행이 실패하면 VerdictExecutionError를 올린다 — 호출자가 판정을 원장에 적고
    오프셋은 소비한다(오프셋을 붙들어 봐야 텔레그램이 24시간 뒤에 지운다).
    그 앞 단계(매칭·통신)의 실패는 적어 둘 판정이 없으므로 일반 예외로 올라가고,
    호출자가 오프셋을 붙든 채 멈춘다.
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

    if execute_verdict(target_pr, verdict, repo, pat, bot_token, chat_id):
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
    
    # Check open PRs
    open_prs = get_open_prs(repo, pat)
    log(f"open auto/* PRs: {len(open_prs)} → {[p['number'] for p in open_prs]}")

    pending = drop_settled_verdicts(load_pending_verdicts(repo, pat), open_prs)
    log(f"미집행 판정 원장: {len(pending)} → {[e.get('pr') for e in pending]}")

    # 재질의 전용 모드 — 텔레그램 큐를 읽지 않는다. 오프셋을 소비하지 않으므로
    # 아침 재질의가 새벽 회차의 판정을 가로채는 일이 없다.
    if "--reask" in sys.argv:
        # 원장에 있는 PR은 빼고 묻는다. 이미 승인을 받아 재시도 중인 건이라
        # 다시 물으면 "승인했는데 또 물어본다"가 된다 — 재집행 실패는 인박스가
        # 자기 경보로 이미 알렸다.
        queued = {e.get("pr") for e in pending}
        due = [p for p in overdue_prs(open_prs) if p["number"] not in queued]
        log(f"재질의 대상: {len(due)} → {[p['number'] for p in due]} (원장 대기 {sorted(queued)} 제외)")
        if due:
            send_telegram(bot_token, chat_id, reask_message(due))
        return

    # 원장을 텔레그램보다 **먼저** 처리한다. 여기 있는 판정은 이미 사람이 내린 것이고
    # 텔레그램 큐에서는 이미 사라졌으므로, 이 경로가 유일한 집행 기회다.
    ledger_failed = False
    if pending:
        before = list(pending)
        pending, open_prs, ledger_failed = retry_pending_verdicts(
            pending, open_prs, repo, pat, bot_token, chat_id)
        if pending != before:
            save_pending_verdicts(repo, pat, pending)

    # Poll Telegram updates (timeout 10)
    try:
        updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset_val}&allowed_updates=[\"message\"]"
        u_resp = requests.get(updates_url, timeout=10)
        u_resp.raise_for_status()
        updates = u_resp.json().get("result", [])
        log(f"getUpdates offset={offset_val} → {len(updates)}건")
    except Exception as e:
        print(f"Telegram API getUpdates failed: {mask(str(e), bot_token)}", file=sys.stderr)
        sys.exit(1)

    last_offset = offset_val
    failed = ledger_failed
    try:
        for up in updates:
            up_id = up["update_id"]
            try:
                open_prs = handle_update(up, open_prs, repo, pat, bot_token, chat_id)
            except VerdictExecutionError as err:
                detail = mask(str(err.detail), bot_token)
                # 판정을 원장에 **먼저** 적고, 그 다음에 오프셋을 소비한다. 순서가 반대면
                # 원장 쓰기가 실패했을 때 판정이 사라진다. 오프셋을 붙들고 있어 봐야
                # 텔레그램이 24시간 뒤에 지우므로(하루 1회 폴링) 보존이 되지 않는다.
                pending = record_pending_verdict(pending, err.pr, err.verdict, detail)
                save_pending_verdicts(repo, pat, pending)
                send_telegram(bot_token, chat_id,
                              f"❌ 판정 처리 중 오류 발생: {mask(str(err), bot_token)}\n\n"
                              f"판정은 원장에 적어 두었습니다 — 다음 회차가 텔레그램과 무관하게 다시 시도합니다.")
                failed = True
            except Exception as err:
                # 집행 이전 단계(매칭·통신)의 오류는 적어 둘 판정이 없다. 이때만
                # 오프셋을 붙들고 멈춘다.
                send_telegram(bot_token, chat_id, f"❌ 판정 처리 중 오류 발생: {mask(str(err), bot_token)}")
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

