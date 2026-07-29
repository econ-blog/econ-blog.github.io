"""② 성과 분석 — 게이트·분수 배분·조정치·감쇄. (SEED AC #14–20)

순수·결정론. 네트워크를 쓰지 않고 API를 호출하지 않는다 — 트래픽 수치는
scripts/fetch_*.py가 수집해 dict로 넘어온다(AC #23).

②의 기본 상태는 "아무것도 쓰지 않음"이다. 이 모듈이 내는 조정치는 상관에
근거한 결정론적 휴리스틱이며 인과 추정치가 아니다(Constraints).

순수 함수만 있고 저장소를 읽지 않는다 — CLI 진입점이 없다.
"""
import json
from datetime import date as _date
from pathlib import Path
from statistics import median

# 전부 초기값이며 경험적으로 유도되지 않았다 — rank.md의 8/15와 같은 성격이다.
# 첫 통과 실행의 실제 분포로 재보정한다(Known limits #1). 한 곳에서 고칠 수 있게 모아 둔다.
CORPUS_MIN_POSTS = 20
CORPUS_MIN_AGE = 28
CORPUS_MIN_GROUPS = 3
SIGNAL_MIN_POSTS = 5
SIGNAL_MIN_IMPRESSIONS = 300
SIGNAL_MIN_SESSIONS = 30


def group_sizes(posts: list[dict]) -> dict:
    """주제군별 c_g(원시 개수)와 n_g(분수 배분). (AC #16)

    c_g와 n_g를 분리한다 — 표본 크기 판정에 분수 배분을 적용하면 태그가 k개일 때
    실제로 3k건을 요구하게 되어 AC #14보다 가혹해진다.
    """
    out: dict[str, dict] = {}
    for post in posts:
        tags = [t for t in post.get("tags", []) if t]
        if not tags:
            continue
        share = 1.0 / len(tags)
        for tag in tags:
            bucket = out.setdefault(tag, {"c": 0, "n": 0.0})
            bucket["c"] += 1
            bucket["n"] += share
    for bucket in out.values():
        bucket["n"] = round(bucket["n"], 3)
    return out


def signal_groups(sizes: dict, metrics: dict, has_gsc_data: bool) -> dict:
    """주제군별 신호 조건 충족 여부. 충족하지 못한 군은 조정치를 받지 못할 뿐
    다른 군의 조정을 막지 않는다. (AC #15)"""
    out = {}
    for tag, size in sizes.items():
        m = metrics.get(tag) or {}
        if has_gsc_data:
            signal_ok = float(m.get("impressions", 0)) >= SIGNAL_MIN_IMPRESSIONS
        else:
            signal_ok = float(m.get("sessions", 0)) >= SIGNAL_MIN_SESSIONS
        out[tag] = size["c"] >= SIGNAL_MIN_POSTS and signal_ok
    return out


def corpus_gate(published_count: int, oldest_age: int,
                signal_group_count: int) -> dict:
    """말뭉치 조건 — 전역 논리곱. 셋 다 충족해야 topic-report.md를 쓸 자격이 생긴다. (AC #14)"""
    conditions = [
        {"name": "발행글 수", "current": published_count,
         "target": CORPUS_MIN_POSTS, "met": published_count >= CORPUS_MIN_POSTS},
        {"name": "최고령 발행글 경과일", "current": oldest_age,
         "target": CORPUS_MIN_AGE, "met": oldest_age >= CORPUS_MIN_AGE},
        {"name": "신호 조건 충족 주제군", "current": signal_group_count,
         "target": CORPUS_MIN_GROUPS, "met": signal_group_count >= CORPUS_MIN_GROUPS},
    ]
    return {"passed": all(c["met"] for c in conditions), "conditions": conditions}


# AC #17. LLM이 점수를 재량으로 매기지 않는다 — 이 표가 유일한 산출 경로다.
ADJUSTMENT_TABLE = ((3.0, 3), (2.0, 2), (1.3, 1), (0.7, 0), (0.4, -1))
DECAY_DAYS = 60


def per_post_metric(sizes: dict, totals: dict) -> dict:
    """m_g = X_g / n_g. 주제군 크기 차이를 제거한다. (AC #16)"""
    out = {}
    for tag, size in sizes.items():
        n = float(size.get("n", 0.0))
        out[tag] = round(float(totals.get(tag, 0.0)) / n, 4) if n else 0.0
    return out


def _median(values: list[float]) -> float:
    """짝수 개면 가운데 두 값의 평균이다 — 신호군은 3~6개라 짝수가 절반이며,
    위쪽 중앙값을 쓰면 M이 높게 잡혀 모든 r_g가 밴드 하나씩 밀린다."""
    return median(values) if values else 0.0


