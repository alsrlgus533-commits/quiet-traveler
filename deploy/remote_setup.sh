#!/usr/bin/env bash
# VM 안에서 돈다 (deploy.sh 가 ssh 로 보냄). 여러 번 돌려도 같은 결과.
set -euo pipefail
APP=/opt/quiet-traveler
cd "$APP"

# 파이썬 가상환경과 패키지
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip >/dev/null
.venv/bin/pip install -q -r requirements.txt

# 화면 + 에이전트 서버 (127.0.0.1:8100, 바깥에는 Caddy 로만 열림)
sudo tee /etc/systemd/system/quiet-traveler.service >/dev/null <<'UNIT'
[Unit]
Description=Quiet Traveler (contest demo, remove 2027-01)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/quiet-traveler
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/quiet-traveler/.venv/bin/python -m agent.server --host 127.0.0.1 --port 8100
Restart=always
RestartSec=5
MemoryMax=250M

[Install]
WantedBy=multi-user.target
UNIT

# 매일 06:30 예측·날씨, 월요일엔 데이터허브 저장본도 새로 받기
sudo tee /etc/systemd/system/quiet-traveler-refresh.service >/dev/null <<'UNIT'
[Unit]
Description=Quiet Traveler daily data refresh

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/opt/quiet-traveler
ExecStart=/opt/quiet-traveler/.venv/bin/python fetch_forecast.py
ExecStart=/bin/sh -c '[ "$$(date +%%u)" = 1 ] && /opt/quiet-traveler/.venv/bin/python -m agent.datahub || true'
UNIT
sudo tee /etc/systemd/system/quiet-traveler-refresh.timer >/dev/null <<'UNIT'
[Unit]
Description=Quiet Traveler daily data refresh timer

[Timer]
OnCalendar=*-*-* 06:30:00 Asia/Seoul
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now quiet-traveler-refresh.timer >/dev/null
sudo systemctl enable quiet-traveler >/dev/null
sudo systemctl restart quiet-traveler

# Caddy: 기존 블록은 그대로 두고, 새 주소 블록만 (없을 때) 덧붙인다
if ! grep -q 'quiet.129-225-172-177.nip.io' /etc/caddy/Caddyfile; then
  sudo cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%Y%m%d%H%M)"
  sudo tee -a /etc/caddy/Caddyfile >/dev/null <<'CADDY'

# 조용한 여행자 (제주 AI Agent 공모전 시연용, 2027년 1월 삭제 예정)
quiet.129-225-172-177.nip.io {
	encode zstd gzip
	header X-Robots-Tag "noindex, nofollow"
	reverse_proxy 127.0.0.1:8100
}
CADDY
  sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  sudo systemctl reload caddy
fi

sleep 2
curl -fsS http://127.0.0.1:8100/api/health && echo
systemctl is-active quiet-traveler
