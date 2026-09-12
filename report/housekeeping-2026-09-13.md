# 주간 유지보수 리포트 (2026-09-13)

## ① 링크 무결성
### 확정 사망 링크 (수정 대상)
- https://www.koreadaily.com/article/20260630021453178
- https://www.koreadaily.com/article/20260728015447613

## ① 확장: 내부 링크 백필
- content/posts/apartment-balance-loan-cap-exclusion.md: 잔금대출 -> final-payment-loan
- content/posts/apartment-move-in-rate-loan-squeeze.md: 잔금대출 -> final-payment-loan
- content/posts/eitc-expansion-2026.md: 근로장려금 -> earned-income-tax-credit
- content/posts/household-loan-cap-30-to-60-trillion.md: 잔금대출 -> final-payment-loan
- content/posts/housing-supply-financial-regulation-easing.md: 잔금 대출 -> final-payment-loan
- content/posts/seoul-property-tax-expansion-2030.md: 종합부동산세 -> comprehensive-real-estate-tax
- content/posts/us-treasury-buyback-yield-rebound.md: 국채 바이백 -> treasury-buyback
- content/posts/us-treasury-buyback-yield-rebound.md: 국채금리 -> treasury-yield
- content/posts/us-treasury-buyback-yield-rebound.md: 코픽스 -> cofix
- content/posts/yen-carry-trade-unwind-boj-rate-hike.md: 엔캐리 트레이드 -> yen-carry-trade
- content/posts/yen-carry-trade-unwind-boj-rate-hike.md: 정책금리 -> base-rate
- content/dictionary/brent-crude.md: 소비자물가 -> consumer-price-index
- content/dictionary/consumer-price-index.md: 기준금리 -> base-rate
- content/dictionary/consumer-price-index.md: PER -> per
- content/dictionary/core-inflation.md: 소비자물가 -> consumer-price-index
- content/dictionary/core-inflation.md: 기준금리 -> base-rate
- content/dictionary/final-payment-loan.md: 가계대출 총량규제 -> aggregate-loan-cap
- content/dictionary/fomc.md: 기준금리 -> base-rate
- content/dictionary/fomc.md: 원/달러 환율 -> won-dollar-exchange-rate
- content/dictionary/fomc.md: 국채금리 -> treasury-yield
- content/dictionary/loan-spread-rate.md: 기준금리 -> base-rate
- content/dictionary/real-effective-exchange-rate.md: 원/달러 환율 -> won-dollar-exchange-rate
- content/dictionary/treasury-buyback.md: 국채금리 -> treasury-yield

## ③ 색인 건전성
| 항목 | 결과 | 값 |
|---|---|---|
| I1 sitemap 생성 | 소견 | loc 0 ≥ 발행 51 |
| I2 robots.txt | 소견 | Disallow 없음, Sitemap 줄 명시 |
| I3 baseURL 3자 정합 | 통과 | hugo=econ-blog.github.io |
| I4 sitemap 제출 | 통과 | 제출 확인 |
| I5 noindex 유출 | 통과 | 유출 0건 |
| I6 색인 커버리지 | 관찰 | GSC 전수 검사 |
| I7 GSC 속성 유형 | 통과 | url-prefix, 호스트 일치 |

## ④ 시스템 스캔

### 효율 (E)
| 축 | 관측값 | 판정 |
|---|---|---|
| E1 빌드 | 종료 0, Non-page 1 고정값 충족 | 통과 (Non-page 1 고정값 충족) |
| E2 CI | gh CLI 미가용 — 루틴 정책상 호출하지 않음, 축 건너뜀 | 미측정 |
| E4 Hugo | 로컬 0.164.0 / CI(`.github/workflows/hugo.yml:25`) 0.164.0 | 일치 |

### 포스트 품질 (Q)
| 축 | 관측값 |
|---|---|
| Q1 front matter | 통과 |
| Q4 방치 초안 | 2건 |
| Q5 자가검토 예산 | 9 / 12 |
| P2 내부 순환 | 중앙값 3.0 |

## ⑥ 수치 무결성
| 검사 | 건수 |
|---|---|
| N1 기준일 누락 | 0 |
| N2 비1차 출처 | 0 |
| N3 교차 불일치 | 3 |
| N4 무한정 최상급 | 0 |
| N5 발행글 수치 전재 | 0 |
