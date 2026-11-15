# 조용한 여행자

덜 붐비고 조용한 제주를 찾는 사람을 위한 모바일웹. 날짜와 도착 시간을 고르면 숲길·오름·바다·마을 16곳을 한산한 순서로 보여 주고, 붐비는 유명 관광지 대신 갈 곳을 추천한다.

- 게시 주소(비공개 아티팩트): https://claude.ai/artifact/LuzrfCCKbaxkDN31eMbfYg

## 파일

| 파일 | 내용 |
|---|---|
| `index.html` | 앱 전체(HTML·CSS·JS 한 파일). 장소 목록 `PLACES`, 대신 가기 `SWAPS`, 예측 API 관광지명 `API_NAME` 이 맨 위 스크립트에 있음 |
| `forecast.json` | 한국관광공사 관광지 집중률 30일 예측(제주 448곳). git 에 올리지 않음 — 각 PC에서 `fetch_forecast.py` 로 생성 |
| `timeofday.json` | 제주데이터허브 시간대별 카드 결제 비율. 과거 자료라 다시 받을 필요 없음 |
| `timeofday_raw.json` | 위 비율을 계산한 원본 응답 |
| `fetch_forecast.py` | 관광공사 예측 받기 (`--sample` 이면 키 없이 샘플 생성) |
| `fetch_timeofday.py` | 데이터허브 시간대별 카드 데이터 받기 |
| `.env.example` | API 키 자리. 복사해서 `.env` 로 만들어 씀 |

## 다른 PC에서 시작하기

필요한 것: Git, Python 3.10 이상(추가 패키지 없음), GitHub 로그인.

```bash
git clone https://github.com/alsrlgus533-commits/quiet-traveler.git
cd quiet-traveler
copy .env.example .env      # macOS/Linux 는 cp
```

`.env` 에 키를 채운다. 키는 git 에 올라가 있지 않으므로 원래 PC의 `.env` 에서 옮기거나 공공데이터포털·데이터허브 마이페이지에서 다시 확인한다.

예측 파일(`forecast.json`)도 git 에 없으므로 처음 한 번 받는다:

```bash
python fetch_forecast.py
```

로컬에서 보기:

```bash
python -m http.server 5173
```

브라우저에서 http://localhost:5173 을 연다. (`index.html` 을 더블클릭해 열거나 `forecast.json` 이 없으면 샘플 예측으로 보인다.)

## 작업을 옮길 때

- 시작 전 `git pull`, 끝나면 `git add -A && git commit -m "..." && git push`.
- 원래 PC에는 매일 06:43쯤 예측을 받아 아티팩트를 재게시하는 Claude 예약 작업(`quiet-traveler-daily-refresh`)이 있다. 그 작업은 원래 PC의 `E:\데이터랩 활용\quiet-traveler` 폴더를 쓴다. 다른 PC에서 수정한 내용이 게시되려면 원래 PC에서도 `git pull` 해야 한다.
- 이미지는 `images/` 폴더에 `hero`, `forest`, `oreum`, `sea`, `village` 이름으로 넣을 예정(WebP, 가로 1200px, 장당 200KB 이하 권장). 특정 장소 사진 자리에는 AI 이미지를 쓰지 않는다.

## 데이터 출처

- 한국관광공사 관광지 집중률 방문자 추이 예측 정보 (data.go.kr 15128555) — 이동통신 방문자 데이터 기반 30일 예측. 집중률은 각 관광지의 자기 평소 대비 값이라 장소끼리 사람 수 비교에는 쓰지 않는다.
- 제주데이터허브 관광지·상업지구 시간대별 카드 데이터 (내국인 관광객·내국인 주요 관광지) — API에서 실제로 나온 건 2017년 11월분뿐. 시간대 비율만 곡선 보정(35%)에 사용.
