"""한국관광공사 '관광지 집중률 방문자 추이 예측' API에서 제주 관광지 30일 예측을 받아
forecast.json 으로 저장한다. (표준 라이브러리만 사용)

사용법
  1) 공공데이터포털(data.go.kr)에서 '한국관광공사_관광지 집중률 방문자 추이 예측 정보'
     (15128555) 활용신청 후 일반 인증키(Decoding)를 받는다.
  2) 이 폴더의 .env 파일에 한 줄 적는다:   TOUR_API_KEY=발급받은키
     (또는 환경변수 TOUR_API_KEY)
  3) python fetch_forecast.py            -> 실제 데이터로 forecast.json 갱신
     python fetch_forecast.py --sample   -> 키 없이 화면 확인용 샘플 생성
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "forecast.json")
BASE = "https://apis.data.go.kr/B551011/TatsCnctrRateService"
# 명세의 상세기능 영문명이 공개 페이지에 없어 후보를 차례로 시도한다.
OPERATIONS = ["tatsCnctrRatedList", "tatsCnctrRateList"]
AREA_CD = "50"                                   # 제주특별자치도
SIGUNGU = {"50110": "제주시", "50130": "서귀포시"}

# 응답 필드명이 바뀌어도 동작하도록 후보 키를 둔다.
KEYS = {
    "date": ["baseYmd", "baseDate", "ymd"],
    "name": ["tAtsNm", "tatsNm", "atsNm"],
    "rate": ["cnctrRate", "cnctrRt", "rate"],
}


def pick(item, field):
    for k in KEYS[field]:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return None


def load_key():
    key = os.environ.get("TOUR_API_KEY")
    env = os.path.join(HERE, ".env")
    if not key and os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if line.strip().startswith("TOUR_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def call(op, key, sigungu, page):
    q = urllib.parse.urlencode({
        "serviceKey": key, "pageNo": page, "numOfRows": 1000,
        "MobileOS": "WEB", "MobileApp": "QuietTraveler",
        "areaCd": AREA_CD, "signguCd": sigungu, "_type": "json",
    })
    with urllib.request.urlopen(f"{BASE}/{op}?{q}", timeout=30) as r:
        raw = r.read().decode("utf-8")
    try:
        body = json.loads(raw)["response"]["body"]
    except (ValueError, KeyError):
        raise RuntimeError(raw[:300])
    items = (body.get("items") or {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    return items, int(body.get("totalCount") or 0)


def fetch_real(key):
    last_err = None
    for op in OPERATIONS:
        try:
            rows = []
            for code, sg in SIGUNGU.items():
                page = 1
                while True:
                    items, total = call(op, key, code, page)
                    for it in items:
                        rate = pick(it, "rate")
                        rows.append({
                            "date": str(pick(it, "date")),
                            "name": pick(it, "name"),
                            "sigungu": sg,
                            "rate": round(float(rate), 1) if rate is not None else None,
                        })
                    if page * 1000 >= total or not items:
                        break
                    page += 1
            if rows:
                print(f"[ok] {op}: {len(rows)}건")
                return rows
        except Exception as e:  # 다음 후보 오퍼레이션 시도
            last_err = e
    raise SystemExit(f"API 호출 실패: {last_err}\n키, 활용신청 승인 여부, 오퍼레이션명을 확인하세요.")


def make_sample():
    """키 없이 화면을 볼 수 있게 만든 가짜 예측값. 실제 수치가 아니다.

    이름은 index.html 의 SWAPS.api / API_NAME 과 글자까지 같아야 앱이 읽는다.
    (실제 API 가 주는 관광지명 그대로다. 줄여 쓰면 앱에서 전부 '패턴 추정'이 된다.)
    """
    spots = {
        # 유명 관광지 (index.html 의 SWAPS)
        "성산일출봉 [유네스코 세계자연유산]": ("서귀포시", 78), "섭지코지": ("서귀포시", 66),
        "쇠소깍": ("서귀포시", 64), "비자림": ("제주시", 72), "협재해수욕장": ("제주시", 74),
        "월정리해변(월정리해수욕장)": ("제주시", 69), "새별오름": ("제주시", 62),
        "우도(해양도립공원)": ("제주시", 80), "한담해변": ("제주시", 67),
        # 조용한 곳 (index.html 의 API_NAME)
        "삼다수숲길": ("제주시", 40), "머체왓숲길": ("서귀포시", 40), "서귀포 치유의 숲": ("서귀포시", 40),
        "따라비 오름": ("서귀포시", 40), "안돌오름": ("제주시", 40),
        "저지오름(닥몰오름,새오름)": ("제주시", 40), "평대해변": ("제주시", 40), "판포포구": ("제주시", 40),
        "신창풍차해안도로": ("제주시", 40), "오조포구": ("서귀포시", 40), "수월봉": ("제주시", 40),
        "대평포구": ("서귀포시", 40), "제주 하도리 철새도래지": ("제주시", 40),
    }
    rnd = random.Random(7)
    today = dt.date.today()
    rows = []
    for i in range(30):
        d = today + dt.timedelta(days=i)
        weekend = 1.18 if d.weekday() >= 5 else 1.0
        for name, (sg, base) in spots.items():
            v = base * weekend + rnd.uniform(-9, 9)
            rows.append({"date": d.strftime("%Y%m%d"), "name": name, "sigungu": sg,
                         "rate": round(max(5, min(100, v)), 1)})
    return rows


def main():
    sample = "--sample" in sys.argv
    if sample:
        rows = make_sample()
    else:
        key = load_key()
        if not key:
            raise SystemExit("TOUR_API_KEY 가 없습니다. .env 에 넣거나 --sample 로 실행하세요.")
        rows = fetch_real(key)
    data = {
        "source": "한국관광공사 관광지 집중률 방문자 추이 예측 정보 (data.go.kr 15128555)",
        "sample": sample,
        "fetchedAt": dt.datetime.now().isoformat(timespec="minutes"),
        "items": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"저장: {OUT} ({len(rows)}건, sample={sample})")


if __name__ == "__main__":
    main()
