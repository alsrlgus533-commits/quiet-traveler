#!/usr/bin/env bash
# 시연 끝나면 VM 에서 조용한 여행자만 지운다 (드론봇·부유물 페이지는 그대로).
#   ssh -i <키> ubuntu@129.225.172.177 'bash -s' < deploy/remove.sh
set -euo pipefail
sudo systemctl disable --now quiet-traveler quiet-traveler-refresh.timer 2>/dev/null || true
sudo rm -f /etc/systemd/system/quiet-traveler.service /etc/systemd/system/quiet-traveler-refresh.service /etc/systemd/system/quiet-traveler-refresh.timer
sudo systemctl daemon-reload
if grep -q 'quiet.129-225-172-177.nip.io' /etc/caddy/Caddyfile; then
  sudo cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%Y%m%d%H%M)"
  # '# 조용한 여행자' 줄부터 그 블록의 닫는 } 까지 지운다
  sudo python3 - <<'PY'
import re
p = "/etc/caddy/Caddyfile"
s = open(p, encoding="utf-8").read()
s = re.sub(r"\n# 조용한 여행자[^\n]*\nquiet\.129-225-172-177\.nip\.io \{.*?\n\}\n?", "\n", s, flags=re.S)
open(p, "w", encoding="utf-8").write(s)
PY
  sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  sudo systemctl reload caddy
fi
sudo rm -rf /opt/quiet-traveler
echo "지웠어요."
