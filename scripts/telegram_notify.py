"""텔레그램 발신부.

2026-08-27 무인 운영 전환 이후 이 스크립트가 보내는 메시지는 **세 종류뿐**이며
셋 다 통보이지 질문이 아니다 — 승인/반려 판정을 묻는 경로는 없어졌다.

| 모드 | 트리거 | 내용 |
|---|---|---|
| `post` | `notify-post.yml` (main 푸시 · `content/posts/**`) | 오늘 발행된 글 본문 |
| `health` | `notify-health.yml` (main 푸시 · `report/health-*.md`) | 격주 점검 중 사람이 알아야 할 것만 |
| `alert` | 수집 워크플로 실패 | 자동화 경보 |

주간 유지보수(`weekly-housekeeping.yml`)는 **어떤 메시지도 보내지 않는다.** 순수
결정론 패스라 사람이 읽고 할 일이 없고, 실패는 격주 점검이 집어낸다.

판정 토큰(`#P0827`)을 만드는 함수가 여기 있었지만 승인 루프와 함께 제거했다.
다시 넣지 않는다 — 받는 쪽(`process_inbox.py`)이 더 이상 존재하지 않아서
사용자가 답장해도 아무 일도 일어나지 않는다.
"""

import os
import re
import sys
import json
import requests

SITE_BASE = "https://econ-blog.github.io"

# 텔레그램 텍스트 메시지 상한은 4096자다. UTF-8 바이트가 아니라 문자 수이며,
# 넘기면 400 Bad Request로 통째로 실패한다 — 잘라 보내는 쪽이 낫다.
TELEGRAM_TEXT_LIMIT = 3500

LEADING_BULLET = re.compile(r'^[-*\s]+')
SUMMARY_FIELD = re.compile(r'^([^:\n]{1,20}):\s*(\S.*)$')
DECISION_DIVIDER = re.compile(r'^[─-]+\s*사람이 해야 할 일\s*[─-]*$')


# ── 커밋 메시지 본문 파싱 ──────────────────────────────────────────────────

def extract_block(body: str, heading: str) -> list:
    """`## <heading>` 아래부터 다음 `## `까지의 줄을 돌려준다.

    커밋 메시지 본문에서 요약 블록만 떼어 낸다. 헤딩 범위로 자르는 이유는 리포트
    산문이 딸려 들어오는 것을 막기 위해서다 — 예전 구현은 고정 키 목록으로 걸렀는데,
    키가 하나 늘 때마다 스크립트를 같이 고쳐야 했고 실제로 한쪽만 고쳐 요약이 반쪽이
    된 적이 있다.
    """
    out, inside = [], False
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == heading
            continue
        if inside and line:
            out.append(line)
    return out


# 배선용 필드 — 워크플로와 이 스크립트가 읽으려고 있는 줄이지 사람에게 보여줄 내용이
# 아니다. `알림:`은 발신 스위치이고(받은 사람은 이미 받았으므로 자명하다), `리포트:`는
# 아래에서 클릭 가능한 URL로 다시 붙는다.
ROUTING_FIELDS = ("알림", "리포트", "상태", "사유")


def summarize_block(lines: list, limit: int = 12) -> str:
    """요약 블록에서 알림에 실을 줄만 남긴다.

    `키: 값` 줄과, 「사람이 해야 할 일」 구분선 **뒤에** 오는 불릿만 싣는다.
    구분선 앞의 불릿은 산문이라 뺀다.
    """
    kept, in_decision = [], False
    for line in lines:
        if DECISION_DIVIDER.match(line):
            in_decision = True
            kept.append(line)
        elif in_decision and line[:1] in ("*", "-"):
            kept.append(LEADING_BULLET.sub("• ", line))
        else:
            m = SUMMARY_FIELD.match(line)
            if m and m.group(1).strip() not in ROUTING_FIELDS:
                kept.append(line)
    return "\n".join(kept[:limit]) if kept else "요약 정보 없음"


def field(lines: list, key: str, default: str = "") -> str:
    """요약 블록에서 `키: 값` 한 줄의 값을 꺼낸다."""
    for line in lines:
        m = SUMMARY_FIELD.match(line)
        if m and m.group(1).strip() == key:
            return m.group(2).strip()
    return default


# ── 포스트 발행 알림 ───────────────────────────────────────────────────────

def strip_front_matter(raw: str) -> str:
    """본문만 남긴다. 알림에서 front matter는 읽을 가치가 없다."""
    return re.sub(r'^---\s*\n.*?\n---\s*\n?', '', raw, count=1, flags=re.DOTALL)


def front_matter(raw: str) -> str:
    m = re.match(r'^---\s*\n(.*?)\n---', raw, flags=re.DOTALL)
    return m.group(1) if m else ""


def is_draft(raw: str) -> bool:
    """front matter의 `draft:` 값. 파일이 진리원이다 — 커밋 메시지가 아니라.

    커밋 메시지의 `상태:` 줄을 믿었다가 둘이 어긋나면 사이트에 없는 글을
    "발행되었습니다"라고 알리게 된다. 파일은 그럴 수 없다.
    """
    return bool(re.search(r'(?m)^draft:\s*true\b', front_matter(raw)))