def ratios(m: dict) -> tuple[dict, float]:
    """r_g = m_g / median(m). z-score를 쓰지 않는다 — 주제군이 3~6개뿐이라
    평균·표준편차는 이상치 하나에 무너진다. (Ontology, Known limits #2)"""
    M = _median(list(m.values()))
    if not M:
        return {tag: 0.0 for tag in m}, 0.0
    return {tag: round(v / M, 4) for tag, v in m.items()}, M


def adjustment(r: float) -> int:
    """r_g → 조정치. 표 밖(하한 미달)은 -2. (AC #17)"""
    for threshold, value in ADJUSTMENT_TABLE:
        if r >= threshold:
            return value
    return -2


def demote(adj: int, group_stats: dict, medians: dict) -> tuple[int, str | None]:
    """방향 확인 — GSC 데이터가 있을 때만 의미가 있다. (AC #18)

    클릭·평균 게재순위는 방향 확인용이며 조정치를 직접 산출하지 않는다.
    """
    if "avg_position" not in group_stats or "clicks" not in group_stats:
        return adj, None
    position = float(group_stats["avg_position"])
    clicks = float(group_stats["clicks"])
    # 중앙값이 없으면 강등하지 않는다 — 기본값 0이면 어떤 실제 순위도 이를 넘어
    # 조건이 "클릭 0"으로 무너진다. 음수 분기와 마찬가지로 no-op 쪽으로 실패한다.
    position_median = float(medians.get("avg_position", float("inf")))
    if adj > 0 and position > position_median and clicks == 0:
        return 0, (f"양수 조정치 강등 — 평균 게재순위 {position} > 중앙값 "
                   f"{position_median}, 클릭 0")
    if adj < 0 and clicks >= float(medians.get("clicks_top_third", float("inf"))):
        return 0, f"음수 조정치 강등 — 클릭 {clicks}이 전체 상위 1/3"
    return adj, None


def clamp_no_gsc(adj: int) -> int:
    """GSC 무데이터 시 [-1, +1]로 clamp. 후행 지표만으로는 신호량이 한 자릿수
    적다. (AC #19)"""
    return max(-1, min(1, adj))


def load_history(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"topic-history.json 파싱 실패: {exc}") from exc


def save_history(path: Path, history: dict) -> None:
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def decay(history: dict, tag: str, adj: int, today: str,
          days: int = DECAY_DAYS) -> tuple[int, dict]:
    """음수 조정치가 최초부여일로부터 days일 이상 유지되면 절대값을 1 줄인다.
    양수는 감쇄하지 않는다 — 래칫을 만드는 것은 감점뿐이다. (AC #20)

    이 상태를 topic-report.md 밖에 두는 이유: 계약 형식에 필드를 추가하면
    rank.md가 깨진다. README.md의 90일 신선도 규칙은 매주 재생성하면
    생성일이 영원히 최신이라 무력하다.

    최초부여일은 "지금 이어지는 음수 구간"의 시작일이다. 음수가 풀리면 지워지고,
    다시 음수가 되면 그날부터 새로 센다 — 안 그러면 지난 감점의 경과일이 남아
    재진입 첫 주에 곧바로 감쇄되어 60일 유지 요건이 무너진다.
    """
    entry = history.get(tag)
    if entry is None:
        entry = {"조정치": adj, "최초부여일": today if adj < 0 else None,
                 "마지막감쇄일": None}
        history[tag] = entry
        return adj, entry

    entry["조정치"] = adj
    if adj >= 0:
        entry["최초부여일"] = None
        entry["마지막감쇄일"] = None
        return adj, entry

    if not entry.get("최초부여일"):
        entry["최초부여일"] = today
        entry["마지막감쇄일"] = None
        return adj, entry

    since = entry.get("마지막감쇄일") or entry["최초부여일"]
    elapsed = (_date.fromisoformat(today) - _date.fromisoformat(since)).days
    if elapsed >= days:
        adj = min(0, adj + 1)
        entry["조정치"] = adj
        entry["마지막감쇄일"] = today
    return adj, entry


def patch_cohorts(posts: list[dict], patch_dates: list[str],
                  min_posts: int = 5) -> list[dict]:
    """문체 패치 반영 시점 기준 전/후 발행글 코호트. (AC #25)

    accepted-patches.md가 아직 없고 loop도 실행 전이므로 이 함수는 상당 기간
    빈 목록을 받는다 — 그 상태가 정상이다(Known limits #11). 이 결과로
    writing-styles.md를 수정하지 않는다. loop이 소유한다.

    날짜가 없는 발행글은 어느 코호트에도 속할 수 없다.
    """
    # 날짜가 None이거나 없는 발행글 제외
    posts = [p for p in posts if p.get("date")]

    out = []
    for patch_date in sorted(patch_dates):
        before = sorted(p["file"] for p in posts if p["date"] < patch_date)
        after = sorted(p["file"] for p in posts if p["date"] >= patch_date)
        out.append({"patch_date": patch_date, "before": before, "after": after,
                    "ready": len(after) >= min_posts})
    return out
