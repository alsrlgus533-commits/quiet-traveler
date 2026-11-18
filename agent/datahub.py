"""제주데이터허브 '관광지·상업지구 시간대별 카드 데이터' (필수 데이터).

요청: https://open.jejudatahub.net/api/proxy/{데이터키}/{프로젝트키}?startDate=YYYYMM&endDate=YYYYMM&districtType=…&userType=…
응답: {"totCnt", "hasMore", "data":[{districtType, userType, dtYearMonth, dateTimeCategory, userCount, useCount, useCost}]}

공개된 기간이 짧아(실제로 응답이 오는 달이 적다) 받은 결과를 agent/data/datahub_card_time.json 에 저장해 두고,
키가 없거나 API 가 응답하지 않을 때는 그 저장본을 쓴다.
    python -m agent.datahub      # 저장본 새로 받기 (.env 의 JEJU_DATAHUB_KEY 필요)
"""
from __future__ import annotations

import datetime as dt
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


# ======================================================================
# 와이파이 AP그룹별 일일 사용량  (매일 갱신, 약 3일 늦게 올라옴)
# 읍면동 단위 내국인 유동인구      (일 단위, 2~3달 늦게 올라옴)
# 둘 다 한 번에 100건까지만 주므로 number(쪽 번호)+limit=100 으로 끝까지 넘겨 받는다.
# ======================================================================
WIFI_KEY = "1aa9D5DabtDt1at935b1tt5t1D95t5at"
POP_KEY = "Daaa1t3at3tt8a8DD3t55538t35Dab1t"
WIFI_CACHE = os.path.join(HERE, "data", "datahub_wifi.json")
POP_CACHE = os.path.join(HERE, "data", "datahub_population.json")
WEEK = "월화수목금토일"

# 앱 장소 → 그 장소에 있는 공공와이파이 AP그룹 (이름이 장소를 직접 가리키는 것만. 버스정류소·충전소는 뺐다)
AP_MAP = {
    "삼다수숲길": ["삼다수숲길 주차장"],
    "서귀포 치유의숲": ["서귀포 치유의 숲"],
    "평대리 해변": ["평대포구"],
    "신창풍차해안": ["신창풍차해안도로"],
    "오조리 식산봉": ["성산.오조 지질트레일"],
    "하도 철새도래지": ["하도 해변"],
    "종달리 마을": ["종달리해변"],
    "성산일출봉": ["성산일출봉"],
    "우도": ["우도해안도로", "우도한반도여 입구해변", "우도비양도", "우도봉", "우도 한반도여", "우도 망루등대"],
    "협재해수욕장": ["협재 해변(협재해수욕장)"],
    "비자림": ["비자림"],
    "월정리해변": ["월정해수욕장 샤워탈의장"],
    "한담해변": ["한담해변"],
    "새별오름": ["새별오름"],
    "쇠소깍": ["하효 쇠소깍 해변"],
    "섭지코지": ["섭지코지"],
    "함덕해수욕장": ["함덕 서우봉 해변", "함덕 서우봉 해변 #1"],
    "천지연폭포": ["천지연폭포", "천지연폭포 매표소"],
    "정방폭포": ["정방폭포"],
    "중문색달해변": ["중문·색달해변"],
    "용두암": ["용두암"],
    "만장굴": ["만장굴"],
    "산방산": ["산방산"],
    "곽지해수욕장": ["곽지과물해변"],
    "금능해수욕장": ["금능으뜸원 해변(금능해수욕장)"],
    "김녕해수욕장": ["김녕 성세기 해변", "김녕해수욕장 샤워탈의장"],
    "표선해수욕장": ["표선 해비치 해변"],
    "천제연폭포": ["천제연폭포"],
    "외돌개": ["외돌개"],
    "송악산": ["송악산"],
    "절물자연휴양림": ["절물자연휴양림"],
    "광치기해변": ["광치기해변"],
    "한라산": ["한라산국립공원_성판악탐방안내소", "한라산국립공원 성판악탐방안내소", "한라산국립공원_어리목",
             "한라산국립공원_어리목탐방로입구", "한라산국립공원_진달래밭대피소", "한라산국립공원_속밭대피소",
             "한라산국립공원_삼각봉대피소", "한라산국립공원_백록담"],
    "1100고지습지": ["1100고지 휴게소"],
    "동문재래시장": ["제주동문시장"],
    "서귀포매일올레시장": ["서귀포매일올레시장"],
    "사려니숲길": ["사려니숲길"],
}
AP_SET = {a for v in AP_MAP.values() for a in v}

