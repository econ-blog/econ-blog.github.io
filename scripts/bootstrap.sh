#!/usr/bin/env bash
# econ-blog 무인/샌드박스 환경 부트스트랩 스크립트
# 사용법:
#   bash scripts/bootstrap.sh          # 일간 포스팅용 기본 부트스트랩
#   bash scripts/bootstrap.sh --hugo   # 주간 감사용 Hugo 포함 부트스트랩
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "=== [1/5] 환경 및 사이드카 확인 ==="
echo "저장소 루트: ${REPO_ROOT}"
if [ ! -d "../automation-data" ]; then
  echo "❌ 오류: 형제 디렉터리에 automation-data 체크아웃이 없습니다." >&2
  exit 1
fi
echo "✓ automation-data 확인 완료"

echo "=== [2/5] Git 서브모듈 동기화 ==="
git submodule update --init --recursive
echo "✓ 서브모듈 동기화 완료"

echo "=== [3/5] Python 가상환경 및 의존성 설치 ==="
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
echo "✓ Python 가상환경(.venv) 준비 완료"

echo "=== [4/5] Git 작성자 설정 ==="
git config user.name "bjh7790"
git config user.email "bjh7790@gmail.com"
echo "✓ Git 설정 완료 (bjh7790 / bjh7790@gmail.com)"

WITH_HUGO=false
for arg in "$@"; do
  if [ "$arg" = "--hugo" ]; then
    WITH_HUGO=true
  fi
done

if [ "$WITH_HUGO" = true ]; then
  echo "=== [5/5] Hugo 설치 확인 (--hugo) ==="
  INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "$INSTALL_DIR"
  export PATH="${INSTALL_DIR}:${PATH}"

  if command -v hugo >/dev/null 2>&1; then
    echo "✓ hugo 이미 설치됨 — $(hugo version)"
  else
    HUGO_VERSION="0.164.0"
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    
    # OS/아키텍처 감지
    OS_TYPE="$(uname -s | tr '[:upper:]' '[:lower:]')"
    ARCH_TYPE="$(uname -m)"
    if [ "$ARCH_TYPE" = "x86_64" ]; then
      ARCH_TYPE="amd64"
    elif [ "$ARCH_TYPE" = "aarch64" ] || [ "$ARCH_TYPE" = "arm64" ]; then
      ARCH_TYPE="arm64"
    fi

    if [ "$OS_TYPE" = "darwin" ]; then
      URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_darwin-universal.tar.gz"
    else
      URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-${ARCH_TYPE}.tar.gz"
    fi

    echo "hugo ${HUGO_VERSION} (${OS_TYPE}-${ARCH_TYPE}) 다운로드: $URL"
    if curl -sSL --max-time 180 -o "${TMP}/hugo.tar.gz" "$URL"; then
      tar xzf "${TMP}/hugo.tar.gz" -C "$TMP"
      mv "${TMP}/hugo" "${INSTALL_DIR}/hugo"
      chmod +x "${INSTALL_DIR}/hugo"
      echo "✓ hugo 설치 완료 — $("${INSTALL_DIR}/hugo" version)"
    else
      echo "⚠️ hugo 다운로드 실패. 상위 워크플로 지침에 따라 측정 불가로 진행할 수 있습니다." >&2
    fi
  fi
else
  echo "=== [5/5] 부트스트랩 완료 ==="
fi

echo "🎉 부트스트랩 완료!"
