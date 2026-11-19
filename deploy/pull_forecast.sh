#!/usr/bin/env bash
# VM 이 매일 받는 최신 예측·데이터허브 저장본을 이 PC 로 가져온다 (제출용 ZIP 을 만들기 전에).
#   bash deploy/pull_forecast.sh && python tools/build_zip.py
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="${QT_VM_KEY:-/e/부유물탐지/secrets/vm_wind.key}"
HOST="${QT_VM_HOST:-ubuntu@129.225.172.177}"
for f in forecast.json agent/data/datahub_wifi.json agent/data/datahub_population.json; do
  scp -q -p -i "$KEY" -o BatchMode=yes "$HOST:/opt/quiet-traveler/$f" "$f"
  echo "받음: $f ($(date -r "$f" '+%m-%d %H:%M'))"
done
