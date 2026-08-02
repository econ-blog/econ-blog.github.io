#!/usr/bin/env bash
# 사이드카 저장소에 스냅샷을 배달한다. GitHub Actions 전용.
# 사용: sidecar_push.sh <src_dir> <dest_subdir>
#   PAT 환경변수 필요. 변경이 없으면 커밋하지 않고 0으로 종료한다.
set -euo pipefail

SRC="$1"
DEST="$2"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git config --local --unset-all http.https://github.com/.extraheader 2>/dev/null || true
git config --global --unset-all http.https://github.com/.extraheader 2>/dev/null || true

git clone --depth 1 "https://x-access-token:${PAT}@github.com/econ-blog/automation-data.git" "$WORK"
mkdir -p "$WORK/$DEST"
cp -R "$SRC"/. "$WORK/$DEST"/

cd "$WORK"
git config user.name "bjh7790"
git config user.email "bjh7790@gmail.com"
git add -A

if git diff --cached --quiet; then
  echo "sidecar: 변경 없음 — 커밋 생략"
  exit 0
fi

git commit -m "data: $DEST"

# 같은 순간에 다른 잡이 밀면 non-fast-forward로 튕긴다. weekly-collect의 두 잡이
# 병렬이고 일요일에는 daily-collect까지 겹치므로 단발 push는 안전하지 않다.
# 재시도 전에 rebase한다 — 각 잡이 서로 다른 경로에만 쓰므로 충돌 파일은 없다.
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
for attempt in 1 2 3 4 5; do
  if git push origin "$BRANCH"; then
    echo "sidecar: $DEST 배달 완료"
    exit 0
  fi
  echo "sidecar: push 거부 — rebase 후 재시도 ($attempt/5)"
  sleep $(( attempt * 3 ))
  # depth 1 클론이라 rebase가 공통 조상을 못 찾는다. 첫 재시도에서 이력을 편다.
  git fetch --unshallow origin "$BRANCH" 2>/dev/null || git fetch origin "$BRANCH"
  git rebase "origin/$BRANCH"
done

echo "sidecar: push 5회 실패 — $DEST 배달 못 함" >&2
exit 1
