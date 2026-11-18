# 조용한 여행자 — 제주 혼잡 회피 여행·관광 분석 AI Agent

"이번 토요일 비 안 오고 덜 붐비는 숲길 어디야?", "다음 주 평소보다 붐빌 관광지 순위 알려줘"처럼 **일상 언어로 물으면**, 에이전트가 제주데이터허브·관광공사·기상청 데이터를 골라 조회하고 계산해 **근거가 붙은 답**(장소, 시간, 코스, 순위, 길안내 링크)을 돌려준다.

- 출품: 제주 AI·빅데이터 활용 AI Agent 개발 챌린지 (제주빅데이터센터)
- 필수 데이터: **제주데이터허브 OpenAPI 3종** — 「와이파이 AP그룹별 일일 사용량」(매일 갱신), 「읍면동 단위 내국인 유동인구」, 「관광지·상업지구 시간대별 카드 데이터」 (자세한 내용: [docs/데이터_활용_명세.md](docs/데이터_활용_명세.md))
- AI: **업스테이지 Solar Pro 4** (`solar-pro4`, OpenAI 호환 Chat Completions + 함수 호출)

## 빠른 실행 (3단계)

필요한 것: **Python 3.10 이상**, 인터넷 연결, 업스테이지 API 키.

```bash
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env  → .env 에 UPSTAGE_API_KEY 입력
python -m agent.server
```

브라우저에서 **http://localhost:8000** 을 열고 "물어보세요" 칸에 질문한다.
화면 사용법은 [docs/사용자_매뉴얼.md](docs/사용자_매뉴얼.md).

- 제출본에는 관광공사 예측·날씨(`forecast.json`)와 제주데이터허브 데이터 저장본(와이파이·유동인구·카드)이 들어 있어 **업스테이지 키 하나만으로 바로 실행**된다.
- 최신 예측·날씨로 바꾸려면 `.env` 에 `TOUR_API_KEY`(공공데이터포털)·`KMA_API_KEY`(기상청 API허브)를 넣고 `python fetch_forecast.py` 를 돌린다.
- 제주데이터허브 저장본을 최신으로 바꾸려면 `.env` 에 `JEJU_DATAHUB_KEY` 를 넣고 `python -m agent.datahub` 를 돌린다 (1~2분).
- 질문 한 번만 시험할 때: `python -m agent.agent "이번 주말 덜 붐비는 바다 추천해 줘"`

## 구조

```
질문 (화면 대화창 또는 명령줄)
  └→ agent/agent.py   업스테이지 Solar 가 도구를 고르고 결과를 받아 답을 쓴다 (최대 6회 도구 호출)
        └→ agent/tools.py   도구 8개 — 숫자는 모두 여기서 계산 (AI 가 숫자를 지어내지 않게)
              ├ find_quiet_places     날짜·시간·테마로 한산한 곳 찾기
              ├ place_forecast        한 장소의 시간대별·14일 예측, 가장 한산한 날
              ├ get_weather           기상청 단기·중기예보 (없는 날 Open-Meteo)
              ├ plan_course           한산한 곳을 이어 코스 (이동·머무는 시간, 해 지는 시각, 비 예보 반영)
              ├ rank_spots            제주 관광지 448곳의 '평소 대비' 붐빔 순위 (분석 질문)
              ├ wifi_visitors         제주데이터허브 와이파이 접속자로 본 최근 실제 붐빔·요일 패턴
              ├ area_visitors         제주데이터허브 유동인구로 본 읍면동 요일 패턴·주민 대비 방문 비율
              └ jeju_card_time_pattern 제주데이터허브 카드 데이터로 지구별 시간대 결제 비율
                    └→ agent/core.py   계산식 (화면 index.html 과 같은 식) · agent/datahub.py 데이터허브 연동
```

| 파일 | 내용 |
|---|---|
| `agent/agent.py` | 에이전트 실행 루프, 시스템 프롬프트(`SYSTEM`) |
| `agent/tools.py` | 도구 함수와 도구 설명(함수 호출 스키마 `TOOLS`) |
| `agent/core.py` | 한산함 점수·코스·날씨 판단 계산 |
| `agent/datahub.py` | 제주데이터허브 API 호출과 저장본 (`python -m agent.datahub` 로 갱신) |
| `agent/server.py` | 화면과 `/api/chat` 을 함께 띄우는 로컬 서버 (표준 라이브러리) |
| `agent/data/places.json` | 장소 53곳(조용한 곳 16, 유명한 곳 37) — `node tools/export_places.mjs` 로 화면에서 뽑음 |
| `agent/data/datahub_wifi.json` | 제주데이터허브 와이파이 저장본 (최근 35일, 장소 37곳 AP) |
| `agent/data/datahub_population.json` | 제주데이터허브 유동인구 저장본 (최근 8주, 43개 읍면동) |
| `agent/data/datahub_card_time.json` | 제주데이터허브 카드 데이터 저장본 |
| `index.html` | 모바일 웹 화면(날짜·시간 선택, 지도, 코스, 대화창) |
| `fetch_forecast.py` | 관광공사 예측 + 날씨 수집 → `forecast.json` |
| `docs/` | 사용자 매뉴얼, 데이터 활용 명세, 개발 메모 |

