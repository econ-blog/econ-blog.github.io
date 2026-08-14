---
description: 텔레그램으로 받은 오늘 초안을 수정해 바로 발행한다. 대화형 전용 — main 직행 + 그날 auto/post PR 닫기. 인자로 대상 날짜(YYYY-MM-DD)를 줄 수 있고, 없으면 오늘(KST)로 본다.
---

## 0. 모드 계약 (먼저 확인)

**이 명령은 대화형 전용이다.** 사람이 텔레그램 알림을 보고 claude cloud session을
직접 열어 실행하는 경로다. 무인 루틴에서 호출하지 않는다 — 무인 경로는
`/daily-post`(초안 생성)와 `daily-collect.yml`의 인박스(승인 집행) 둘뿐이고,
이 명령은 그 둘 사이에 사람이 끼어드는 지점이다.

승인 경로와 **다른 점 하나만** 기억하면 된다: 승인은 다음날 01:30 인박스가
집행하지만, 수정은 **이 세션이 그 자리에서 집행한다.** `main`에 직접 커밋·푸시하고
그날 `auto/post-YYYY-MM-DD` PR을 닫는다. 그래서 다음날 01:30 인박스는 열린 PR을
찾지 못하고 아무 일도 하지 않는다 — 그것이 의도된 "sleep"이며, 따로 배선할
것이 없다. 재질의(`--reask`)도 같은 이유로 조용하다.

`main` 직행은 무인 규약(「무인은 `main`에 절대 직접 푸시하지 않는다」)의 예외가
아니다. 이 경로는 수동 모드이고, `/daily-post` 수동 모드가 이미 승인 뒤 `main`에
푸시한다. **승인 게이트(§5)를 건너뛰면 그때 규약을 어기는 것이다.**

## 1. 대상 특정

인자로 날짜(`YYYY-MM-DD`)를 받으면 그 날짜를, 없으면 **KST 오늘** 날짜를 쓴다.
UTC로 계산하면 16시 이후에 하루가 어긋난다.

```bash
TARGET="${1:-$(TZ=Asia/Seoul date +%F)}"
```

`auto/post-$TARGET` 브랜치와 그 브랜치를 head로 하는 열린 PR을 찾는다.

- **`gh`가 있으면** `gh pr list --head "auto/post-$TARGET" --state open`.
- **`gh`가 없으면**(클라우드 세션이 보통 이쪽이다) GitHub MCP 도구
  `list_pull_requests`(`state: open`)로 같은 head를 찾는다.

찾지 못하면 **중단한다.** 브랜치가 없다는 것은 (a) 그날 초안이 없거나 (b) 이미
발행·반려됐다는 뜻이고, 둘 다 이 명령이 할 일이 아니다. 어느 쪽인지 사람에게
보고하고 멈춘다.

## 2. 초안을 작업 트리로 가져오기

초안은 `main`이 아니라 `auto/post-$TARGET`에만 있다. **브랜치를 체크아웃하지 않고
파일만 `main` 위로 가져온다** — 아래 §6에서 `main`에 커밋할 것이기 때문이다.

```bash
git fetch origin main "auto/post-$TARGET"
git checkout -B main origin/main
git checkout "origin/auto/post-$TARGET" -- content/
git status --short          # 가져온 경로가 그날 산출물뿐인지 눈으로 확인한다
```

`content/` 밖(예: `.claude/`, `layouts/`)은 가져오지 않는다. 초안 브랜치에는
그날 포스트·사전 항목·`_terms.yaml` append 셋만 있어야 하고, 그 밖의 것이
섞여 있으면 그 자리에서 사람에게 알리고 멈춘다.

**`auto/post-$TARGET` 브랜치에는 어떤 커밋도 밀지 않는다.** `auto/**` 푸시는
`open-auto-pr.yml`을 깨우고, 그 워크플로는 이 시점에 PR을 만들 이유가 없다.

## 3. 요청사항 확인

세션 프롬프트에 수정 요청이 이미 적혀 있으면 그것을 쓴다. 없거나 모호하면
**고치기 전에 묻는다.** "톤을 부드럽게" 같은 지시는 어느 문단을 말하는지
확인해야 하고, "숫자가 틀렸다"는 어느 숫자가 무엇으로 바뀌는지 확인해야 한다.

원문 사실관계를 다시 확인해야 하는 요청이면 한계를 먼저 말한다 — **클라우드 세션
샌드박스는 뉴스 사이트에 도달하지 못한다**(egress allowlist는 GitHub 계열 +
PyPI + npm뿐). WebSearch는 되고 WebFetch는 되지 않는다. 새 수치를 원문에서
확인할 수 없으면 지어내지 말고, 사람에게 값을 받거나 그 문장을 들어낸다.

## 4. 수정

산문·톤 규칙은 `.claude/daily-post/writing-styles.md`에 있다. Read로 읽고 그
규칙 안에서 고친다. 새 용어사전 항목을 추가하게 되면 `draft.md` §3의 계약이
그대로 적용된다 — **사전 파일 생성과 `content/dictionary/_terms.yaml` append는
따로 일어나므로 한쪽만 하면 위키링크가 조용히 깨진다.**

