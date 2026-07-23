"""신규 특성 발굴 — 사전 지정 없이 코퍼스 대비 과대표현 패턴을 캐낸다.

extract_features.py가 "이미 아는 것을 측정"한다면 이 스크립트는 "모르는 것을
찾는다". Monroe et al.의 정보적 디리클레 사전 log-odds를 써서 빈도 차이를
표본 크기에 맞게 보정한다 — 단순 빈도비는 희소 항목에서 폭주한다.

주제 오염 주의: 발행글 4건은 유가·후티·반도체·주담대 이야기다. 내용어를 그대로
비교하면 주제어가 상위를 독식한다. 그래서 주제 중립 위치(문장 시작/끝)와
기능어에만 적용한다.

사용:
    python3 discover.py
"""

import math
import re
from collections import Counter
from pathlib import Path

from extract_features import normalize, sentences

HERE = Path(__file__).parent
CORPUS = HERE / "reference-corpus"
POSTS = HERE.parent.parent / "content" / "posts"
SKIP = {"_index.md", "welcome.md"}

# 주제어 제어는 불용어 목록이 아니라 문서빈도로 한다. 주제어는 한두 글에만
# 몰려 나오고, 문체 패턴은 모든 글에 고르게 나온다. 손으로 쓴 목록은 다음
# 주제에서 바로 새지만 이 기준은 새 주제에도 그대로 작동한다.
MIN_DOC_FRAC = 0.75   # 발행글의 3/4 이상에 등장해야 후보로 인정


def log_odds(counts_a, counts_b, min_total=5):
    """정보적 디리클레 사전 log-odds z-score.

    z > 0 이면 A(초안)에 과대표현. |z| >= 1.96 이 관례적 유의 경계.
    """
    vocab = set(counts_a) | set(counts_b)
    n_a, n_b = sum(counts_a.values()), sum(counts_b.values())
    prior = {w: counts_a[w] + counts_b[w] for w in vocab}
    a0 = sum(prior.values())

    out = []
    for w in vocab:
        ya, yb, aw = counts_a[w], counts_b[w], prior[w]
        if ya + yb < min_total:
            continue
        d = (math.log((ya + aw) / (n_a + a0 - ya - aw))
             - math.log((yb + aw) / (n_b + a0 - yb - aw)))
        var = 1.0 / (ya + aw) + 1.0 / (yb + aw)
        out.append((d / math.sqrt(var), w, ya, yb))
    return sorted(out, reverse=True)


def features_from(text):
    """주제 중립 위치에서 패턴을 뽑는다."""
    norm = normalize(text)
    sents = [s for s in sentences(norm) if len(s) >= 6]
    paras = [p for p in re.split(r"\n\s*\n", norm) if p.strip()]

    tail4 = Counter(re.sub(r"[^\w가-힣]+$", "", s)[-4:] for s in sents)
    head2 = Counter(s.split()[0] for s in sents if s.split())
    para_head = Counter(" ".join(p.split()[:2]) for p in paras if len(p.split()) >= 2)
    words = Counter(w for w in norm.split() if 2 <= len(w) <= 6)
    return {"문장 끝 4음절": tail4, "문장 첫 어절": head2,
            "문단 첫 두 어절": para_head, "어절": words}


def merge(files):
    """빈도 합계와 함께 문서빈도(몇 개 문서에 등장했는지)를 센다."""
    acc, docfreq = None, None
    for f in files:
        d = features_from(f.read_text(encoding="utf-8"))
        if acc is None:
            acc = {k: Counter() for k in d}
            docfreq = {k: Counter() for k in d}
        for k in acc:
            acc[k].update(d[k])
            docfreq[k].update(set(d[k]))
    return acc, docfreq


def main():
    corpus_files = sorted(CORPUS.glob("*.md"))
    post_files = [p for p in sorted(POSTS.glob("*.md")) if p.name not in SKIP]
    print(f"코퍼스 {len(corpus_files)}건 vs 발행글 {len(post_files)}건")
    print("z > 0 = 발행글에 과대표현.  |z| >= 1.96 이 관례적 유의 경계.\n")

    c, _ = merge(corpus_files)
    p, pdf = merge(post_files)
    need = math.ceil(MIN_DOC_FRAC * len(post_files))
    print(f"주제어 제어: 발행글 {need}/{len(post_files)}건 이상에 등장한 패턴만 후보\n")

    for bucket in c:
        z = log_odds(p[bucket], c[bucket])
        sig = [r for r in z if abs(r[0]) >= 1.96]
        spread = [r for r in sig if r[0] < 0 or pdf[bucket][r[1]] >= need]
        dropped = len(sig) - len(spread)
        print(f"── {bucket} " + "─" * (52 - len(bucket)))
        if not spread:
            print(f"   유의한 항목 없음 (주제어로 탈락 {dropped}건)\n")
            continue
        print(f"   {'패턴':<16}{'z':>7}{'발행글':>7}{'코퍼스':>7}{'문서':>6}")
        for zz, w, ya, yb in spread[:6]:
            if zz > 0:
                print(f"   {w:<16}{zz:>7.2f}{ya:>7}{yb:>7}{pdf[bucket][w]:>6}   과대")
        for zz, w, ya, yb in spread[-6:][::-1]:
            if zz < 0:
                print(f"   {w:<16}{zz:>7.2f}{ya:>7}{yb:>7}{pdf[bucket][w]:>6}   과소")
        print(f"   (주제어로 탈락 {dropped}건)\n")


if __name__ == "__main__":
    main()
