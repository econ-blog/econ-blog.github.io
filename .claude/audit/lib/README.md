# 주간 감사 측정 헬퍼

`/weekly-audit`(`.claude/commands/weekly-audit.md`)와 스테이지 지침
(`.claude/audit/*.md`)이 호출하는 결정론적 Python 헬퍼.

## 규약
- 실행: `.venv/bin/python .claude/audit/lib/<name>.py <args>` (시스템 python 금지).
- 측정 헬퍼(mdtext·internal_links·backfill·corpus)는 **표준 라이브러리 + 정규식만**.
  AST 파서·형태소 분석기·외부 의존성을 도입하지 않는다. 근거: `.claude/loop/`가
  못박은 클라우드 재현성 규약과 동일.
- `linkcheck.py`만 네트워크 I/O에 `requests`를 쓴다. 네트워크는 본디 비결정적이라
  이 경계는 측정 헬퍼의 결정론 규약을 깨지 않는다. 순수 로직(원장 갱신·판정)은
  여전히 stdlib이며 테스트 대상이다.
- 각 헬퍼는 파일 경로를 argv로 받아 JSON을 stdout에 낸다(LLM 스테이지가 소비).
- 같은 입력에 같은 출력. LLM은 여기의 어떤 값도 산출하지 않는다.

## 소스 vs 런타임 산출물
이 디렉터리의 `.py`는 에이전트 **소스**다. SEED AC #36의 "산출물 5개 외 파일
금지"는 감사 **실행**이 남기는 파일(`audit-*.md`·`*.json`)에 대한 제약이지
소스 파일에 대한 것이 아니다.

## 테스트
`.venv/bin/python .claude/audit/lib/test_<name>.py` — 전부 통과 시 "전부 통과",
실패 시 exit 1. `.claude/loop/test_extract_features.py`와 같은 하니스.
