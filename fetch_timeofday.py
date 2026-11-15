"""제주데이터허브 '관광지·상업지구 시간대별 카드 데이터'를 월별로 받아
내국인 관광객이 주요 관광지에서 어느 시간대에 결제했는지 비율을 timeofday.json 으로 저장한다.

  .env 에 JEJU_DATAHUB_KEY=프로젝트키  가 있어야 한다.
  python fetch_timeofday.py
데이터는 과거 자료(2017-11~)라서 한 번만 받아 두면 된다.
"""
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "timeofday.json")
RAW_OUT = os.path.join(HERE, "timeofday_raw.json")
DATA_KEY = "DD7a1ta6tba70bt7tD1D1aDttDt701b7"
DISTRICT = "내국인 주요 관광지"
USER = "내국인관광객"
SLOTS = ["오전", "점심", "오후", "저녁", "밤"]


def load_key():
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        if line.strip().startswith("JEJU_DATAHUB_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env 에 JEJU_DATAHUB_KEY 가 없습니다.")


def month_range(start, end):
    y, m = start
    while (y, m) <= end:
        yield f"{y}{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def get(key, ym):
    q = urllib.parse.urlencode({"startDate": ym, "endDate": ym, "districtType": DISTRICT})
    url = f"https://open.jejudatahub.net/api/proxy/{DATA_KEY}/{key}?{q}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "QuietTraveler"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8")).get("data", [])
        except Exception as e:
            err = e
            time.sleep(2 + attempt * 3)
    print(f"  {ym}: 실패 ({err})")
    return None


def main():
    key = load_key()
    today = dt.date.today()
    rows = []
    for ym in month_range((2017, 11), (2022, 12)):   # 공개 자료는 이 범위 안에 있다
        data = get(key, ym)
        if data is None:
            continue
        rows += data
        users = sorted({r.get("userType") for r in data})
        print(f"  {ym}: {len(data)}건 {users}")
        time.sleep(0.5)
    json.dump(rows, open(RAW_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    rows = [r for r in rows if (r.get("userType") or "").replace(" ", "") == USER]
    total = {s: 0 for s in SLOTS}
    for r in rows:
        if r.get("dateTimeCategory") in total:
            total[r["dateTimeCategory"]] += int(r.get("useCount") or 0)
    s = sum(total.values()) or 1
    months = sorted({r["dtYearMonth"] for r in rows})
    data = {
        "source": "제주데이터허브 관광지·상업지구 시간대별 카드 데이터",
        "district": DISTRICT, "userType": USER,
        "period": [months[0], months[-1]] if months else None,
        "share": {k: round(v / s, 4) for k, v in total.items()},
    }
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("저장:", OUT, data["period"], data["share"])


if __name__ == "__main__":
    main()