# 앱 장소 → 행정 읍면동 (유동인구 데이터의 emd 값). 주소의 읍·면은 그대로 쓰고, 동 지역만 손으로 맞췄다.
EMD_OF = {
    "서귀포 치유의숲": "대륜동", "성산일출봉": "성산읍", "우도": "우도면", "협재해수욕장": "한림읍", "비자림": "구좌읍",
    "월정리해변": "구좌읍", "한담해변": "애월읍", "새별오름": "애월읍", "쇠소깍": "효돈동", "섭지코지": "성산읍",
    "함덕해수욕장": "조천읍", "천지연폭포": "천지동", "중문색달해변": "중문동", "용두암": "용담2동", "만장굴": "구좌읍",
    "산방산": "안덕면", "오설록 티뮤지엄": "안덕면", "카멜리아힐": "안덕면", "곽지해수욕장": "애월읍", "금능해수욕장": "한림읍",
    "용머리해안": "안덕면", "김녕해수욕장": "구좌읍", "표선해수욕장": "표선면", "천제연폭포": "중문동", "외돌개": "서홍동",
    "송악산": "대정읍", "아부오름": "구좌읍", "용눈이오름": "구좌읍", "금오름": "한림읍", "절물자연휴양림": "봉개동",
    "광치기해변": "성산읍", "1100고지습지": "중문동", "동문재래시장": "일도1동", "보롬왓": "표선면", "사려니숲길": "조천읍",
}


def _pages(dkey, key, params):
    """number=1,2,… 로 끝까지 받는다. 실패하면 None."""
    rows, n = [], 1
    while n < 2000:
        q = urllib.parse.urlencode({**params, "number": n, "limit": 100})
        url = f"https://open.jejudatahub.net/api/proxy/{dkey}/{key}?{q}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "QuietTraveler"})
                j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
                break
            except Exception:
                time.sleep(1 + attempt * 2)
        else:
            return None
        data = j.get("data") or []
        rows += data
        if not j.get("hasMore") or not data:
            return rows
        n += 1
    return rows


def _ymd(d):
    return d.strftime("%Y%m%d")


