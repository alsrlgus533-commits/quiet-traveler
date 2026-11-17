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


# ---------- 날씨 예보 ----------
# 하늘 상태는 sun(맑음) · partly(구름많음) · cloud(흐림) · fog(안개) · rain(비) · shower(소나기) · snow(눈) · storm(뇌우)
# 일곱 가지로 맞춘다. 두 지점(제주시·서귀포시)을 받으면 더 나쁜 쪽을 그날 제주 날씨로 쓴다.
SKY_RANK = {"sun": 0, "partly": 1, "cloud": 2, "fog": 3, "shower": 4, "rain": 5, "snow": 6, "storm": 7}
SKY_WORD = {"sun": "맑음", "partly": "구름많음", "cloud": "흐림", "fog": "안개", "shower": "소나기",
            "rain": "비", "snow": "눈", "storm": "뇌우"}


def merge_days(per):
    out = {}
    for day, v in per.items():
        worst = max(v, key=lambda x: SKY_RANK.get(x["sky"], 0))
        tx = [x["tmax"] for x in v if x.get("tmax") is not None]
        tn = [x["tmin"] for x in v if x.get("tmin") is not None]
        pop = max((x.get("pop") or 0) for x in v)
        sky = worst["sky"]
        # 잠깐 오는 이슬비 때문에 하루 종일 '비'로 보이지 않게: 비 올 확률이 40% 미만이면 흐림으로 본다.
        if sky in ("rain", "shower", "snow", "storm") and pop < 40:
            sky = "cloud"
        out[day] = {"sky": sky, "word": SKY_WORD[sky],
                    "tmax": round(sum(tx) / len(tx)) if tx else None,
                    "tmin": round(sum(tn) / len(tn)) if tn else None,
                    "pop": pop}
    return out


def kma_get(key, url, params):
    q = urllib.parse.urlencode({"serviceKey": key, "pageNo": 1, "dataType": "JSON", **params})
    with urllib.request.urlopen(url + "?" + q, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))["response"]["body"]
    items = (body.get("items") or {}).get("item") or []
    return [items] if isinstance(items, dict) else items


def kma_word_sky(w):
    """중기예보 문장(예: '구름많고 비', '흐리고 눈')을 하늘 상태로."""
    w = w or ""
    if "눈" in w: return "snow"
    if "소나기" in w: return "shower"
    if "비" in w: return "rain"
    if "흐림" in w or "흐리" in w: return "cloud"
    if "구름" in w: return "partly"
    return "sun"


