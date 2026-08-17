# 랭킹 단계 지침 (daily-post 랭킹 단계)

<instructions>
후보 기사를 수집·채점하여 최적의 포스팅 후보(무인: 1위 1건, 수동: 상위 3건)를 선별한다. 결과는 `daily-post.md`로 넘긴다.

## 1. 후보 스냅샷 읽기
GitHub Actions(`daily-collect.yml`)가 매일 01:30 KST에 수집해 둔 스냅샷을 읽는다 (RSS 직접 호출 금지):

```bash
.venv/bin/python scripts/read_snapshot.py
```
(수동 모드에서는 필요 시 `--allow-local-fetch` 추가)

- `status == "ok"`: `candidates` 목록으로 §2 이하 진행.
- 그 외 (`no_snapshot`, `stale`, `no_usable`, `sidecar_unreachable`): 후보를 지어내지 않고 상태를 보고한 뒤 즉시 종료.

## 2. 중복 판정
- **기존 포스트 대조**: `content/posts/` 스캔. 기존 `source_url` 또는 `related_articles[].url`과 일치 시 즉시 탈락. 제목/태그 유사 시 4번 항목에서 감점 (새 국면의 후속 보도는 감점 면제).
- **용어사전 대조**: `content/dictionary/_terms.yaml`의 `title` 및 `aliases` 전체 매칭 결과를 5번 항목에 반영.

## 3. 점수 체계 (15점 만점, 5개 기준 × 0~3점)
1. **일반인 관심도** (생활 밀접도)
2. **경제적 중요도** (사회적·거시적 파급력)
3. **투자 도움도** (경기 흐름, 유동성, 기업 체력 중 영향도 및 4대 전달 경로 연결성)
4. **과거 글 비중복성** (기존 글과의 차별성 및 후속 국면 여부)
5. **용어사전 연관성** (`_terms.yaml` 매칭도)

### 총점 합산 순서
1. 5개 기준 합계 (0~15)
2. `topic-report.md` 조정치 (−2~+3, 파일 부재 시 0)
3. 집중 주제 가점 (`topics.yaml`의 `focus: true` 주제 포함 시 +1)
4. 합산 결과를 **0~15로 clamp**
5. **8점 바닥 임계값 판정**

## 4. 임계값 판정 및 출력
- **무인 모드**: 1위 점수 8점 미만 시 조용히 종료. 8점 이상 시 1위 후보만 `daily-post.md`로 전달.
- **수동 모드**: 상위 3건을 표로 제시하여 사용자 선택을 받음. 3건 모두 8점 미만 시 "오늘 추천 후보 없음" 보고 후 중단.
</instructions>
