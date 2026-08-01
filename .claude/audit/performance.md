# ② 성과 분석 스테이지 지침

GA4·GSC 데이터로 어떤 주제가 먹히는지 판정하고, **데이터 충분성 게이트를 통과할 때만**
`topic-report.md`를 갱신한다. 결과를 문자열로 weekly-audit.md에 넘긴다 — 파일 쓰기·git은
시퀀서가 한다. 모든 Python은 `.venv/bin/python`으로 호출한다.

이 스테이지의 불변조건(시퀀서와 이중 진술 — AC #39 규약):

- **기본 상태는 "아무것도 쓰지 않음"이다.** 게이트 미충족이면 `topic-report.md`를
  **생성하지도, 수정하지도, 삭제하지도 않는다.** 기존 파일이 있으면 그대로 둔다. (AC #21)
- **조정치를 재량으로 매기지 않는다.** `attribution.adjustment`의 표가 유일한 산출
  경로다. 숫자를 손으로 조정하거나 "이 주제는 좋아 보인다"로 보정하지 않는다. (AC #17)
- **API를 직접 호출하지 않는다.** GA4·GSC는 `scripts/fetch_*.py` 경유로만. (AC #23)
- **`topic-report.md`에 계약 밖 필드를 추가하지 않는다.** 판정 근거는 감사 리포트에.
  (AC #22)
- **자격증명을 리포트에 쓰지 않는다.** 리포트는 공개 저장소에 커밋된다. 스크립트 출력의
  `propertyId`·서비스 계정 관련 필드를 리포트에 옮기지 않는다. (AC #41)
- **`writing-styles.md`를 수정하지 않는다.** loop이 소유한다. (AC #25)

## 1. 말뭉치 규모 측정 (네트워크 없음)

```
.venv/bin/python .claude/audit/lib/corpus.py
```

`gate_stats`에서 `published_count`·`site_age`를 얻는다. **이 두 값을 시퀀서에 돌려준다** —
③과 ⑤가 같은 값을 재사용해야 하고, 각자 다시 계산하면 세 곳이 어긋날 수 있다.

## 2. 트래픽 수집 (28일)

**스크립트를 직접 실행하지 않는다.** 루틴 샌드박스는 Google API에 도달할 수 없다(`AGENTS.md` 자동화 평면). `analytics.yml`이 일 01:20 KST에 미리 수집해 사이드카에 올려둔다:

```
.venv/bin/python scripts/read_snapshot.py --subdir analytics --dir-mode
```

AC #23("API를 직접 호출하지 않는다 — `scripts/fetch_*.py` 경유로만")의 취지는 유지된다.
스크립트가 여전히 유일한 산출 경로이고 실행 위치만 Actions로 옮겼다.

읽는 파일:

| 파일 | 대응하는 기존 호출 |
|---|---|
| `gsc_page_28d.json` | `fetch_gsc.py --json --days 28 --dimensions page` |
| `ga4_28d.json` | `fetch_ga4.py --days 28 --limit 200` |
| `gsc_28d.json` | `fetch_gsc.py --json --days 28` (차원 `query,page`) — ⑤가 쓴다 |

- **전제조건은 2단계로 판정하고, 두 판정은 서로 다른 곳에서 읽는다**(AC #26 규약을
  ②에도 적용): (1) 연동됨 — `--dir-mode` 실행 결과의 `files` 목록(정렬된 stem명)에
  해당 stem이 있는가로 판정한다. (2) 데이터 있음 — `{snapshot_path}/{stem}.json`을
  개별로 열어 그 안의 `total_rows > 0`을 본다. `--dir-mode`의 stdout 자체에는
  `total_rows`가 없다(`status`·`files`·`snapshot_path`·`reason`뿐이다). 두 판정을
  리포트에 **각각** 기록한다. 스냅샷이 통째로 없으면(`files`가 비었거나 stem 자체가
  없으면) "조회 실패"로 기록한다.
- GSC 출력이 `{"error": ...}`이거나 `{"ok": false}` 또는 종료 코드가 1이면 **"조회 실패"**로
  기록한다. `total_rows: 0`과 **다르게** 취급한다 — 전자는 모르는 것이고 후자는 아는 것이다.
- `has_gsc_data` = GSC `page` 차원의 `total_rows > 0`.

## 3. 주제군 지표 산출 (AC #16)

포스트 경로 → 태그 매핑은 `corpus.published()`가 준다. GSC `page` 행의 URL과 GA4
`topPages`의 `path`를 그 매핑에 붙여 주제군별 합계 `X_g`를 만든다.

- **URL → 파일 대응**: GSC는 절대 URL(`https://…/posts/<slug>/`), GA4는 경로
  (`/posts/<slug>/`)를 준다. 둘 다 `<slug>`를 뽑아 `content/posts/<slug>.md`에 맞춘다.
  대응되지 않는 행(홈 `/`, 태그 목록, 사전)은 **버리고 버린 행 수를 리포트에 적는다.**
- **분수 배분은 지표에만 적용한다**: 태그가 `k_p`개인 포스트는 각 주제군에 `x_p / k_p`만
  기여한다. 표본 크기 판정은 원시 개수 `c_g`로 한다(AC #16 후단).
- 선행 지표는 GSC **노출**, 후행 지표는 GA4 **세션**이다. 클릭·평균 게재순위는
  §5의 방향 확인에만 쓰고 조정치를 직접 산출하지 않는다(Ontology).
- 주제군별 세션은 `topPages[].sessions`에서 온다 — `summary.sessions`는 사이트 전체
  합계라 주제군으로 쪼갤 수 없다. `topPages` 행에 `sessions` 키가 없으면 그건 조회
  실패이므로 세션을 0으로 채우지 말고 `metrics`에서 그 키를 생략한다.

```
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".claude/audit/lib")
from attribution import group_sizes, signal_groups, per_post_metric, ratios
# posts, totals, metrics는 위에서 만든 dict를 넣는다
PY
```

`X_g`(주제군별 지표 합)와 `metrics`(주제군별 `impressions`·`sessions`)를 만들어
`group_sizes` → `signal_groups` → `per_post_metric` → `ratios` 순으로 통과시킨다.

## 4. 게이트 판정 (AC #14·#15·#21)

```
corpus_gate(published_count, site_age, sum(signal_groups.values()))
```

**미충족이면 여기서 멈춘다.** 리포트에 각 조건의 현재값/목표값 표와
`데이터 충분성: 미달`을 출력하고, `topic-report.md`에 손대지 않는다. `rank.md`는 파일
부재를 이미 정상으로 처리하므로 `rank.md` 변경은 필요 없다.

2026-07-26 기준 세 조건 전부 미달이며(발행 9/20 · 연령 8/28 · 신호군 0/3) **그 상태가
정상이다.** ②가 잠들어 있다는 사실 자체를 ③이 별도로 감시한다.

## 5. 조정치 산출 — 게이트 통과 시에만 (AC #17·#18·#19·#20)

1. 신호 조건을 충족한 주제군의 `m_g`로 `r_g`를 구하고 `adjustment(r_g)`를 적용한다.
   `M == 0`이면 **조정치를 전부 0으로 두고 사유를 리포트에 기록한다.**
2. `has_gsc_data`가 참이면 `demote(adj, group_stats, medians)`로 방향을 확인한다.
   `medians`는 전체 주제군의 `avg_position` 중앙값과 클릭 **상위 1/3 경계값**이다.
   강등 사실과 근거 수치를 리포트에 남긴다.
3. `has_gsc_data`가 거짓이면 `clamp_no_gsc(adj)`로 `[-1, +1]`로 자른다.
4. 감쇄 적용 전에 기존 감쇄 기록을 불러온다:
   ```
   .venv/bin/python - <<'PY'
   from pathlib import Path
   import sys
   sys.path.insert(0, ".claude/audit/lib")
   from attribution import load_history
   history = load_history(Path(".claude/audit/topic-history.json"))
   # history는 {} (파일 부재 시 정상)이거나 기존 JSON 파일의 dict 형태
   PY
   ```
   `load_history`는 파일이 없으면 `{}`를 돌려주며, 이는 첫 실행의 정상 상태다.
   파일이 있으면 JSON을 파싱한다. 갱신된 `history` 레지를 다음 단계로 넘긴다.
5. `decay(history, tag, adj, today)`로 감쇄를 적용한다. 갱신된 `history`를 문자열로
   변환해 시퀀서에 돌려준다: `json.dumps(history, ensure_ascii=False, indent=2) + "\n"`.
6. `M`을 만든 주제군 수를 리포트에 함께 적는다 — **3개면 중앙값 자체가 한 그룹이라
   사실상 두 그룹 비교다**(Known limits #2).

## 6. topic-report.md 조립 — 게이트 통과 시에만 (AC #22)

```
render(good, bad, conditions, today)
```

- `good`은 최종 조정치가 **양수**인 주제군, `bad`는 **음수**인 주제군. **0은 어느 섹션에도
  넣지 않는다**(`render`가 `ValueError`를 던진다).
- 주제 설명은 **통제 어휘 태그 이름을 그대로** 쓴다. `rank.md`의 매칭이 모호해지지 않게
  하는 유일한 방법이며 계약 형식은 그대로다.
- `conditions`("좋은 포스트의 조건")는 점수에 반영되지 않는 참고 섹션이다. **근거 없는
  일반론을 채우지 않는다** — 근거가 없으면 빈 섹션으로 둔다.
- 출력 문자열을 시퀀서에 돌려준다. **파일에 쓰지 않는다.**

## 7. 문체 패치 사후검증 (AC #25)

`.claude/loop/accepted-patches.md`가 **없으면 이 절과 리포트 섹션을 통째로 생략한다.**
placeholder를 만들지 않는다. 현재 그 파일은 없고 loop도 실행 전이므로 **상당 기간
아무것도 출력하지 않는 것이 정상이다**(Known limits #11).

있으면 각 패치의 반영 날짜를 뽑아 `attribution.patch_cohorts(posts, dates)`에 넘긴다.
`ready`가 참인 코호트만 전/후 지표를 비교해 리포트에 남긴다. **이 결과로
`writing-styles.md`를 수정하지 않는다.**

## 8. 수익 섹션 (AC #24)

AdSense는 미신청이다. **수익 섹션을 통째로 생략한다.** "데이터 없음" placeholder나 빈 표를
만들지 않는다. (④ P1의 신청 준비도 소견은 ④가 이미 낸다 — 여기서 중복하지 않는다.)

## 리포트 조립 (시퀀서가 소비)

```
## ② 성과 분석
> 이것은 관측 연구다. 주제군 간 지표 차이에 무작위 배정이 없고 발행 시각·뉴스 사이클·
> 우연이 교란한다. r_g 기반 조정치는 상관에 근거한 결정론적 휴리스틱이며 **인과 추정치가
> 아니다.** (Constraints)

- GSC: 연동됨 O / 데이터 {있음|없음(0행)|조회 실패} {(잘림 — 상위 N행만 집계)|없음}. GA4: 연동됨 O / 데이터 {…}.
- URL 대응 실패로 버린 행: N개

### 데이터 충분성
| 조건 | 현재 | 목표 | 판정 |
| 발행글 수 | 9 | 20 | 미달 |
| 최고령 발행글 경과일 | 8 | 28 | 미달 |
| 신호 조건 충족 주제군 | 0 | 3 | 미달 |
→ 데이터 충분성: 미달. topic-report.md를 만들지 않았다.

### 주제군 (참고 — 게이트 미충족 시에도 낸다)
| 주제군 | c_g | n_g | 노출 | 세션 | 신호 |

### 조정치 산출 근거 (게이트 통과 시에만)
| 주제군 | m_g | r_g | 표 조정치 | 강등 | 감쇄 | 최종 |
M = … (주제군 N개로 계산)
```

**게이트 미충족이어도 "주제군" 표는 낸다.** 임계값이 경험적으로 유도되지 않았으므로
(Known limits #1) 재보정에 필요한 것은 바로 이 분포다. 판정은 침묵해도 관측치는 남긴다.
