"""계약 검사 — 프롬프트 파일 간 합의가 깨졌는지 보는 결정론적 문자열 검사.

CLAUDE.md가 "조용히 깨진다"고 명시한 계약이 대상이다. 위반은 소견이 아니라
계약 위반이며, 4필드 규칙을 적용받지 않고 리포트 최상단에 무조건 출력된다
(AC #32). 이 모듈은 어떤 파일도 수정하지 않는다.

사용:
    .venv/bin/python .claude/audit/lib/contracts.py   # 위반 JSON
"""
import json
import re
import sys
from pathlib import Path

# analysis.md §4가 방출하고 draft.md §2가 소비해야 하는 4개 필드.
# 하나라도 짝을 잃으면 런타임에 조용히 드롭된다 — 실제로 한 번 일어났고
# 자동 검사가 없어 사람 리뷰로 잡혔다.
ANALYSIS_FIELDS = ("건드리는 렌즈", "선행 vs 동행", "확인된 수치", "자산군별 함의")

ANALYSIS_PATH = Path(".claude/daily-post/analysis.md")
DRAFT_PATH = Path(".claude/daily-post/draft.md")
WRITING_STYLES_PATH = Path(".claude/daily-post/writing-styles.md")
TERMS_PATH = Path("content/dictionary/_terms.yaml")
DICT_DIR = Path("content/dictionary")
TOPIC_REPORT_PATH = Path(".claude/audit/topic-report.md")


def check_four_fields(analysis_text: str, draft_text: str) -> list[dict]:
    """4필드가 양방향으로 살아 있는지. (AC #31 첫째)"""
    out = []
    for field in ANALYSIS_FIELDS:
        if field not in analysis_text:
            out.append({
                "check": "4필드",
                "detail": f"analysis.md가 '{field}'를 더 이상 방출하지 않는다",
            })
        elif field not in draft_text:
            out.append({
                "check": "4필드",
                "detail": f"draft.md에 '{field}'를 소비하는 지점이 없다 "
                          f"— 이 필드는 런타임에 조용히 드롭된다",
            })
    return out


if __name__ == "__main__":
    pass
