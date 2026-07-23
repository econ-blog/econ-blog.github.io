"""발행글 대조 진단 — 발행글이 참조 코퍼스 분포의 어디에 있는지 본다.

이 결과는 feature-spec.yaml의 genre_invariant를 사람이 정할 때 쓰는 참고
자료다. 루프가 이 값으로 자동 판단하지 않는다. 발행글도 LLM이 쓴 것이므로
"장르 차이"와 "사람이 문제 삼지 않은 AI 흔적"을 구분하지 못한다.

사용:
    python3 diagnose.py
"""

import statistics as st
import sys
from pathlib import Path

from extract_features import FEATURES, extract

HERE = Path(__file__).parent
CORPUS = HERE / "reference-corpus"
POSTS = HERE.parent.parent / "content" / "posts"
SKIP = {"_index.md", "welcome.md"}


def percentile_of(value, dist):
    """dist 안에서 value가 차지하는 백분위(0~100)."""
    below = sum(1 for d in dist if d < value)
    equal = sum(1 for d in dist if d == value)
    return 100.0 * (below + 0.5 * equal) / len(dist)


def main():
    corpus_files = sorted(CORPUS.glob("*.md"))
    post_files = [p for p in sorted(POSTS.glob("*.md")) if p.name not in SKIP]
    if len(corpus_files) < 30:
        sys.exit(f"코퍼스 {len(corpus_files)}건 — 스펙 하한 30건 미달. 수집을 더 해야 한다.")

    corpus = [extract(f.read_text(encoding="utf-8")) for f in corpus_files]
    posts = [extract(f.read_text(encoding="utf-8")) for f in post_files]
    print(f"코퍼스 {len(corpus)}건 vs 발행글 {len(posts)}건\n")

    hdr = f"{'특성':<22}{'코퍼스 중앙':>12}{'코퍼스 IQR':>18}{'발행글 평균':>12}{'백분위':>9}  판정"
    print(hdr)
    print("-" * len(hdr))

    outside = []
    for name in FEATURES:
        cd = sorted(d[name] for d in corpus)
        pv = st.mean(d[name] for d in posts)
        q1, q3 = st.quantiles(cd, n=4)[0], st.quantiles(cd, n=4)[2]
        pct = percentile_of(pv, cd)
        flag = "" if 25 <= pct <= 75 else ("▲ 높음" if pct > 75 else "▼ 낮음")
        if flag:
            outside.append((name, pct, st.median(cd), pv))
        print(f"{name:<22}{st.median(cd):>12.4g}{f'[{q1:.3g}, {q3:.3g}]':>18}"
              f"{pv:>12.4g}{pct:>8.0f}%  {flag}")

    print(f"\n[25, 75] 밖: {len(outside)}/{len(FEATURES)}개 특성")
    for name, pct, med, pv in sorted(outside, key=lambda x: -abs(x[1] - 50)):
        print(f"  {name:<22} 백분위 {pct:>5.0f}%   코퍼스중앙 {med:.4g} → 발행글 {pv:.4g}")
    print("\n각 항목은 '장르 차이'와 'AI 흔적' 중 어느 쪽인지 사람이 판정해야 한다.")


if __name__ == "__main__":
    main()
