"""② 성과 분석 — 게이트·분수 배분·조정치·감쇄. (SEED AC #14–20)

순수·결정론. 네트워크를 쓰지 않고 API를 호출하지 않는다 — 트래픽 수치는
scripts/fetch_*.py가 수집해 dict로 넘어온다(AC #23).

②의 기본 상태는 "아무것도 쓰지 않음"이다. 이 모듈이 내는 조정치는 상관에
근거한 결정론적 휴리스틱이며 인과 추정치가 아니다(Constraints).

  .venv/bin/python .claude/audit/lib/attribution.py
"""
import json
from datetime import date as _date
from pathlib import Path

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
