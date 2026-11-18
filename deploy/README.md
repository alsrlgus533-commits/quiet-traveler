# 시연용 서버 (Oracle Cloud VM)

공모전 시연 기간에만 띄우는 공개 주소입니다. **2027년 1월에 지웁니다** (맨 아래 '지우기').

- 주소: https://quiet.129-225-172-177.nip.io
- 서버: Oracle Cloud 무료 VM (Ubuntu 22.04), 같은 VM 의 드론 카카오봇·부유물 현황 페이지와 함께 씀
- 구조: Caddy(443, 자동 HTTPS) → 127.0.0.1:8100 `python -m agent.server`
- 질문 수 제한: 한 사람 1시간 20번, 하루 전체 300번 (`.env` 의 `CHAT_LIMIT_PER_IP_HOUR`, `CHAT_LIMIT_PER_DAY`)
- 매일 06:30 관광공사 예측·날씨, 월요일엔 제주데이터허브 저장본도 새로 받음 (`quiet-traveler-refresh.timer`)

## 올리기 / 고친 것 다시 올리기 (이 PC 에서)

```bash
bash deploy/deploy.sh            # 코드 올리고 서비스 다시 시작 (처음이면 설치까지)
```

`.env` 는 저장소에 없으므로 처음 한 번 따로 올립니다 (deploy.sh 가 처음일 때 함께 올림).

## 확인

```bash
ssh -i <키> ubuntu@129.225.172.177 'systemctl status quiet-traveler --no-pager; journalctl -u quiet-traveler -n 20 --no-pager'
```

## 지우기 (2027년 1월)

```bash
ssh -i <키> ubuntu@129.225.172.177 'bash -s' < deploy/remove.sh
```

서비스·타이머·Caddy 블록·`/opt/quiet-traveler` 를 지우고 Caddy 를 다시 읽힙니다. 드론봇과 부유물 페이지는 건드리지 않습니다.