def _iso(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def refresh_wifi(key, days=35):
    """가장 최근에 올라온 날부터 days 일치. 장소에 묶인 AP 만 저장하고, 제주 전체 합계도 함께 저장."""
    d = dt.date.today() - dt.timedelta(days=1)
    for _ in range(14):                                   # 최근 올라온 날 찾기
        q = urllib.parse.urlencode({"searchDate": _ymd(d), "number": 1, "limit": 1})
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://open.jejudatahub.net/api/proxy/{WIFI_KEY}/{key}?{q}", headers={"User-Agent": "QuietTraveler"}),
                timeout=60).read().decode("utf-8"))
        except Exception:
            j = {}
        if j.get("totCnt"):
            break
        d -= dt.timedelta(days=1)
    out = {}
    for i in range(days):
        day = d - dt.timedelta(days=i)
        rows = _pages(WIFI_KEY, key, {"searchDate": _ymd(day)})
        if not rows:
            print(f"  wifi {day}: 없음")
            continue
        aps = {r["apGroupName"]: int(r.get("userCount") or 0) for r in rows if r.get("apGroupName") in AP_SET}
        out[day.isoformat()] = {"jeju_total_users": sum(int(r.get("userCount") or 0) for r in rows),
                                "ap_groups": len(rows), "aps": aps}
        print(f"  wifi {day}: AP그룹 {len(rows)}곳")
    json.dump({"source": "제주데이터허브 와이파이 AP그룹별 일일 사용량", "dataKey": WIFI_KEY,
               "fetchedAt": time.strftime("%Y-%m-%d"), "latest": d.isoformat(), "days": out},
              open(WIFI_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장: {WIFI_CACHE} ({len(out)}일, 최근 {d})")


def refresh_population(key, weeks=8):
    """가장 최근에 올라온 날을 찾아 weeks 주치를 읍면동·날짜별 합계로 저장 (성별·연령 합산)."""
    end = None
    m = dt.date.today().replace(day=1)
    for _ in range(12):                                   # 달 끝에서부터 거꾸로 찾기
        last = m - dt.timedelta(days=1)                   # 지난달 말일
        for back in (0, 7, 14, 21, 27):
            day = last - dt.timedelta(days=back)
            rows = _pages(POP_KEY, key, {"startDate": _ymd(day), "endDate": _ymd(day), "emd": "구좌읍"})
            if rows:
                end = day
                break
        if end:
            break
        m = last.replace(day=1)
    if not end:
        print("  유동인구: 최근 1년 안에 올라온 날이 없어요.")
        return
    while True:                                           # 찾은 주에서 하루씩 앞으로 밀어 마지막 날 확정
        nxt = end + dt.timedelta(days=1)
        if not _pages(POP_KEY, key, {"startDate": _ymd(nxt), "endDate": _ymd(nxt), "emd": "구좌읍"}):
            break
        end = nxt
    start = end - dt.timedelta(days=weeks * 7 - 1)
    days = {}
    cur = start
    while cur <= end:                                     # 일주일씩 나눠 받기
        stop = min(end, cur + dt.timedelta(days=6))
        rows = _pages(POP_KEY, key, {"startDate": _ymd(cur), "endDate": _ymd(stop)}) or []
        for r in rows:
            dd = days.setdefault(_iso(r["baseDate"]), {})
            e = dd.setdefault(r["emd"], {"city": r.get("city"), "visit": 0, "resident": 0, "work": 0})
            e["visit"] += int(r.get("visitPop") or 0)
            e["resident"] += int(r.get("resdPop") or 0)
            e["work"] += int(r.get("workPop") or 0)
        print(f"  유동인구 {cur}~{stop}: {len(rows)}건")
        cur = stop + dt.timedelta(days=1)
    json.dump({"source": "제주데이터허브 읍면동 단위 내국인 유동인구", "dataKey": POP_KEY,
               "fetchedAt": time.strftime("%Y-%m-%d"), "start": start.isoformat(), "end": end.isoformat(), "days": days},
              open(POP_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장: {POP_CACHE} ({len(days)}일, {start}~{end})")


def _load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0


def _place_key(name):
    """'성산 일출봉' 같이 띄어 쓴 이름도 AP_MAP/EMD_OF 의 이름에 맞춘다."""
    n = (name or "").replace(" ", "")
    for k in list(AP_MAP) + list(EMD_OF):
        kk = k.replace(" ", "")
        if n == kk or (len(n) >= 2 and (n in kk or kk in n)):
            return k
    return None


def _series(days, aps):
    """날짜 오름차순 [(날짜, 접속자 합)]. 그 장소 AP 가 그날 하나도 안 잡혔으면(장비 꺼짐 등) 뺀다."""
    out = []
    for d in sorted(days):
        got = [days[d]["aps"][a] for a in aps if a in days[d]["aps"]]
        if got:
            out.append((d, sum(got)))
    return out


def _trend(series):
    """최근 7일 평균 ÷ 그 앞 기간 평균."""
    if len(series) < 10:
        return None
    recent, before = [v for _, v in series[-7:]], [v for _, v in series[:-7]]
    b = _avg(before)
    return round(_avg(recent) / b, 2) if b else None


def _trend_word(k):
    if k is None:
        return None
    return "요즘 평소보다 붐벼요" if k >= 1.2 else "요즘 평소보다 한산해요" if k <= .8 else "평소와 비슷해요"


def _weekday_profile(series):
    by = {i: [] for i in range(7)}
    for d, v in series:
        by[dt.date.fromisoformat(d).weekday()].append(v)
    base = _avg(v for _, v in series) or 1
    return {WEEK[i] + "요일": round(_avg(by[i]) / base * 100) for i in range(7) if by[i]}


def wifi_visitors(place_name: str = "", limit: int = 10):
    """공공와이파이 접속자 수로 본 장소별 최근 실제 붐빔."""
    w = _load(WIFI_CACHE)
    days = w.get("days") or {}
    if not days:
        return {"error": "와이파이 저장본이 없어요. 'python -m agent.datahub' 로 받아 주세요."}
    meta = {"source": "제주데이터허브 와이파이 AP그룹별 일일 사용량 (공공와이파이 하루 접속자 수)",
            "period": f"{min(days)} ~ {max(days)}", "latest_day": max(days),
            "note": "와이파이에 접속한 사람만 세므로 실제 방문객의 일부예요. 장소끼리 숫자를 견주기보다 같은 장소의 날짜별 변화를 보세요."}
    if place_name:
        k = _place_key(place_name)
        if not k or k not in AP_MAP:
            return {**meta, "error": f"'{place_name}'에는 이름이 맞는 공공와이파이 AP 가 없어요.",
                    "places_with_wifi": list(AP_MAP)}
        s = _series(days, AP_MAP[k])
        if not s:
            return {**meta, "error": f"'{k}' 와이파이 기록이 이 기간에 없어요."}
        prof = _weekday_profile(s)
        t = _trend(s)
        return {**meta, "place": k, "ap_groups": AP_MAP[k],
                "daily_users": [{"date": d, "weekday": WEEK[dt.date.fromisoformat(d).weekday()], "users": v}
                                for d, v in s[-14:]],
                "recent_7day_avg": round(_avg(v for _, v in s[-7:]), 1),
                "period_avg": round(_avg(v for _, v in s), 1),
                "recent_vs_before": t, "trend_word": _trend_word(t),
                "weekday_index_100_is_avg": prof,
                "quietest_weekday": min(prof, key=prof.get) if prof else None,
                "busiest_weekday": max(prof, key=prof.get) if prof else None}
    rows = []
    for k, aps in AP_MAP.items():
        s = _series(days, aps)
        t = _trend(s)
        if t is None:
            continue
        rows.append({"place": k, "recent_vs_before": t, "trend_word": _trend_word(t),
                     "recent_7day_avg_users": round(_avg(v for _, v in s[-7:]), 1)})
    rows.sort(key=lambda r: r["recent_vs_before"])
    tot = [(d, days[d]["jeju_total_users"]) for d in sorted(days)]
    n = max(1, min(20, int(limit)))
    return {**meta, "places_compared": len(rows),
            "quieter_than_before": rows[:n], "busier_than_before": rows[::-1][:n],
            "jeju_wide": {"recent_vs_before": _trend(tot), "trend_word": _trend_word(_trend(tot)),
                          "weekday_index_100_is_avg": _weekday_profile(tot)}}


def area_visitors(area: str = "", limit: int = 8):
    """읍면동 내국인 유동인구(방문 인구)로 본 지역별 요일 패턴·붐비는 정도."""
    p = _load(POP_CACHE)
    days = p.get("days") or {}
    if not days:
        return {"error": "유동인구 저장본이 없어요. 'python -m agent.datahub' 로 받아 주세요."}
    emds = sorted({e for d in days.values() for e in d})
    meta = {"source": "제주데이터허브 읍면동 단위 내국인 유동인구 (방문 인구 visitPop, 성별·연령 합산)",
            "period": f"{p.get('start')} ~ {p.get('end')}",
            "note": "공개가 2~3달 늦어 가장 최근 몇 주의 요일 패턴으로 보는 자료예요. 외국인은 포함되지 않아요."}
    if area:
        a = area.replace(" ", "")
        emd = next((e for e in emds if e == a or a in e), None)
        place = None
        if not emd:
            place = _place_key(area)
            emd = EMD_OF.get(place) if place else None
            if not emd:
                try:
                    from .core import store
                    pl = store().find(area)
                    if pl:
                        place = pl["name"]
                        emd = next((t for t in (pl.get("area") or "").split() if t in emds), None)
                except Exception:
                    pass
        if not emd:
            return {**meta, "error": f"'{area}'의 읍면동을 찾지 못했어요.", "areas": emds}
        s = [(d, days[d][emd]["visit"]) for d in sorted(days) if emd in days[d]]
        prof = _weekday_profile(s)
        res = _avg(days[d][emd]["resident"] for d in days if emd in days[d]) or 1
        allavg = {e: _avg(days[d][e]["visit"] for d in days if e in days[d]) for e in emds}
        rank = sorted(allavg, key=allavg.get, reverse=True).index(emd) + 1
        return {**meta, "area": emd, "place": place,
                "avg_daily_visitors": round(_avg(v for _, v in s)),
                "visitors_per_resident": round(_avg(v for _, v in s) / res, 2),
                "rank_among_areas_by_visitors": f"{rank}/{len(emds)}",
                "weekday_index_100_is_avg": prof,
                "quietest_weekday": min(prof, key=prof.get) if prof else None,
                "busiest_weekday": max(prof, key=prof.get) if prof else None,
                "last_7_days": [{"date": d, "weekday": WEEK[dt.date.fromisoformat(d).weekday()], "visitors": v}
                                for d, v in s[-7:]]}
    rows = []
    for e in emds:
        vis = _avg(days[d][e]["visit"] for d in days if e in days[d])
        res = _avg(days[d][e]["resident"] for d in days if e in days[d]) or 1
        rows.append({"area": e, "avg_daily_visitors": round(vis), "visitors_per_resident": round(vis / res, 2)})
    rows.sort(key=lambda r: r["visitors_per_resident"], reverse=True)
    n = max(1, min(20, int(limit)))
    jeju = [(d, sum(x["visit"] for x in days[d].values())) for d in sorted(days)]
    return {**meta, "ranked_by": "주민 대비 방문 인구 비율(높을수록 사는 사람에 비해 찾는 사람이 많음)",
            "most_visited_for_size": rows[:n], "least_visited_for_size": rows[::-1][:n],
            "jeju_weekday_index_100_is_avg": _weekday_profile(jeju)}


def refresh_all():
    key = env("JEJU_DATAHUB_KEY")
    if not key:
        raise SystemExit(".env 에 JEJU_DATAHUB_KEY 가 없습니다.")
    refresh_wifi(key)
    refresh_population(key)


if __name__ == "__main__":
    import sys
    if "--card" in sys.argv:
        refresh()                 # 카드 데이터(2017~2021 공개분)는 바뀌지 않아 필요할 때만
    else:
        refresh_all()
