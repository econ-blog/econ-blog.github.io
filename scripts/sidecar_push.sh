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
git push
echo "sidecar: $DEST 배달 완료"
