---
description: 텔레그램으로 받은 오늘 글을 고쳐 다시 발행한다. 대화형 전용 — main 직행. 인자로 대상 날짜(YYYY-MM-DD)를 줄 수 있고, 없으면 오늘(KST)로 본다.
---

## 0. 모드 계약 (먼저 확인)

**이 명령은 대화형 전용이다.** 사람이 텔레그램으로 그날 글을 받아 읽고, 고치고 싶을 때
claude cloud session을 직접 열어 실행하는 경로다. 무인 루틴에서 호출하지 않는다.

**2026-08-27 무인 운영 전환으로 이 명령의 성격이 바뀌었다.** 예전에는 승인 대기 중인
초안을 사람이 가로채는 자리였다 — 초안은 `auto/post-*` 브랜치에만 있었고, PR을 닫는 것이
이 명령의 마지막 일이었다. 지금은 글이 **이미 `main`에 있고 대개 이미 발행돼 있다.**
그러니 이 명령이 하는 일은 가로채기가 아니라 **사후 수정**이다:

- 글은 `main`의 `content/posts/`에 있다. 브랜치도 PR도 없다.
- 사이트에는 이미 올라가 있다(`draft: false`). 고치면 다시 배포된다.
- 예외: `/daily-post` §6이 검사 위반으로 **보류**한 글은 `draft: true`로 올라와 있다.
  사이트에는 없으며, 이 명령이 위반을 고치고 발행으로 넘기는 것이 정규 경로다.

승인 게이트(§6)는 그대로 남는다. 사람이 이 세션 안에 있는데도 확인 없이 미는 것은
무인화와 무관하게 규약 위반이다.

## 1. 대상 특정

인자로 날짜(`YYYY-MM-DD`)를 받으면 그 날짜를, 없으면 **KST 오늘** 날짜를 쓴다.
UTC로 계산하면 16시 이후에 하루가 어긋난다.

```bash
TARGET="${1:-$(TZ=Asia/Seoul date +%F)}"
git fetch origin main && git checkout -B main origin/main
grep -l "^date: ${TARGET}" content/posts/*.md
```

front matter의 `date`가 진리원이다 — 파일명 슬러그에는 날짜가 없다.

찾지 못하면 **중단한다.** 그날 글이 없다는 뜻이고(1위 후보 8점 미만으로 조용히 종료됐거나
수집이 실패했거나), 그건 이 명령이 할 일이 아니다. 사람에게 그렇게 보고하고 멈춘다.

여러 건이 나오면 사람에게 목록을 보여주고 어느 것인지 확인받는다.

## 2. 현재 상태 확인

```bash
sed -n '1,20p' content/posts/<슬러그>.md      # front matter — draft 값을 본다
git log --oneline -3 -- content/posts/<슬러그>.md
```

`draft: true`면 **보류된 글이다.** 커밋 메시지 본문의 `사유:` 줄이 무엇이 걸렸는지 말해
준다(`git log -1 --format=%b <커밋>`). 그 위반을 먼저 고친다 — 고치지 않은 채 `draft: false`로
넘기면 발행 게이트를 사람 손으로 우회하는 것이다.

`draft: false`면 이미 사이트에 있다. 고친 내용은 푸시 직후 재배포된다.

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
**"이대로 main에 푸시할까요?"**(보류된 글이면 "draft: false로 바꿔 main에 푸시할까요?")
라고 구체적으로 묻는다.

명확한 긍정("네", "승인", "푸시해줘")만 승인으로 인정한다. **"좋아요"·"괜찮네요"는
승인이 아니다** — 다시 명확히 묻는다. 승인 전에는 어떤 git 쓰기도 하지 않는다.

## 7. 발행

승인 후에만, 이 순서로 한다.

```bash
# 1. 보류된 글이었다면 draft 플립 — 포스트와 사전 항목 양쪽
sed -i 's/^draft: true$/draft: false/' content/posts/<슬러그>.md content/dictionary/<슬러그>.md

# 2. 대상 파일만 명시적으로 add한다 (글롭 금지)
git status --short
git add content/posts/<슬러그>.md content/dictionary/<슬러그>.md content/dictionary/_terms.yaml

# 3. main에 커밋·푸시 → hugo.yml이 배포한다
git pull --rebase origin main
git commit -m "post(revise): <제목>"
git push origin main
```

**커밋 제목은 반드시 `post(revise): `로 시작한다.** `notify-post.yml`은 `post: ` 접두사만
듣고 본문을 텔레그램으로 민다. `post: `로 커밋하면 사람이 방금 이 세션에서 읽은 글을
텔레그램으로 한 번 더 받는다 — `post(revise): `는 그것을 걸러 내기 위한 접두사다.

푸시가 네트워크 오류로 실패하면 2s·4s·8s·16s로 최대 4회 재시도한다.

닫을 PR도, 지울 브랜치도 없다. 승인 루프가 사라지면서 둘 다 없어졌다.

## 8. 보고

사람에게 세 줄로 보고한다.

```
발행: <배포된 URL 경로>
상태: 보류 해제(draft:false) | 이미 발행된 글 수정
검사: 통과 | 사람 지시로 위반 N건 남긴 채 발행
```

텔레그램에 따로 알림을 보내지 않는다 — 사람이 이 세션 안에 있으므로 같은 내용을
두 번 받게 된다. `post(revise): ` 접두사가 그것을 이미 막는다.
