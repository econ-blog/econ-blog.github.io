# 주간 유지보수 리포트 (2026-08-30)

## ① 링크 무결성
### 확정 사망 링크 (수정 대상)
- https://www.koreadaily.com/article/20260630021453178

## ① 확장: 내부 링크 백필
- content/posts/bok-august-rate-hike-core-inflation-dilemma.md: 최고가격제 -> oil-price-cap
- content/posts/bok-back-to-back-rate-hike-possibility.md: 기준금리 -> base-rate
- content/posts/bok-rate-hike-3-percent-krw-11month-low.md: 원/달러 환율 -> won-dollar-exchange-rate
- content/posts/bok-rate-hike-3-percent-krw-11month-low.md: 기준금리 -> base-rate
- content/posts/bok-rate-hike-3-percent-krw-11month-low.md: 코픽스 -> cofix
- content/posts/china-nand-ymtc-samsung-sk-hynix-catch-up.md: 낸드플래시 -> nand-flash
- content/posts/china-nand-ymtc-samsung-sk-hynix-catch-up.md: HBM -> hbm
- content/posts/fed-economists-no-rate-hike-2026.md: 연방공개시장위원회 -> fomc
- content/posts/fed-economists-no-rate-hike-2026.md: 기준금리 -> base-rate
- content/posts/household-credit-2000-trillion-milestone.md: 가계신용 잔액 -> household-credit
- content/posts/household-loan-cap-30-to-60-trillion.md: 가계신용 -> household-credit
- content/posts/isa-maturity-limit-tax-reform-review.md: 자산 배분 -> asset-allocation
- content/posts/kospi-consecutive-circuit-breaker.md: 주주환원 정책 -> shareholder-return
- content/posts/kospi-consecutive-circuit-breaker.md: 원/달러 -> won-dollar-exchange-rate
- content/posts/kospi-consecutive-circuit-breaker.md: HBM4 -> hbm
- content/posts/kospi-rebound-foreign-buying-bull-market.md: 주주환원 -> shareholder-return
- content/posts/nvidia-gpu-collateral-credit-market.md: AI 순환금융 -> circular-financing
- content/posts/nvidia-gpu-collateral-credit-market.md: 고대역폭메모리 -> hbm
- content/posts/oil-price-cap-brent-90-dollar-freeze.md: 석유 최고가격 -> oil-price-cap
- content/posts/russia-sakhalin-lng-eu-sanction-waiver.md: 원/달러 환율 -> won-dollar-exchange-rate
- content/posts/samsung-sk-hynix-shareholder-return-300-trillion.md: 주주환원 -> shareholder-return
- content/posts/samsung-sk-hynix-shareholder-return-300-trillion.md: 잉여현금흐름 -> free-cash-flow
- content/posts/samsung-sk-hynix-shareholder-return-kospi.md: 잉여현금흐름 -> free-cash-flow
- content/posts/samsung-sk-hynix-shareholder-return-kospi.md: 주주환원 -> shareholder-return
- content/posts/tsmc-foundry-price-hike-10-percent.md: 반도체 위탁생산 -> foundry
- content/posts/us-treasury-buyback-yield-rebound.md: 국채 바이백 -> treasury-buyback
- content/posts/us-treasury-buyback-yield-rebound.md: 코픽스 -> cofix
- content/dictionary/core-inflation.md: 기준금리 -> base-rate
- content/dictionary/fomc.md: 기준금리 -> base-rate
- content/dictionary/fomc.md: 원/달러 환율 -> won-dollar-exchange-rate
- content/dictionary/real-effective-exchange-rate.md: 원/달러 환율 -> won-dollar-exchange-rate

## ③ 색인 건전성
| 항목 | 결과 | 값 |
|---|---|---|
| I1 sitemap 생성 | 소견 | loc 0 ≥ 발행 39 |
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
| Q4 방치 초안 | 0건 |
| Q5 자가검토 예산 | 0 / 12 |
| P2 내부 순환 | 중앙값 3.0 |

## ⑥ 수치 무결성
| 검사 | 건수 |
|---|---|
| N1 기준일 누락 | 0 |
| N2 비1차 출처 | 0 |
| N3 교차 불일치 | 0 |
| N4 무한정 최상급 | 0 |
| N5 발행글 수치 전재 | 0 |
