"""자격증명 단일 진입점.

저장소 루트 `credentials.json` 하나가 로컬 원본이며 스키마는 GitHub Secret
`CREDENTIALS_JSON`과 **동일**하다:

    {"telegram": {"bot_token": ..., "chat_id": ...},
     "ga4": {"service_account": {<서비스 계정 키 원본>}}}

Google 라이브러리는 평탄한 서비스 계정 키 파일 경로를 받는다. 워크플로는 이미
평탄한 파일을 RUNNER_TEMP에 풀어 `*_CREDENTIALS`로 넘기므로 그 경로는 그대로
통과시키고, 로컬의 중첩 파일일 때만 임시 파일로 풀어 그 경로를 돌려준다.

사용:
    from credentials import service_account_path, telegram_credentials
"""
import atexit
import json
import os
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(REPO_ROOT, "credentials.json")

_ENV_KEYS = ("GSC_CREDENTIALS", "GA4_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS")


def _load_bundle():
    """CREDENTIALS_JSON(문자열) 또는 credentials.json(파일)에서 중첩 번들을 읽는다."""
    raw = os.environ.get("CREDENTIALS_JSON")
    if raw:
        return json.loads(raw)
    if os.path.exists(DEFAULT_PATH):
        with open(DEFAULT_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _materialize(service_account: dict) -> str:
    fd, path = tempfile.mkstemp(prefix="sa-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(service_account, fh)
    os.chmod(path, 0o600)
    atexit.register(lambda: os.path.exists(path) and os.remove(path))
    return path


def service_account_path():
    """GA4/GSC용 평탄한 서비스 계정 키 파일 경로. 없으면 None."""
    for key in _ENV_KEYS:
        path = os.environ.get(key)
        if path and os.path.exists(path):
            return path
    bundle = _load_bundle()
    if not bundle:
        return None
    if "ga4" in bundle:
        return _materialize(bundle["ga4"]["service_account"])
    # 평탄한 서비스 계정 키를 그대로 credentials.json에 둔 경우
    if bundle.get("type") == "service_account":
        return DEFAULT_PATH
    return None


def telegram_credentials():
    """(bot_token, chat_id). 없으면 (None, None)."""
    bundle = _load_bundle()
    if not bundle or "telegram" not in bundle:
        return None, None
    tg = bundle["telegram"]
    return tg.get("bot_token"), tg.get("chat_id")
