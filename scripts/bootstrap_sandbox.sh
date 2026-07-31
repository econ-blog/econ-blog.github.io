#!/usr/bin/env bash
# 루틴 샌드박스용 Hugo 설치. 로컬(이미 설치됨)에서는 no-op.
# github.com 릴리스는 샌드박스 allowlist에 있다 (프로브 ③, 2026-07-30).
set -euo pipefail

HUGO_VERSION="0.164.0"   # .github/workflows/hugo.yml 의 HUGO_VERSION 과 일치해야 한다
INSTALL_DIR="${HOME}/.local/bin"

if command -v hugo >/dev/null 2>&1; then
  echo "bootstrap: hugo 이미 설치됨 — $(hugo version)"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz"

echo "bootstrap: hugo ${HUGO_VERSION} 다운로드"
curl -sSL --max-time 180 -o "${TMP}/hugo.tar.gz" "$URL"
tar xzf "${TMP}/hugo.tar.gz" -C "$TMP"

mkdir -p "$INSTALL_DIR"
mv "${TMP}/hugo" "${INSTALL_DIR}/hugo"
chmod +x "${INSTALL_DIR}/hugo"
export PATH="${INSTALL_DIR}:${PATH}"

echo "bootstrap: $(hugo version)"
echo "bootstrap: PATH 에 ${INSTALL_DIR} 를 추가하라 — export PATH=\"${INSTALL_DIR}:\$PATH\""
