"""제주데이터허브 '관광지·상업지구 시간대별 카드 데이터' (필수 데이터).

요청: https://open.jejudatahub.net/api/proxy/{데이터키}/{프로젝트키}?startDate=YYYYMM&endDate=YYYYMM&districtType=…&userType=…
응답: {"totCnt", "hasMore", "data":[{districtType, userType, dtYearMonth, dateTimeCategory, userCount, useCount, useCost}]}

공개된 기간이 짧아(실제로 응답이 오는 달이 적다) 받은 결과를 agent/data/datahub_card_time.json 에 저장해 두고,
키가 없거나 API 가 응답하지 않을 때는 그 저장본을 쓴다.
    python -m agent.datahub      # 저장본 새로 받기 (.env 의 JEJU_DATAHUB_KEY 필요)
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

from .config import env

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "datahub_card_time.json")
DATA_KEY = "DD7a1ta6tba70bt7tD1D1aDttDt701b7"     # 관광지·상업지구 시간대별 카드 데이터
DISTRICTS = ["내국인 주요 관광지", "상업지", "중국인 주요 관광지", "제주시 구도심", "서귀포시 구도심"]
USERS = ["내국인관광객", "중국인관광객"]
SLOTS = ["오전", "점심", "오후", "저녁", "밤"]
MONTHS = ["201711", "201712", "201801", "202101", "202106", "202111"]


def _get(key, ym, district):
    q = urllib.parse.urlencode({"startDate": ym, "endDate": ym, "districtType": district})
    url = f"https://open.jejudatahub.net/api/proxy/{DATA_KEY}/{key}?{q}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "QuietTraveler"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8")).get("data", [])
        except Exception:
            time.sleep(1 + attempt * 2)
    return None


def refresh():
    key = env("JEJU_DATAHUB_KEY")
    if not key:
        raise SystemExit(".env 에 JEJU_DATAHUB_KEY 가 없습니다.")
    rows = []
    for d in DISTRICTS:
        for ym in MONTHS:
            data = _get(key, ym, d)
            print(f"  {d} {ym}: {'실패' if data is None else len(data)}")
            rows += data or []
            time.sleep(.3)
    json.dump({"source": "제주데이터허브 관광지·상업지구 시간대별 카드 데이터", "dataKey": DATA_KEY,
               "fetchedAt": time.strftime("%Y-%m-%d"), "rows": rows},
              open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장: {CACHE} ({len(rows)}건)")


def load_rows():
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8")).get("rows", [])
    return []


def card_time_pattern(district: str = "내국인 주요 관광지", user_type: str = "내국인관광객"):
    """지구·관광객 구분별로 시간대(오전·점심·오후·저녁·밤) 결제 비율을 낸다."""
    rows = [r for r in load_rows()
            if r.get("districtType") == district and r.get("userType", "").replace(" ", "") == user_type]
    if not rows:
        return {"error": f"'{district}' / '{user_type}' 데이터가 없어요.",
                "available_districts": sorted({r.get("districtType") for r in load_rows()})}
    tot = {s: 0 for s in SLOTS}
    users = {s: 0 for s in SLOTS}
    for r in rows:
        s = r.get("dateTimeCategory")
        if s in tot:
            tot[s] += int(r.get("useCount") or 0)
            users[s] += int(r.get("userCount") or 0)
    all_ = sum(tot.values()) or 1
    months = sorted({r["dtYearMonth"] for r in rows})
    peak = max(tot, key=tot.get)
    calm = min((s for s in SLOTS if s != "밤"), key=tot.get)
    return {
        "district": district, "user_type": user_type,
        "months": months,
        "share_of_card_use": {s: round(tot[s] / all_ * 100, 1) for s in SLOTS},
        "card_users": users,
        "busiest_slot": peak, "calmest_daytime_slot": calm,
        "source": "제주데이터허브 관광지·상업지구 시간대별 카드 데이터",
        "note": "카드 결제가 일어난 시간대의 비율이라 실제 방문 인원과 다를 수 있어요. 시간대 경계는 데이터에 정의돼 있지 않아요.",
    }


if __name__ == "__main__":
    refresh()