## 사용 모델·라이브러리·외부 서비스

| 구분 | 이름 | 용도 |
|---|---|---|
| AI 모델 | 업스테이지 Solar Pro 4 (`solar-pro4`) | 질문 해석, 도구 선택, 답 작성 |
| 라이브러리 | `openai` (Python) | 업스테이지 OpenAI 호환 API 호출 (`base_url=https://api.upstage.ai/v1`) |
| 라이브러리 | Python 표준 라이브러리 | 서버, 데이터 수집, 계산 |
| 외부 API | 제주데이터허브 OpenAPI | 필수 데이터 (와이파이 일일 사용량, 읍면동 유동인구, 카드 시간대별) |
| 외부 API | 공공데이터포털 한국관광공사 집중률 예측, TourAPI | 관광지 30일 예측, 좌표·사진 |
| 외부 API | 기상청 API허브 단기·중기예보, Open-Meteo | 날씨 |
| 외부 API | 비짓제주 OPEN API | 일부 장소 좌표·사진 |
| 웹 폰트 | Google Fonts (Gowun Batang, IBM Plex Sans KR) | 화면 글꼴 |

**AI 활용 범위:** 서비스 안에서는 업스테이지 Solar 가 질문 해석·도구 선택·설명을 맡고, 모든 수치는 도구가 데이터로 계산한다. 개발 과정에서는 코드 작성 보조에 Anthropic Claude(Claude Code)를, 배경·테마 일러스트 생성에 ComfyUI(Qwen-Image)를 사용했다. 특정 장소 사진은 AI 생성 이미지를 쓰지 않고 관광공사·비짓제주 사진을 썼다.

## 환경변수 (`.env`)

| 이름 | 필수 | 발급 |
|---|---|---|
| `UPSTAGE_API_KEY` | **필수** | console.upstage.ai → API Keys |
| `UPSTAGE_MODEL` | 선택 | 기본 `solar-pro4` |
| `JEJU_DATAHUB_KEY` | 선택 | jejudatahub.net 로그인 → 마이페이지 → 프로젝트 키 (저장본 갱신 시) |
| `TOUR_API_KEY` | 선택 | data.go.kr 일반 인증키 + 관광지 집중률 예측(15128555)·TourAPI·기상청 단기/중기예보 활용신청 |
| `KMA_API_KEY` | 선택 | apihub.kma.go.kr 인증키 + 단기예보·중기예보(육상·기온) 활용신청 |
| `PORT` | 선택 | 서버 포트, 기본 8000 |

실제 API 키는 제출물에 넣지 않는다. 평가용 업스테이지 키는 사용 한도를 걸어 별도로 전달하고, 평가 후 폐기한다.

## 오류와 제약

- **"AI 키가 없어 대화가 꺼져 있어요"**: `.env` 의 `UPSTAGE_API_KEY` 를 확인한다. 키가 없어도 화면의 추천·지도·코스는 동작한다.
- **포트 사용 중**: `python -m agent.server --port 9000`
- **한산함·주차는 실시간 측정이 아니라 추정**이다. 관광공사 30일 예측(장소별 평소 대비) × 장소 규모 × 유형별 시간대 곡선으로 만든다.
- 관광공사 예측이 없는 장소(일부 마을, 사려니숲길)는 제주 전체 예측과 유형별 패턴으로 추정한다.
- 제주데이터허브 와이파이는 약 3일, 유동인구는 2~3달 늦게 올라온다. 그래서 앞날은 관광공사 예측으로, '요즘 실제로 어땠는지'는 와이파이로, 요일·지역 성향은 유동인구로 답한다.
- 와이파이 접속자는 방문객의 일부라 장소끼리 숫자를 견주지 않고 같은 장소의 변화만 본다.
- 제주데이터허브 카드 데이터는 API 로 값이 오는 공개분이 오래돼 **시간대 비율 근거로만** 쓴다.
- 길안내 링크는 카카오맵·네이버 지도 웹 주소다. 휴대폰에서는 앱으로 이어서 열 수 있다.
- 답은 AI 가 쓰므로 표현이 매번 조금 다를 수 있다. 숫자는 도구 결과에서만 가져오도록 지시했다.
