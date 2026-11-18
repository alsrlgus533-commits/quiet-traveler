#!/usr/bin/env bash
# 이 PC 에서 시연 VM 으로 올린다. 저장소의 커밋된 파일 + forecast.json 만 보낸다 (.env 는 처음 한 번만).
#   bash deploy/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${QT_VM_KEY:-/e/부유물탐지/secrets/vm_wind.key}"
HOST="${QT_VM_HOST:-ubuntu@129.225.172.177}"
SSH=(ssh -i "$KEY" -o BatchMode=yes "$HOST")

echo "== 코드 보내기"
tmp=$(mktemp -d)
git archive --format=tar HEAD > "$tmp/app.tar"
tar -rf "$tmp/app.tar" forecast.json
"${SSH[@]}" 'sudo mkdir -p /opt/quiet-traveler && sudo chown ubuntu:ubuntu /opt/quiet-traveler && tar -xf - -C /opt/quiet-traveler' < "$tmp/app.tar"
rm -rf "$tmp"

if ! "${SSH[@]}" 'test -f /opt/quiet-traveler/.env'; then
  echo "== .env 처음 올리기 (질문 수 제한 추가)"
  { tr -d '\r' < .env; printf '\nCHAT_LIMIT_PER_IP_HOUR=20\nCHAT_LIMIT_PER_DAY=300\n'; } \
    | "${SSH[@]}" 'umask 077 && cat > /opt/quiet-traveler/.env'
fi

echo "== 설치·서비스"
"${SSH[@]}" 'bash -s' < deploy/remote_setup.sh
echo "끝: https://quiet.129-225-172-177.nip.io"
