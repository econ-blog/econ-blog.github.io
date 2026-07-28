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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from internal_links import load_terms  # noqa: E402

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

SELF_REVIEW_HEADING = "## AI 흔적 자가검토"
NUMBERED_ITEM = re.compile(r"^\s*(\d+)\.\s+\S", re.MULTILINE)
CREATED_AT = re.compile(r"^생성일:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
ADJUSTMENT = re.compile(r"\(조정치:\s*([+-]\d+)\)")


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


def check_terms_sync(terms: dict, dict_dir: Path) -> list[dict]:
    """_terms.yaml 키 ↔ content/dictionary/*.md 파일명 양방향 일치. (AC #31 둘째)

    _terms.yaml이 위키링크 매칭의 단일 출처이므로, 한쪽에만 있는 항목은
    링크 누락이나 죽은 링크로 이어진다.
    """
    files = {
        p.stem for p in dict_dir.glob("*.md") if not p.name.startswith("_")
    }
    slugs = set(terms)
    out = []
    for missing_file in sorted(slugs - files):
        out.append({
            "check": "사전 정합",
            "detail": f"_terms.yaml에 '{missing_file}'가 있으나 "
                      f"content/dictionary/{missing_file}.md가 없다",
        })
    for missing_slug in sorted(files - slugs):
        out.append({
            "check": "사전 정합",
            "detail": f"content/dictionary/{missing_slug}.md가 있으나 "
                      f"_terms.yaml에 '{missing_slug}' 키가 없다",
        })
    return out


def count_self_review_items(writing_styles_text: str) -> int:
    """'## AI 흔적 자가검토' 아래 번호 항목 수. 다음 ## 헤딩 전까지."""
    idx = writing_styles_text.find(SELF_REVIEW_HEADING)
    if idx < 0:
        return 0
    rest = writing_styles_text[idx + len(SELF_REVIEW_HEADING):]
    nxt = rest.find("\n## ")
    section = rest if nxt < 0 else rest[:nxt]
    return len(NUMBERED_ITEM.findall(section))


def check_self_review_budget(writing_styles_text: str, budget: int = 12) -> list[dict]:
    """자가검토 항목 수 ≤ 12. (AC #31 셋째)

    개수만 센다 — writing-styles.md는 loop이 소유하며 내용을 수정하지 않는다.
    """
    n = count_self_review_items(writing_styles_text)
    if n <= budget:
        return []
    return [{
        "check": "자가검토 예산",
        "detail": f"writing-styles.md 자가검토 항목 {n}개 > 예산 {budget}개",
    }]


def check_topic_report_format(text: str | None) -> list[dict]:
    """README.md 형식 계약과 실재 topic-report.md의 합치. (AC #31 넷째)

    파일 부재는 정상 상태이며 위반이 아니다(rank.md가 조용히 건너뛴다).
    """
    if text is None:
        return []
    out = []
    if not CREATED_AT.search(text):
        out.append({
            "check": "리포트 형식",
            "detail": "topic-report.md 최상단 '생성일: YYYY-MM-DD' 누락",
        })
    for section in ("## 잘 되는 주제", "## 안 되는 주제", "## 좋은 포스트의 조건"):
        if section not in text:
            out.append({
                "check": "리포트 형식",
                "detail": f"topic-report.md에 '{section}' 섹션 누락",
            })
    for raw in ADJUSTMENT.findall(text):
        val = int(raw)
        if not (-2 <= val <= 3):
            out.append({
                "check": "리포트 형식",
                "detail": f"조정치 {raw}가 계약 범위 −2~+3 밖 "
                          f"(rank.md가 끝값으로 clamp한다)",
            })
    return out


def all_checks() -> list[dict]:
    violations = []
    violations += check_four_fields(
        ANALYSIS_PATH.read_text(encoding="utf-8"),
        DRAFT_PATH.read_text(encoding="utf-8"),
    )
    violations += check_terms_sync(
        load_terms(TERMS_PATH.read_text(encoding="utf-8")), DICT_DIR
    )
    violations += check_self_review_budget(
        WRITING_STYLES_PATH.read_text(encoding="utf-8")
    )
    report = (
        TOPIC_REPORT_PATH.read_text(encoding="utf-8")
        if TOPIC_REPORT_PATH.exists()
        else None
    )
    violations += check_topic_report_format(report)
    return violations


if __name__ == "__main__":
    print(json.dumps(all_checks(), ensure_ascii=False, indent=2))

