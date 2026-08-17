# AGENTS.md

<system_context>
  <site_info>
    한국 경제뉴스를 비전문가에게 설명하는 Hugo 정적 사이트 (테마: PaperMod, `themes/PaperMod` 서브모듈), GitHub Pages 배포.
    Hugo 버전: 0.164.0 (CI와 로컬 버전 일치 필수).
    모든 Python 호출: `.venv/bin/python` 전용 (pytest 미사용, `if __name__ == '__main__'` 스탠드얼론 unittest).
  </site_info>

  <environment_constraints>
    - 루틴 샌드박스는 외부 웹(뉴스 사이트, Google API 등)에 도달할 수 없다 (GitHub, PyPI, npm만 허용).
    - WebFetch는 동작하지 않으며, WebSearch만 동작한다.
    - 외부 뉴스/데이터 수집은 GitHub Actions (`daily-collect.yml`, `weekly-collect.yml`)가 비공개 사이드카(`econ-blog/automation-data`)에 수집하여 스냅샷으로 제공한다.
  </environment_constraints>
</system_context>

<command_registry>
  <command name="/daily-post" file=".claude/commands/daily-post.md">
    - 일간 뉴스 해설 포스트 초안 생성.
    - 인자 없음 = 무인 모드 (`auto/post-YYYY-MM-DD` 브랜치 + PR 생성).
    - `manual` 인자 = 대화형 수동 모드 (후보 3건 제시 -> 선택 -> 승인 후 `main` 푸시).
  </command>

  <command name="/revise-post" file=".claude/commands/revise-post.md">
    - 대화형 수정 발행. 사용자 승인 후 `draft: false`로 `main`에 직접 푸시하고 해당 일자 PR을 닫음.
  </command>

  <command name="/weekly-audit" file=".claude/commands/weekly-audit.md">
    - 주 1회 감사 패스 (① 링크, ② 성과, ③ 색인, ④ 스캔, ⑤ 방향, ⑥ 수치).
    - 리포트 및 원장 JSON은 `main` 직행. `content/` 수정(사망링크 제거, 백필, front matter) 발생 시에만 `auto/audit-YYYY-MM-DD` PR 생성.
  </command>

  <command name="/weekly-housekeeping">
    - 순수 Python 무인 유지보수 (`scripts/housekeeping.py`, GitHub Actions 매주 일요일 실행).
  </command>

  <command name="/audit-local" file=".claude/commands/audit-local.md">
    - 로컬 대화형 전용 세션 (외부 네트워크 실측이 필요한 색인 제출, N1 기준일 확인 등 처리).
  </command>
</command_registry>

<content_model>
  <posts path="content/posts/<slug>.md">
    - Front matter: `title` (40자 이하), `date` (+09:00 KST), `description` (100자 내외), `tags` (2~3개, topics.yaml 목록 내), `draft` (true/false), `source_url`, `faq` (선택/권장 2개), `related_articles` (선택).
    - 본문: 볼드체(`**`) 절대 금지, 선 정의 후 비유, 4단 H2 구성, 투자 관점 섹션(3단계 인과 사슬 + 시소 매트릭스).
  </posts>

  <dictionary path="content/dictionary/<term-slug>.md">
    - Front matter: `title`, `date`, `description` (한 문장 정의 필수), `tags: ["용어사전"]`, `draft: true`.
    - 슬롯: 리드 정의 + `## 실생활에서는` + `## 투자에서는` + (선택)`## 숫자로 보면` + (선택)`## 함께 보면 좋은 용어`.
    - 색인 진리원: `content/dictionary/_terms.yaml` (새 용어 추가 시 동시 등록 필수).
  </dictionary>

  <wikilinks>
    - Goldmark 상대 링크: `[용어](/dictionary/slug/)`
    - `[[...]]` shortcode 문법 금지.
  </wikilinks>
</content_model>

<critical_contracts>
  <contract name="analysis_4_fields">
    `analysis.md`가 방출하는 4개 필드(`건드리는 렌즈`, `선행 vs 동행`, `확인된 수치`, `자산군별 함의`)는 `draft.md` §2에서 빠짐없이 소비되어야 한다.
  </contract>

  <contract name="terms_yaml_sync">
    `content/dictionary/*.md` 파일과 `content/dictionary/_terms.yaml`의 슬러그 키는 항상 100% 양방향 일치해야 한다 (`contracts.py --check terms`).
  </contract>

  <contract name="primary_source_hosts">
    1차 출처 인정 호스트는 `numerics.py`의 `PRIMARY_HOSTS` 6개(ECOS, FRED, KOSIS, DART, 전국은행연합회 소비자포털, BIS)로 단일화되어 있다.
  </contract>

  <contract name="headings_discipline">
    포스트 본문 H2는 정확히 4개이며, 옛 고정 제목을 금지하고, 4개 중 최소 3개는 `title`의 핵심 주제어를 포함해야 한다 (`headings.py`).
  </contract>

  <contract name="topic_report_format">
    `topic-report.md`는 최상단 `생성일: YYYY-MM-DD`로 시작하며, `## 잘 되는 주제`, `## 안 되는 주제`, `## 좋은 포스트의 조건` 섹션과 `(조정치: ±N)` 표기를 엄격히 준수한다.
  </contract>
</critical_contracts>

<runtime_invariants>
  - **무인 불변조건**: `auto/**` 브랜치에만 푸시 · 단일 커밋만 푸시 (`git commit --cleanup=verbatim`) · 항상 `draft: true` · 대화형 도구 호출 금지 · 1위 후보 < 8점이면 조용히 종료.
  - **수동 불변조건**: 명확한 사용자 긍정 확인 후에만 `draft: false` 변경 및 `main` 푸시.
  - **쓰기 금지 영역**: 감사 실행 시 `.claude/daily-post/` 전체, `hugo.toml`, `layouts/`, `content/` 본문 산문은 수정하지 않는다.
</runtime_invariants>
