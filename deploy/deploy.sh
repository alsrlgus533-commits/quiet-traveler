#!/usr/bin/env bash
# 이 PC 에서 시연 VM 으로 올린다. 저장소의 커밋된 파일만 보낸다.
# forecast.json·.env 는 VM 에 없을 때(처음)만 보낸다 — VM 이 매일 직접 새로 받으므로 덮어쓰지 않는다.
# 데이터허브 저장본처럼 VM 에서 더 최근에 받은 파일도 그대로 둔다 (tar --keep-newer-files).
#   bash deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${QT_VM_KEY:-/e/부유물탐지/secrets/vm_wind.key}"
HOST="${QT_VM_HOST:-ubuntu@129.225.172.177}"
SSH=(ssh -i "$KEY" -o BatchMode=yes "$HOST")

echo "== 코드 보내기"
mkdir -p dist; tmp=$(mktemp -d -p "$PWD/dist")   # 이 PC 의 TEMP 설정이 없는 폴더를 가리켜도 되게
git archive --format=tar HEAD > "$tmp/app.tar"
if ! "${SSH[@]}" 'test -f /opt/quiet-traveler/forecast.json'; then
  echo "   (처음이라 예측 파일도 함께)"
  tar -rf "$tmp/app.tar" forecast.json
fi
"${SSH[@]}" 'sudo mkdir -p /opt/quiet-traveler && sudo chown ubuntu:ubuntu /opt/quiet-traveler && tar --keep-newer-files -xf - -C /opt/quiet-traveler 2>&1 | grep -v "is newer or same age" || true' < "$tmp/app.tar"
rm -rf "$tmp"

if ! "${SSH[@]}" 'test -f /opt/quiet-traveler/.env'; then
  echo "== .env 처음 올리기 (질문 수 제한 추가)"
  { tr -d '\r' < .env; printf '\nCHAT_LIMIT_PER_IP_HOUR=20\nCHAT_LIMIT_PER_DAY=300\nPICKS_LIMIT_PER_IP_HOUR=40\nPICKS_LIMIT_PER_DAY=500\n'; } \
    | "${SSH[@]}" 'umask 077 && cat > /opt/quiet-traveler/.env'
fi

echo "== 설치·서비스"
tr -d '\r' < deploy/remote_setup.sh | "${SSH[@]}" 'bash -s'
echo "끝: https://quiet.129-225-172-177.nip.io"