def fetch_kma(key):
    """기상청 단기예보(오늘~3일) + 중기예보(4~10일). 공공데이터포털에서 두 서비스 활용신청이 필요하다."""
    now = dt.datetime.now()
    per = {}
    # 단기예보: 05시 발표분(05:10 이후)을, 그 전이면 전날 23시 발표분을 쓴다.
    if now.hour * 60 + now.minute >= 5 * 60 + 15:
        bd, bt = now.strftime("%Y%m%d"), "0500"
    else:
        bd, bt = (now - dt.timedelta(days=1)).strftime("%Y%m%d"), "2300"
    for nx, ny in [(53, 38), (52, 33)]:                     # 제주시, 서귀포시 격자
        items = kma_get(key, "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
                        {"base_date": bd, "base_time": bt, "nx": nx, "ny": ny, "numOfRows": 1500})
        days = {}
        for it in items:
            d = days.setdefault(it["fcstDate"], {"sky": [], "pty": [], "pop": 0, "tmax": None, "tmin": None})
            hh, c, v = int(it["fcstTime"][:2]), it["category"], it["fcstValue"]
            if c == "TMX": d["tmax"] = float(v)
            elif c == "TMN": d["tmin"] = float(v)
            elif c == "POP": d["pop"] = max(d["pop"], int(v))
            elif 9 <= hh <= 18 and c == "SKY": d["sky"].append(int(v))
            elif 9 <= hh <= 18 and c == "PTY": d["pty"].append(int(v))
        for day, d in days.items():
            pty = [p for p in d["pty"] if p]
            if pty:
                sky = "snow" if any(p in (2, 3) for p in pty) else "shower" if all(p == 4 for p in pty) else "rain"
            elif d["sky"]:
                avg = sum(d["sky"]) / len(d["sky"])
                sky = "cloud" if avg >= 3.5 else "partly" if avg >= 2 else "sun"
            else:
                continue
            per.setdefault(day, []).append({"sky": sky, "tmax": d["tmax"], "tmin": d["tmin"], "pop": d["pop"]})
    # 중기예보: 06시·18시 발표. 3~10일 뒤.
    tmfc = now.strftime("%Y%m%d") + ("1800" if now.hour >= 18 else "0600")
    if now.hour < 6:
        tmfc = (now - dt.timedelta(days=1)).strftime("%Y%m%d") + "1800"
    base = dt.datetime.strptime(tmfc[:8], "%Y%m%d").date()
    land = kma_get(key, "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst", {"regId": "11G00000", "tmFc": tmfc, "numOfRows": 10})
    ta = kma_get(key, "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidTa", {"regId": "11G00201", "tmFc": tmfc, "numOfRows": 10})
    land, ta = (land[0] if land else {}), (ta[0] if ta else {})
    for n in range(3, 11):
        day = (base + dt.timedelta(days=n)).strftime("%Y%m%d")
        if day in per:
            continue                                            # 단기예보가 있는 날은 그쪽을 쓴다
        w = land.get(f"wf{n}Pm") or land.get(f"wf{n}")
        if not w:
            continue
        pop = max(int(land.get(f"rnSt{n}Am") or 0), int(land.get(f"rnSt{n}Pm") or land.get(f"rnSt{n}") or 0))
        per[day] = [{"sky": kma_word_sky(w), "tmax": ta.get(f"taMax{n}"), "tmin": ta.get(f"taMin{n}"), "pop": pop}]
    return merge_days(per)


def wmo_sky(c):
    c = int(c or 0)
    if c >= 95: return "storm"
    if c in (71, 73, 75, 77, 85, 86): return "snow"
    if c in (80, 81, 82): return "shower"
    if c >= 51: return "rain"
    if c in (45, 48): return "fog"
    if c == 3: return "cloud"
    if c in (1, 2): return "partly"
    return "sun"


def fetch_open_meteo():
    """Open-Meteo 16일 일별 예보(키 없음). 기상청을 못 받을 때의 예비."""
    per = {}
    for lat, lng in [(33.50, 126.53), (33.25, 126.56)]:
        q = urllib.parse.urlencode({
            "latitude": lat, "longitude": lng, "timezone": "Asia/Seoul", "forecast_days": 16,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
        with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))["daily"]
        for i, day in enumerate(d["time"]):
            per.setdefault(day.replace("-", ""), []).append({
                "sky": wmo_sky(d["weather_code"][i]), "tmax": d["temperature_2m_max"][i],
                "tmin": d["temperature_2m_min"][i], "pop": d["precipitation_probability_max"][i]})
    return merge_days(per)


def fetch_weather(key):
    """기상청 → Open-Meteo 순서로 시도. 둘 다 실패하면 None (예측 저장은 막지 않는다)."""
    for name, fn in [("기상청 단기·중기예보", lambda: fetch_kma(key)), ("Open-Meteo", fetch_open_meteo)]:
        try:
            w = fn()
            if w:
                print(f"[ok] 날씨 {len(w)}일 ({name})")
                return w, name
        except Exception as e:
            print(f"[warn] 날씨 {name} 실패: {e}")
    return None, None


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
    weather, wsrc = fetch_weather(load_key()) if not sample else (None, None)
    if weather:
        data["weather"] = weather
        data["weatherSource"] = f"{wsrc} (제주시·서귀포시 중 나쁜 쪽)"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"저장: {OUT} ({len(rows)}건, sample={sample})")


if __name__ == "__main__":
    main()
