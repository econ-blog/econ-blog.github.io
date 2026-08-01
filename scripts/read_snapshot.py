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
    import atexit, shutil
    atexit.register(shutil.rmtree, dest, ignore_errors=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", SIDECAR_URL, dest],
        check=True, capture_output=True,
    )
    return dest


def load_snapshot(sidecar: str, subdir: str, date_str: str) -> dict:
    path = os.path.join(sidecar, subdir, f"{date_str}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_snapshot_dir(sidecar: str, subdir: str, date_str: str) -> dict:
    """analytics는 파일 하나가 아니라 날짜 디렉터리 안의 여러 JSON이다.

    "candidates" 키를 일부러 넣지 않는다 — gate()는 그 키의 존재 여부로
    후보 스냅샷인지를 판별한다. 넣으면 candidates: [] 있음-으로 오인되어
    본문 게이트가 "본문 확보 후보 0건"으로 오판정한다(빈 파일 목록과는
    다른 사상인데 같은 코드로 떨어진다). 대신 main()이 files 존재 여부로
    직접 status를 정한다."""
    base = os.path.join(sidecar, subdir, date_str)
    if not os.path.isdir(base):
        raise FileNotFoundError(base)
    files = {}
    for name in sorted(os.listdir(base)):
        if name.endswith(".json"):
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                files[name[:-5]] = json.load(fh)
    return {"generated_at": f"{date_str}T00:00:00+09:00", "files": files}


# gate()가 채우는 계약 키 + main()이 진단용으로 얹는 키. 이 이름들은
# candidates-없는 스냅샷(예: linkstate)의 페이로드 통과 시에도 덮어쓰지 않는다.
RESULT_KEYS = {"status", "candidates", "reason", "sidecar_via",
               "feeds_used", "feed_errors", "snapshot_path"}


def gate(snapshot: dict, today: str) -> dict:
    snap_date = snapshot.get("generated_at", "")[:10]
    if snap_date != today:
        return {"status": "stale", "candidates": [],
                "reason": f"스냅샷 날짜 {snap_date} ≠ 오늘 KST {today}"}

    # "candidates" 키가 아예 없으면 후보 스냅샷이 아니다(예: linkstate) — 본문 게이트는
    # 적용 대상이 없다. 빈 리스트로 존재하는 경우와는 다르게 취급해야 하므로 truthiness가
    # 아니라 키 존재로 판별한다.
    if "candidates" not in snapshot:
        return {"status": "ok", "candidates": [],
                "reason": "candidates 키 없음 — 날짜 신선도만 확인"}

    usable = [c for c in snapshot["candidates"] if body_ok(c)]
    if not usable:
        total = len(snapshot["candidates"])
        return {"status": "no_usable", "candidates": [],
                "reason": f"본문 확보 후보 0건 (후보 {total}건)"}

    return {"status": "ok", "candidates": usable,
            "reason": f"후보 {len(usable)}건"}


def build_result(snapshot: dict, today: str, how: str, snapshot_path: str | None) -> dict:
    """gate() 결과에 진단 필드를 얹는다. candidates 키가 없는 스냅샷(예: linkstate)은
    본문 게이트 대상이 아니다 — 대신 그 스냅샷 자신의 페이로드(summary/ledger 등)를
    result에 통째로 얹어서, 소비자가 stdout만으로 문서화된 키를 읽을 수 있게 한다.
    RESULT_KEYS(계약 키)와 이름이 겹치는 페이로드 키는 덮어쓰지 않는다."""
    result = gate(snapshot, today)
    result["sidecar_via"] = how
    result["feeds_used"] = snapshot.get("feeds_used", [])
    result["feed_errors"] = snapshot.get("feed_errors", [])
    if snapshot_path is not None:
        result["snapshot_path"] = snapshot_path
    if "candidates" not in snapshot:
        for key, value in snapshot.items():
            if key not in RESULT_KEYS:
                result[key] = value
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecar")
    ap.add_argument("--subdir", default="candidates")
    ap.add_argument("--allow-local-fetch", action="store_true",
                    help="수동 모드 전용. 스냅샷이 없으면 직접 수집한다.")
    ap.add_argument("--dir-mode", action="store_true",
                    help="스냅샷이 단일 JSON이 아니라 YYYY-MM-DD/ 디렉터리인 경우(analytics)")
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
        if args.dir_mode:
            snapshot = load_snapshot_dir(sidecar, args.subdir, today)
            snapshot_path = os.path.abspath(os.path.join(sidecar, args.subdir, today))
        else:
            snapshot = load_snapshot(sidecar, args.subdir, today)
            snapshot_path = os.path.abspath(
                os.path.join(sidecar, args.subdir, f"{today}.json"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        if args.allow_local_fetch and not args.dir_mode and isinstance(exc, FileNotFoundError):
            from fetch_candidates import collect
            snapshot = collect(now)
            snapshot_path = None  # 파일에서 읽은 게 아니라 그 자리에서 수집한 것 — 가리킬 경로가 없다
        else:
            missing = f"{args.subdir}/{today}" + ("" if args.dir_mode else ".json")
            reason = f"{missing} 없음" if isinstance(exc, FileNotFoundError) else f"{missing} 손상됨 (JSONDecodeError)"
            print(json.dumps({"status": "no_snapshot", "candidates": [],
                              "reason": reason,
                              "sidecar_via": how}, ensure_ascii=False))
            return 1

    result = build_result(snapshot, today, how, snapshot_path)
    if args.dir_mode:
        # gate()는 "candidates" 키 부재 스냅샷을 날짜 신선도만으로 ok 처리한다 — 그건
        # analytics 디렉터리가 존재한다는 사실 자체로 이미 참이다(경로에 today가 박혀
        # 있으므로 stale이 될 수 없다). 파일이 하나도 없는 빈 디렉터리까지 ok로 남기지
        # 않기 위해 status만 여기서 덮어쓴다. files는 브리핑이 요구한 대로 스템 이름의
        # 정렬된 목록으로 낸다 — 내용까지 담으면 계약이 무거워지고, 소비자(performance.md
        # §2)는 어차피 사이드카 경로에서 개별 파일을 직접 읽는다.
        file_names = sorted(snapshot["files"].keys())
        result["files"] = file_names
        result["status"] = "ok" if file_names else "no_usable"
        result["reason"] = f"스냅샷 파일 {len(file_names)}건"
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