def post_title(raw: str) -> str:
    m = re.search(r'(?m)^title:\s*["\']?(.*?)["\']?\s*$', front_matter(raw))
    return m.group(1).strip() if m else ""


def post_url(path: str) -> str:
    slug = os.path.splitext(os.path.basename(path))[0]
    return f"{SITE_BASE}/posts/{slug}/"


def format_post_published(path: str, raw: str, note: str = "") -> str:
    """오늘 발행된(혹은 보류된) 글의 머리말.

    승인을 묻지 않는다. 사람이 읽고 고치고 싶으면 `/revise-post`로 고쳐 다시 밀면
    되고, 그대로 두면 그대로 남는다.
    """
    title = post_title(raw) or os.path.basename(path)
    if is_draft(raw):
        head = "🟡 오늘의 글 — 보류됨 (사이트에 노출되지 않음)"
        tail = (f"{note}\n\n" if note else "") + "고쳐서 발행하려면 로컬에서 `/revise-post`."
    else:
        head = "🟢 오늘의 글 — 발행됨"
        tail = post_url(path)
    return f"{head}\n\n{title}\n\n{tail}"


def format_health_notification(body: str, report_path: str, url: str) -> str:
    """격주 점검 알림. 보낼지 말지는 워크플로가 `알림:` 줄로 이미 판정했다."""
    lines = extract_block(body, "점검 요약")
    monthly = field(lines, "월간 리포트") == "예"
    head = "📊 월간 현황 리포트" if monthly else "🔧 격주 점검 — 사람 확인 필요"
    name = os.path.basename(report_path) if report_path else "health report"
    return (
        f"{head} ({name})\n\n"
        f"{summarize_block(lines)}\n\n"
        f"리포트: {url}"
    )


def format_automation_alert(workflow: str, reason: str, detail: str, run_url: str) -> str:
    """수집 워크플로 실패 경보. 요약 블록 계약과 무관한 별개 경로다."""
    return (
        f"⚠ 자동화 경보 [{workflow}]\n\n"
        f"{reason}\n"
        f"{detail}\n\n"
        f"실행 로그 {run_url}"
    )


# ── 전송 ───────────────────────────────────────────────────────────────────

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
    """글 파일을 첨부한다. 실패해도 죽지 않는다 — 본문은 이미 갔고, 첨부는 보관용이라
    이것 때문에 워크플로를 실패시키면 경보가 거짓말을 하게 된다."""
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


def send_posts(bot_token: str, chat_id: str, paths: list, note: str = ""):
    """발행된 글을 머리말 + 본문(인라인) + 파일(첨부)로 보낸다.

    인라인이 주다 — 텔레그램은 .md를 다운로드 카드로만 그려서 모바일에서 바로
    읽히지 않는다. 사용자가 매일 받기로 한 것은 그 본문이다.
    """
    for path in paths:
        if not os.path.isfile(path):
            print(f"post file not found, skipping: {path}", file=sys.stderr)
            continue
        raw = open(path, encoding="utf-8").read()
        name = os.path.basename(path)
        send_telegram_message(bot_token, chat_id, format_post_published(path, raw, note))
        chunks = chunk_text(strip_front_matter(raw).strip())
        for i, chunk in enumerate(chunks, 1):
            header = f"📄 {name}" + (f" ({i}/{len(chunks)})" if len(chunks) > 1 else "")
            send_telegram_message(bot_token, chat_id, f"{header}\n\n{chunk}")
        send_telegram_document(bot_token, chat_id, path, caption=name)


def resolve_credentials():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        return bot_token, chat_id
    creds_json = os.environ.get("CREDENTIALS_JSON")
    if not creds_json:
        print("Error: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or CREDENTIALS_JSON missing",
              file=sys.stderr)
        sys.exit(1)
    creds = json.loads(creds_json)
    return creds["telegram"]["bot_token"], creds["telegram"]["chat_id"]


def main():
    bot_token, chat_id = resolve_credentials()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "alert":
        workflow, reason, detail, run_url = sys.argv[2:6]
        send_telegram_message(bot_token, chat_id,
                              format_automation_alert(workflow, reason, detail, run_url))
        return

    if mode == "health":
        send_telegram_message(bot_token, chat_id, format_health_notification(
            os.environ.get("COMMIT_BODY", ""),
            os.environ.get("REPORT_PATH", ""),
            os.environ.get("REPORT_URL", ""),
        ))
        return

    if mode == "post":
        paths = [p.strip() for p in os.environ.get("POST_FILES", "").splitlines() if p.strip()]
        if not paths:
            print("POST_FILES is empty — nothing to send", file=sys.stderr)
            return
        note = field(extract_block(os.environ.get("COMMIT_BODY", ""), "발행"), "사유")
        send_posts(bot_token, chat_id, paths, note)
        return

    print(f"Unknown mode: {mode!r} (expected: post | health | alert)", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
