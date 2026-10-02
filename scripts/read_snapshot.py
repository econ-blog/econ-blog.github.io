"""사이드카 스냅샷 읽기 + 결정론적 게이트.

/daily-post 무인 모드의 중단 판정이 여기 있다. 산문 판단이 아니라 코드로 정한다:
  - 스냅샷 부재      → no_snapshot  (기존 "세 피드 전부 실패" 사상)
  - 날짜 ≠ 오늘 KST  → stale        (어제 뉴스로 글 쓰는 것 차단)
  - body_ok 후보 0건 → no_usable    (기존 "원문 읽기 실패 → 후보 폐기" 사상)

`--days N`(N > 1)은 주 1회 발행용이다(2026-10-02~). 수집은 그대로 매일 24시간 창으로
하고, 발행하는 날 지난 N일치 일간 스냅샷을 합쳐 그 주의 후보 전체에서 고른다. 오늘
스냅샷 하나만 보면 월요일 새벽에는 일요일 하루치 뉴스만 남는다. 창 안의 파일이 하나도
없을 때만 no_snapshot이고, 하루 빠진 날은 `missing_dates`로만 알린다.

사용:
    .venv/bin/python scripts/read_snapshot.py [--sidecar PATH] [--days N] [--allow-local-fetch]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

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


def load_window(sidecar: str, subdir: str, today: str, days: int) -> dict:
    """오늘부터 `days`일 거슬러 올라간 일간 스냅샷을 후보 스냅샷 하나로 합친다.

    같은 기사(url)는 가장 최근 날짜의 사본만 남긴다. 각 후보에 `snapshot_path`를
    단다 — `post-reviewer`는 스냅샷 파일 하나를 받아 url로 원문을 찾으므로, 합친 뒤에도
    고른 후보가 어느 파일에서 왔는지 알아야 한다. `generated_at`은 오늘로 둔다 —
    신선도는 창이 정하므로 gate()의 stale 판정이 다시 걸지 않게 한다.
    """
    t = date.fromisoformat(today)
    candidates, seen, used, missing = [], set(), [], []
    feeds_used, feed_errors = [], []
    for i in range(days):
        d = (t - timedelta(days=i)).isoformat()
        path = os.path.abspath(os.path.join(sidecar, subdir, f"{d}.json"))
        try:
            snap = load_snapshot(sidecar, subdir, d)
        except (FileNotFoundError, json.JSONDecodeError):
            missing.append(d)
            continue
        used.append(d)
        for feed in snap.get("feeds_used", []):
            if feed not in feeds_used:
                feeds_used.append(feed)
        feed_errors.extend(snap.get("feed_errors", []))
        for c in snap.get("candidates", []):
            key = c.get("url") or c.get("title")
            if key in seen:
                continue
            seen.add(key)
            candidates.append({**c, "snapshot_path": path, "snapshot_date": d})
    if not used:
        raise FileNotFoundError(f"{subdir}/{missing[-1]}~{missing[0]} 창 안에 스냅샷 없음")
    return {"generated_at": f"{today}T00:00:00+09:00", "candidates": candidates,
            "feeds_used": feeds_used, "feed_errors": feed_errors,
            "window_days": days, "snapshot_dates": sorted(used),
            "missing_dates": sorted(missing)}


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
    ap.add_argument("--days", type=int, default=1,
                    help="후보 창(일). 1이면 오늘 스냅샷만, N이면 지난 N일 스냅샷을 합친다.")
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
        elif args.days > 1:
            snapshot = load_window(sidecar, args.subdir, today, args.days)
            snapshot_path = os.path.abspath(os.path.join(sidecar, args.subdir))
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
            if args.days > 1 and not args.dir_mode:
                reason = str(exc)
            elif isinstance(exc, FileNotFoundError):
                reason = f"{missing} 없음"
            else:
                reason = f"{missing} 손상됨 (JSONDecodeError)"
            print(json.dumps({"status": "no_snapshot", "candidates": [],
                              "reason": reason,
                              "sidecar_via": how}, ensure_ascii=False))
            return 1

    result = build_result(snapshot, today, how, snapshot_path)
    if "window_days" in snapshot:
        for key in ("window_days", "snapshot_dates", "missing_dates"):
            result[key] = snapshot[key]
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
