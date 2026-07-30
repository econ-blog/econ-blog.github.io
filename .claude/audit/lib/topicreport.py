"""topic-report.md 직렬화. 형식 계약은 .claude/audit/README.md이며 여기 고정한다.

계약을 README에서 파싱하지 않는다 — 파싱하면 문장이 바뀔 때 출력이 조용히
변하고 계약의 권위가 코드로 새어 나간다. 대신 Plan 2의
contracts.check_topic_report_format으로 양방향 검증한다.

rank.md는 이 파일의 조정치를 그대로 읽어 15점 만점 총점에 더한다. 계약에 없는
필드를 추가하면 그 소비 로직이 깨진다. (SEED AC #22, Constraints)

r_g 기반 조정치는 상관에 근거한 결정론적 휴리스틱이며 인과 추정치가 아니다.
"""
from typing import Any

REQUIRED_HEADINGS = ("## 잘 되는 주제", "## 안 되는 주제", "## 좋은 포스트의 조건")
ADJUSTMENT_MIN = -2
ADJUSTMENT_MAX = 3


def _line(item: dict[str, Any], expect_sign: int) -> str:
    adj = int(item["조정치"])
    if not ADJUSTMENT_MIN <= adj <= ADJUSTMENT_MAX:
        raise ValueError(
            f"조정치 범위 밖: {adj} (허용 {ADJUSTMENT_MIN}~{ADJUSTMENT_MAX})")
    if adj == 0 or (adj > 0) != (expect_sign > 0):
        raise ValueError(
            f"조정치 {adj}는 이 섹션에 들어갈 수 없다 — 0은 어느 주장도 아니다")
    return f"- {item['주제']} (조정치: {adj:+d})"


def render(good: list[dict[str, Any]], bad: list[dict[str, Any]],
           conditions: list[str], today: str) -> str:
    """topic-report.md 전문. 게이트를 통과했을 때만 호출한다. (AC #22)"""
    parts = [f"생성일: {today}", ""]
    parts.append(REQUIRED_HEADINGS[0])
    parts.extend(_line(i, 1) for i in good)
    parts.append("")
    parts.append(REQUIRED_HEADINGS[1])
    parts.extend(_line(i, -1) for i in bad)
    parts.append("")
    parts.append(REQUIRED_HEADINGS[2])
    parts.extend(f"- {c}" for c in conditions)
    return "\n".join(parts) + "\n"
