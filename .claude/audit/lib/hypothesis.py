"""⑤ 방향성 — 방향 원장 direction-log.json. (SEED AC #46·#48·#49·#51)

가설은 5필드를 모두 갖췄을 때만 등록된다. ⑤의 감독자는 다른 LLM이 아니라
이 사전등록 절차다 — 제안 시점에 예측과 기각 기준을 못박고 다음 감사가
데이터로 대조한다.

  .venv/bin/python .claude/audit/lib/hypothesis.py <direction-log.json>
"""
import json
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
