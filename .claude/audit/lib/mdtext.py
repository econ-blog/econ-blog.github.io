"""마크다운 전처리 — 주간 감사의 코드스팬·링크 처리 단일 주체.

결정론적. 표준 라이브러리 + 정규식만 사용한다. AST 파서를 도입하지 않는다.
(근거: SEED Constraints — extract_features.py와 같은 재현성 규약.)

사용:
    .venv/bin/python .claude/audit/lib/mdtext.py <파일.md>   # JSON 링크 인벤토리
"""
import json
import re
import sys
from pathlib import Path

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")
MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
SOURCE_URL = re.compile(r'^source_url:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
RELATED_URL = re.compile(r'^\s+url:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)


def split_front_matter(raw: str) -> tuple[str, str]:
    """(구분자 포함 front matter, 본문). front matter가 없으면 ('', raw)."""
    m = FRONT_MATTER.match(raw)
    if not m:
        return "", raw
    return m.group(0), raw[m.end():]


def strip_code_spans(text: str) -> str:
    """펜스 코드블록과 인라인 코드 스팬을 제거한다. (AC #5)

    펜스를 먼저 지운 뒤 인라인을 지운다 — 순서를 바꾸면 펜스 안의 단일 백틱이
    인라인 스팬을 거짓으로 열어 펜스 경계를 깨뜨린다. 링크 추출 전에 적용해
    코드 예시 안의 대괄호·괄호가 링크로 오인되는 것을 막는다.
    """
    text = FENCED_CODE.sub("", text)
    text = INLINE_CODE.sub("", text)
    return text


if __name__ == "__main__":
    pass