front matter `date`는 건드리지 않는다. 초안이 만들어진 시각이 그 글의 발행일이고,
수정 시각으로 바꾸면 `related_articles`의 "같은 날 기사 제외" 판정과 발행 순서가
어긋난다.

## 5. 발행 전 검사 게이트

`/daily-post`와 **같은 모듈**을 돌린다. 재구현하지 않는다 — 쓰기시점과 감사시점의
판정이 갈린다.

`.venv`가 있으면 `.venv/bin/python`을 쓴다. 클라우드 세션에는 보통 없는데,
`.claude/audit/lib/`의 측정 헬퍼는 **표준 라이브러리 전용**이라 `python3`로 그대로
돌아간다. `requirements.txt` 설치는 이 명령에 필요 없다(네트워크 수집을 하지 않는다).

```bash
PY=$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

$PY .claude/audit/lib/numerics.py --file content/posts/<슬러그>.md      # N1·N2·N4·N5
$PY .claude/audit/lib/numerics.py --file content/dictionary/<슬러그>.md # 사전 항목이 있으면
$PY .claude/audit/lib/contracts.py --check terms                        # _terms.yaml 정합
$PY .claude/audit/lib/headings.py  --file content/posts/<슬러그>.md      # 제목 규율 T1~T4
```

`numerics.py`는 `total`이, `headings.py`는 `total`이 0이어야 하고,
`contracts.py --check terms`는 `[]`여야 한다.

Hugo 빌드도 확인한다. 클라우드 세션에는 Hugo도 테마 서브모듈도 없으므로 먼저 받는다:

```bash
bash scripts/bootstrap_sandbox.sh
export PATH="$HOME/.local/bin:$PATH"
git submodule update --init --depth 1 themes/PaperMod
hugo --gc --minify
rm -rf public resources
```

**`Non-page files`가 1로 유지되는지 본다** — 그 1은 `content/dictionary/_terms.yaml`이
올바르게 건너뛰어진 것이다. `Pages`는 발행마다 늘어나므로 고정값으로 보지 않는다.

결과는 `통과` · `남은 위반 N건` · `검사 불가` 셋 중 하나다. **`검사 불가`를 `통과`와
같게 취급하지 않는다.** `통과`가 아니면 §6의 승인 질문을 **하지 않는다.** 대신 남은
위반 목록(또는 검사 불가 사유)을 파일 경로와 함께 보여주고 "고칠지, 그대로 발행할지"를
묻는다. 사람이 그대로 발행하라고 명확히 지시하면 그때만 §6으로 넘어간다.

## 6. 승인 게이트

(a) 바꾼 내용을 diff로, (b) 검사 결과 한 줄을 보여주고
**"draft: false로 바꿔 main에 푸시하고 PR #N을 닫을까요?"**라고 구체적으로 묻는다.

명확한 긍정("네", "승인", "푸시해줘")만 승인으로 인정한다. **"좋아요"·"괜찮네요"는
승인이 아니다** — 다시 명확히 묻는다. 승인 전에는 어떤 git 쓰기도 하지 않는다.

## 7. 발행

승인 후에만, 이 순서로 한다.

```bash
# 1. draft 플립 — 포스트와 사전 항목 양쪽
sed -i 's/^draft: true$/draft: false/' content/posts/<슬러그>.md content/dictionary/<슬러그>.md

# 2. 대상 파일만 명시적으로 add한다 (글롭 금지)
git status --short
git add content/posts/<슬러그>.md content/dictionary/<슬러그>.md content/dictionary/_terms.yaml

# 3. main에 커밋·푸시 → hugo.yml이 배포한다
git commit -m "post: <제목>"
git push origin main
```

푸시가 네트워크 오류로 실패하면 2s·4s·8s·16s로 최대 4회 재시도한다.

그다음 PR을 닫고 브랜치를 지운다. `gh`가 있으면 `gh pr close`, 없으면 GitHub MCP
`update_pull_request`(`state: closed`)를 쓴다. **병합이 아니라 닫기다** — 내용은
이미 `main`에 있고, 병합하면 `draft: true` 버전이 되살아난다.

브랜치 삭제까지 끝나야 다음날 인박스가 이 PR을 보지 않는다. 다만 브랜치가 남아도
PR이 닫혀 있으면 `get_open_prs()`가 걸러 내므로 교착은 생기지 않는다.

## 8. 보고

사람에게 (a) 배포된 URL 경로, (b) 닫은 PR 번호, (c) 다음날 01:30 인박스가 할 일이
없다는 사실을 한 번에 알린다.

텔레그램에 따로 알림을 보내지 않는다 — 사람이 이 세션 안에 있으므로 같은 내용을
두 번 받게 된다. 알림이 필요하면 사람이 요청할 때만 `scripts/telegram_notify.py`를 쓴다.

**남아 있을 수 있는 것 하나**: 그날 텔레그램에 이미 `승인`이나 다른 답장을 보냈다면,
그 업데이트는 다음날 01:30 인박스가 뒤늦게 소비하면서 "대기 중인 PR이 없습니다"
또는 "지정한 토큰과 일치하는 대기 PR이 없습니다"를 돌려보낸다. 정상이며 조치할
것이 없다 — 사람에게 그렇게 알린다.
