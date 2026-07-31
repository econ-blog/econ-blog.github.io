"""사이드카 스냅샷 읽기 + 결정론적 게이트.

/daily-post 무인 모드의 중단 판정이 여기 있다. 산문 판단이 아니라 코드로 정한다:
  - 스냅샷 부재      → no_snapshot  (기존 "세 피드 전부 실패" 사상)
  - 날짜 ≠ 오늘 KST  → stale        (어제 뉴스로 글 쓰는 것 차단)
  - body_ok 후보 0건 → no_usable    (기존 "원문 읽기 실패 → 후보 폐기" 사상)

사용:
    .venv/bin/python scripts/read_snapshot.py [--sidecar PATH] [--allow-local-fetch]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_candidates import KST, body_ok, kst_date_str  # noqa: E402

SIDECAR_URL = "https://github.com/econ-blog/automation-data.git"


def resolve_sidecar(explicit, env, cwd_parent):
    """사이드카 체크아웃 경로를 정한다. 루틴이 두 번째 source를 어디에 놓는지
    모르므로 네 단계로 흡수한다. 어떻게 얻었는지를 함께 돌려준다 — 진단에 필요하다."""
    if explicit:
        return explicit, "arg"
    from_env = env.get("AUTOMATION_DATA_DIR")
    if from_env:
        return from_env, "env"
    sibling = os.path.join(cwd_parent, "automation-data")
    if os.path.isdir(sibling):
        return sibling, "sibling"
    return None, "clone"


def clone_sidecar():
    dest = tempfile.mkdtemp(prefix="automation-data-")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", SIDECAR_URL, dest],
        check=True, capture_output=True,
    )
    return dest


def load_snapshot(sidecar: str, subdir: str, date_str: str) -> dict:
    path = os.path.join(sidecar, subdir, f"{date_str}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def gate(snapshot: dict, today: str) -> dict:
    snap_date = snapshot.get("generated_at", "")[:10]
    if snap_date != today:
        return {"status": "stale", "candidates": [],
                "reason": f"스냅샷 날짜 {snap_date} ≠ 오늘 KST {today}"}

    usable = [c for c in snapshot.get("candidates", []) if body_ok(c)]
    if not usable:
        total = len(snapshot.get("candidates", []))
        return {"status": "no_usable", "candidates": [],
                "reason": f"본문 확보 후보 0건 (후보 {total}건)"}

    return {"status": "ok", "candidates": usable,
            "reason": f"후보 {len(usable)}건"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar")
    ap.add_argument("--subdir", default="candidates")
    ap.add_argument("--allow-local-fetch", action="store_true",
                    help="수동 모드 전용. 스냅샷이 없으면 직접 수집한다.")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = kst_date_str(now)

    sidecar, how = resolve_sidecar(args.sidecar, os.environ, os.path.dirname(os.getcwd()))
    if sidecar is None:
        try:
            sidecar = clone_sidecar()
            how = "clone"
        except subprocess.CalledProcessError as exc:
            # 네트워크 고장과 "뉴스 없음"을 섞지 않는다 — 진단이 다르다.
            print(json.dumps({"status": "sidecar_unreachable", "candidates": [],
                              "reason": f"사이드카 clone 실패: {exc.stderr.decode()[:200]}",
                              "sidecar_via": "clone"}, ensure_ascii=False))
            return 1

    try:
        snapshot = load_snapshot(sidecar, args.subdir, today)
    except FileNotFoundError:
        if args.allow_local_fetch:
            from fetch_candidates import collect
            snapshot = collect(now)
        else:
            print(json.dumps({"status": "no_snapshot", "candidates": [],
                              "reason": f"{args.subdir}/{today}.json 없음",
                              "sidecar_via": how}, ensure_ascii=False))
            return 1

    result = gate(snapshot, today)
    result["sidecar_via"] = how
    result["feeds_used"] = snapshot.get("feeds_used", [])
    result["feed_errors"] = snapshot.get("feed_errors", [])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
