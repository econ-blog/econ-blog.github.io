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


def external_source(
    presenter: str,
    verified_on: str,
    passed_urls: list[str],
    rejected_siblings: int,
    unverified: bool = False,
) -> dict:
    """외부 가설의 출처 기록. 어디서 왔고 형제 몇 건이 걸러졌는지 추적한다. (AC #51)"""
    return {
        "유형": "외부",
        "제시자": presenter,
        "검증일": verified_on,
        "통과URL": list(passed_urls),
        "기각된형제주장수": int(rejected_siblings),
        "근거미확인": bool(unverified),
    }


def register_external(
    ledger: dict, candidate: dict, today: str, source: dict
) -> dict:
    """3관문을 통과한 외부 주장을 `제안`으로 등록. (AC #50·#51)

    관문 1(인용 검증)·관문 2(저장소 대조)는 스테이지가 진행하고 결과를 source로
    넘긴다. 관문 3(5필드 변환)은 register의 validate가 그대로 강제한다.
    """
    if source.get("유형") != "외부":
        raise ValueError("register_external은 유형이 '외부'인 출처만 받는다")
    return register(ledger, candidate, today, source=source)


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
    h.setdefault("대조이력", []).append(
        {"date": today, "outcome": outcome, "evidence": evidence}
    )
    return h


TERMINAL = ("확증", "반증", "기각")


def postpone(h: dict, today: str, reason: str) -> dict:
    """대조 자체가 불가능할 때 연기. 3회에 이르면 기각(사유 "측정 불가"). (AC #49)"""
    if h.get("상태") in TERMINAL:
        raise ValueError(
            f"이미 종결된 가설은 연기할 수 없다: {h.get('id')} ({h.get('상태')})"
        )
    h["연기횟수"] = int(h.get("연기횟수", 0)) + 1
    history = h.setdefault("대조이력", [])
    if h["연기횟수"] >= POSTPONE_LIMIT:
        h["상태"] = "기각"
        history.append({"date": today, "outcome": "기각", "evidence": "측정 불가"})
    else:
        history.append({"date": today, "outcome": "연기", "evidence": reason})
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


USAGE = """사용:
  hypothesis.py summary  <원장>
  hypothesis.py due      <원장> <발행건수> <사이트연령>
  hypothesis.py record   <원장> <스냅샷.json> [오늘] [n1_count=N] [claims_total=N] [claims_per_post=X]
  hypothesis.py register <원장> <후보.json> [오늘]
  hypothesis.py adopt    <원장> <ID…> [오늘]
  hypothesis.py resolve  <원장> <ID> <확증|반증> <근거> [오늘]
  hypothesis.py postpone <원장> <ID> <사유> [오늘]

원장 인자에 `-`를 주면 표준입력에서 읽는다(앞 명령의 출력을 그대로 파이프).
**어떤 하위 명령도 파일에 쓰지 않는다** — 갱신된 원장을 stdout으로만 낸다.
파일 쓰기와 git은 시퀀서(§9)가 한다."""


def _read_ledger(arg: str) -> dict:
    """경로 또는 `-`(표준입력). 앞 명령이 낸 봉투({"ledger": …})도 그대로 받는다."""
    if arg == "-":
        import sys as _s

        data = json.loads(_s.stdin.read())
    else:
        return load_ledger(Path(arg))
    if isinstance(data, dict) and "ledger" in data:
        data = data["ledger"]
    data.setdefault("hypotheses", [])
    data.setdefault("portfolio_history", [])
    return data


def _find(ledger: dict, hid: str) -> dict:
    for h in ledger["hypotheses"]:
        if h.get("id") == hid:
            return h
    raise ValueError(f"원장에 없는 가설 id: {hid}")


def _emit(ledger: dict, **info) -> None:
    """갱신된 원장 + 부수 정보를 한 봉투로. 시퀀서는 `ledger`만 파일에 쓴다."""
    print(json.dumps({"ledger": ledger, **info}, ensure_ascii=False, indent=2))


def _today_or(args: list[str], index: int) -> str:
    if len(args) > index and args[index]:
        return args[index]
    return _date.today().isoformat()


def _coerce(text: str):
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            continue
    return text


def main(argv: list[str]) -> None:
    """하위 명령 디스패치. summary·due는 읽기 전용, 나머지는 stdout으로만 낸다."""
    from collections import Counter

    if len(argv) < 3:
        raise SystemExit(USAGE)
    cmd, args = argv[1], argv[2:]
    ledger = _read_ledger(args[0])
    rest = args[1:]

    if cmd == "summary":
        today = _today_or(rest, 0)
        print(
            json.dumps(
                {
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
        return

    if cmd == "due":
        if len(rest) < 2:
            raise SystemExit(USAGE)
        print(
            json.dumps(
                due(ledger, int(rest[0]), int(rest[1])),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if cmd == "record":
        if not rest:
            raise SystemExit(USAGE)
        snap = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
        # portfolio.py의 전체 출력을 그대로 줘도 받는다.
        snap = snap.get("snapshot", snap)
        positional = [a for a in rest[1:] if "=" not in a]
        # ⑥의 세 값은 주어진 것만 얹는다 — 없으면 키를 생략한다(None을 채우지 않는다).
        for pair in (a for a in rest[1:] if "=" in a):
            key, _, value = pair.partition("=")
            if value.strip():
                snap[key] = _coerce(value)
        today = _today_or(positional, 0)
        # 정체 경고는 **적재 전** 원장으로 판정한다 — 오늘 이력을 넣은 뒤에 보면
        # 최신 이력이 항상 오늘이라 경고가 영원히 null이 된다.
        stale = stale_warning(ledger, today)
        previous = record_portfolio(ledger, snap, today)
        _emit(ledger, previous=previous, stale=stale)
        return

    if cmd == "register":
        if not rest:
            raise SystemExit(USAGE)
        payload = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
        candidates = payload if isinstance(payload, list) else [payload]
        kept, dropped = enforce_cap(candidates)
        today = _today_or(rest, 1)
        registered = []
        for c in kept:
            source = c.pop("출처", None)
            if source and source.get("유형") == "외부":
                registered.append(register_external(ledger, c, today, source))
            else:
                registered.append(register(ledger, c, today, source=source))
        _emit(ledger, registered=registered, dropped=dropped)
        return

    if cmd == "adopt":
        if not rest:
            raise SystemExit(USAGE)
        ids = [a for a in rest if a.startswith("H")]
        today = _today_or([a for a in rest if not a.startswith("H")], 0)
        adopted = [adopt(_find(ledger, i), today) for i in ids]
        _emit(ledger, adopted=adopted)
        return

    if cmd == "resolve":
        if len(rest) < 3:
            raise SystemExit(USAGE)
        h = resolve(_find(ledger, rest[0]), rest[1], rest[2], _today_or(rest, 3))
        _emit(ledger, resolved=h)
        return

    if cmd == "postpone":
        if len(rest) < 2:
            raise SystemExit(USAGE)
        h = postpone(_find(ledger, rest[0]), _today_or(rest, 2), rest[1])
        _emit(ledger, postponed=h)
        return

    raise SystemExit(USAGE)


if __name__ == "__main__":
    import sys as _sys

    main(_sys.argv)

