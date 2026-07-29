"""⑤ 방향성 — 방향 원장 direction-log.json. (SEED AC #46·#48·#49·#51)

가설은 5필드를 모두 갖췄을 때만 등록된다. ⑤의 감독자는 다른 LLM이 아니라
이 사전등록 절차다 — 제안 시점에 예측과 기각 기준을 못박고 다음 감사가
데이터로 대조한다.

  .venv/bin/python .claude/audit/lib/hypothesis.py <direction-log.json>
"""
import json
import re
from datetime import date as _date
from pathlib import Path

FIELDS = ("주장", "지표", "예측", "확인시점", "기각기준")
STATES = ("제안", "채택", "확인대기", "확증", "반증", "기각")
HISTORY_LIMIT = 12


def validate(candidate: dict) -> list[str]:
    """빠진 필드 목록. 빈 목록이면 5필드 완비. (AC #46)

    값이 공백만인 필드는 빠진 것으로 본다 — "예측: " 같은 형식적 충족을
    통과시키면 사전등록이 무의미해진다.
    """
    return [f for f in FIELDS if not str(candidate.get(f, "")).strip()]


def load_ledger(path: Path) -> dict:
    """원장 로드. 부재는 정상이며 기본 골격을 돌려준다."""
    if not path.is_file():
        return {"hypotheses": [], "portfolio_history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"direction-log.json 파싱 실패: {exc}") from exc
    data.setdefault("hypotheses", [])
    data.setdefault("portfolio_history", [])
    return data


def save_ledger(path: Path, ledger: dict) -> None:
    path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def next_id(ledger: dict) -> str:
    nums = [
        int(h["id"][1:])
        for h in ledger["hypotheses"]
        if str(h.get("id", "")).startswith("H") and h["id"][1:].isdigit()
    ]
    return f"H{(max(nums) + 1) if nums else 1:03d}"


def record_portfolio(ledger: dict, snapshot: dict, today: str) -> dict | None:
    """오늘 스냅샷을 이력에 넣고 직전 스냅샷을 돌려준다. (AC #45)

    AC #36이 산출물을 다섯 개로 못박았으므로 직전값 보관 파일을 따로 만들지
    않고 이 원장에 함께 둔다. 같은 날 재실행은 덮어쓴다.
    """
    history = ledger["portfolio_history"]
    history[:] = [h for h in history if h.get("date") != today]
    previous = history[-1] if history else None
    history.append({"date": today, "snapshot": snapshot})
    del history[:-HISTORY_LIMIT]
    return previous


PROPOSAL_CAP = 3
POSTPONE_LIMIT = 3
PUBLISHED_DUE = re.compile(r"발행\s*(\d+)\s*건")
AGE_DUE = re.compile(r"(?:연령|D)\s*(\d+)\s*일")


def register(
    ledger: dict, candidate: dict, today: str, source: dict | None = None
) -> dict:
    """5필드 완비 후보를 `제안` 상태로 등록. 미달이면 ValueError. (AC #46)"""
    missing = validate(candidate)
    if missing:
        raise ValueError(f"가설 미달 — 빠진 필드: {', '.join(missing)}")
    entry = {"id": next_id(ledger)}
    entry.update({f: str(candidate[f]).strip() for f in FIELDS})
    entry.update(
        {
            "상태": "제안",
            "제기일": today,
            "채택일": None,
            "연기횟수": 0,
            "출처": source or {"유형": "내부"},
            "대조이력": [],
        }
    )
    ledger["hypotheses"].append(entry)
    return entry


def enforce_cap(candidates: list[dict]) -> tuple[list[dict], int]:
    """상위 PROPOSAL_CAP건과 버린 건수. 버린 것은 기록하지 않는다. (AC #47)"""
    return candidates[:PROPOSAL_CAP], max(0, len(candidates) - PROPOSAL_CAP)


def adopt(h: dict, today: str) -> dict:
    """제안 → 채택 → 확인대기. 수동 모드에서 사람의 명확한 긍정으로만 호출한다. (AC #48)"""
    h["채택일"] = today
    h["상태"] = "확인대기"
    return h


def due(ledger: dict, published_count: int, site_age: int) -> list[dict]:
    """확인 시점에 도달한 `확인대기` 가설. 파싱 불가는 미도달로 본다. (AC #49)"""
    out = []
    for h in ledger["hypotheses"]:
        if h.get("상태") != "확인대기":
            continue
        when = str(h.get("확인시점", ""))
        pm, am = PUBLISHED_DUE.search(when), AGE_DUE.search(when)
        if pm and published_count >= int(pm.group(1)):
            out.append(h)
        elif am and site_age >= int(am.group(1)):
            out.append(h)
    return out


def resolve(h: dict, outcome: str, evidence: str, today: str) -> dict:
    """예측 충족 → 확증, 기각 기준 충족 → 반증. 삭제하지 않고 원장에 남긴다. (AC #49)"""
    if outcome not in ("확증", "반증"):
        raise ValueError(f"outcome은 확증 또는 반증이어야 한다: {outcome!r}")
    h["상태"] = outcome
    h["대조이력"].append({"date": today, "outcome": outcome, "evidence": evidence})
    return h


def postpone(h: dict, today: str, reason: str) -> dict:
    """대조 자체가 불가능할 때 연기. 3회에 이르면 기각(사유 "측정 불가"). (AC #49)"""
    h["연기횟수"] = int(h.get("연기횟수", 0)) + 1
    if h["연기횟수"] >= POSTPONE_LIMIT:
        h["상태"] = "기각"
        h["대조이력"].append(
            {"date": today, "outcome": "기각", "evidence": "측정 불가"}
        )
    else:
        h["대조이력"].append(
            {"date": today, "outcome": "연기", "evidence": reason}
        )
    return h


def current_direction(ledger: dict) -> list[dict]:
    """"현재 방향" 블록에 올릴 가설. 없으면 빈 목록이며 블록 자체를 생략한다. (AC #48)"""
    return [
        h for h in ledger["hypotheses"] if h.get("상태") in ("채택", "확인대기")
    ]


def stale_warning(ledger: dict, today: str, days: int = 14) -> str | None:
    """원장 정체 감지. AC #13을 direction-log.json에도 적용한다. (Known limits #17)"""
    history = ledger.get("portfolio_history") or []
    if not history:
        return (
            "방향 원장 미누적 — 이전 감사 PR이 병합되지 않았을 수 있음. "
            "직전 감사값 대조와 연기 카운트 불가"
        )
    last = history[-1].get("date", "")
    if not last:
        return "방향 원장의 최신 이력에 날짜가 없음 — 대조 불가"
    gap = (_date.fromisoformat(today) - _date.fromisoformat(last)).days
    if gap >= days:
        return (
            f"방향 원장 정체 — 최신 이력 {last}({gap}일 전). "
            "이전 감사 PR이 병합되지 않았을 수 있음"
        )
    return None


def main(argv: list[str]) -> None:
    """원장 요약을 JSON으로. 읽기 전용 — 이 진입점은 원장을 쓰지 않는다."""
    from collections import Counter
    from datetime import date as _today

    path = Path(
        argv[1] if len(argv) > 1 else ".claude/audit/direction-log.json"
    )
    ledger = load_ledger(path)
    today = _today.today().isoformat()
    print(
        json.dumps(
            {
                "path": str(path),
                "current_direction": current_direction(ledger),
                "counts_by_state": dict(
                    Counter(h.get("상태") for h in ledger["hypotheses"])
                ),
                "stale": stale_warning(ledger, today),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    import sys as _sys

    main(_sys.argv)

