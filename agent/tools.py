"""에이전트가 부르는 도구. 각 함수는 dict 를 돌려주고, 숫자는 모두 core 계산에서 나온다.
TOOLS 는 OpenAI 호환 함수 호출 형식(업스테이지 Solar 가 그대로 받는 형식)의 도구 설명이다."""
from __future__ import annotations

from . import core, datahub
from .core import (clock, drive_min, fmt_date, kakao_course, kakao_to, naver_course, naver_to, norm_date, park_word,
                   quiet_word, store)

THEMES = ["숲길", "오름", "바다", "마을"]


def _place_brief(s, p, h, date):
    q = s.quiet(p, h, date)
    out = {"name": p["name"], "kind": "유명한 곳" if p["famous"] else "조용한 곳", "theme": p["theme"],
           "area": p.get("area", ""), "quiet_score": q, "quiet_word": quiet_word(q),
           "parking": park_word(q), "best_window": f"{s.best_window(p, date)}–{s.best_window(p, date) + 2}시",
           "directions_kakao": kakao_to(p), "directions_naver": naver_to(p)}
    u = s.usual(p, date)
    if u:
        out["vs_usual"] = u["word"]
    return out


def _meta(s, date):
    w = s.weather_of(date)
    return {"date": date, "date_label": fmt_date(date), "jeju_day": s.day_state(date),
            "weather": w and {"word": w.get("word"), "tmax": w.get("tmax"), "tmin": w.get("tmin"), "rain_chance": w.get("pop")},
            "rainy": s.rainy(date)}


# ---------- 도구 ----------
def find_quiet_places(date: str = "", hour: int = 10, theme: str = "전체", include_famous: bool = False, limit: int = 5):
    s = store()
    date = norm_date(date, s)
    hour = max(6, min(20, int(hour)))
    pool = list(s.places) + (list(s.famous) if include_famous else [])
    if theme in THEMES:
        pool = [p for p in pool if p["theme"] == theme]
    wet = s.rainy(date)
    rows = [_place_brief(s, p, hour, date) for p in pool]
    # 비 오는 날 오름은 뒤로 (미끄럽고 바람이 세서)
    rows.sort(key=lambda r: ((wet and r["theme"] == "오름"), -r["quiet_score"]))
    for r in rows:
        if wet and r["theme"] == "오름":
            r["caution"] = "비 예보: 오름은 길이 미끄러워요"
    return {**_meta(s, date), "hour": hour, "places": rows[:max(1, min(16, int(limit)))],
            "basis": "관광공사 30일 예측(그 장소의 평소 대비) × 장소 규모 × 유형별 시간대 곡선으로 만든 한산함 추정(0~100)"}


def place_forecast(place_name: str, date: str = ""):
    s = store()
    p = s.find(place_name)
    if not p:
        return {"error": f"'{place_name}'을(를) 찾지 못했어요.",
                "known_places": [x["name"] for x in s.places + s.famous]}
    date = norm_date(date, s)
    days = []
    for d in s.dates[:14]:
        u = s.usual(p, d)
        w = s.weather_of(d)
        days.append({"date": fmt_date(d), "vs_usual": u and u["word"], "ratio_to_usual": u and u["ratio_to_usual"],
                     "weather": w and w.get("word"), "quiet_at_10": s.quiet(p, 10, d)})
    hours = [{"hour": h, "quiet_score": s.quiet(p, h, date), "quiet_word": quiet_word(s.quiet(p, h, date))}
             for h in range(6, 21)]
    has = any(x["ratio_to_usual"] for x in days)
    wifi = datahub.wifi_visitors(p["name"])
    recent = None if "error" in wifi else {
        "trend_word": wifi["trend_word"], "recent_vs_before": wifi["recent_vs_before"],
        "quietest_weekday": wifi["quietest_weekday"], "busiest_weekday": wifi["busiest_weekday"],
        "period": wifi["period"], "source": wifi["source"]}
    quiet_days = sorted([x for x in days if x["ratio_to_usual"]], key=lambda x: x["ratio_to_usual"])[:3]
    return {"place": _place_brief(s, p, 10, date) | {"desc": p.get("desc", "")}, **_meta(s, date),
            "hourly_on_date": hours, "next_14_days": days,
            "quietest_days": [x["date"] for x in quiet_days] if has else None,
            "recent_actual_wifi": recent,
            "forecast_source": "한국관광공사 관광지 집중률 방문자 추이 예측" if has else "예측 대상이 아니어서 제주 전체 예측과 유형별 패턴으로 추정"}


def get_weather(date: str = ""):
    s = store()
    if date:
        d = norm_date(date, s)
        return _meta(s, d) | {"source": s.forecast.get("weatherSource")}
    return {"days": [_meta(s, d) for d in s.dates[:14]], "source": s.forecast.get("weatherSource")}


# 출발 지역 → 대략의 중심 좌표 (앞에 있는 이름이 먼저 맞음)
REGIONS = [
    ("제주공항", 33.5070, 126.4929), ("공항", 33.5070, 126.4929), ("제주시", 33.4996, 126.5312),
    ("성산", 33.4500, 126.9100), ("서귀포", 33.2490, 126.5600), ("중문", 33.2500, 126.4120),
    ("애월", 33.4630, 126.3300), ("협재", 33.3940, 126.2400), ("한림", 33.4140, 126.2690),
    ("표선", 33.3260, 126.8300), ("세화", 33.5230, 126.8560), ("구좌", 33.5230, 126.8560),
    ("월정", 33.5560, 126.7960), ("함덕", 33.5430, 126.6690), ("조천", 33.5380, 126.6340),
    ("남원", 33.2790, 126.7190), ("모슬포", 33.2190, 126.2510), ("대정", 33.2190, 126.2510),
    ("안덕", 33.2560, 126.3200), ("고산", 33.3000, 126.1800), ("한경", 33.3000, 126.1800),
    ("교래", 33.4300, 126.6700),
]


def _origin(s, text):
    """'성산 쪽', '제주공항', '협재 숙소', 장소 이름, '구좌읍' 같은 말을 출발 좌표로."""
    t = (text or "").replace(" ", "")
    if not t:
        return None
    for name, lat, lng in REGIONS:
        if name in t:
            return {"name": name, "lat": lat, "lng": lng}
    p = s.find(t)
    if p:
        return {"name": p["name"], "lat": p["lat"], "lng": p["lng"]}
    near = [p for p in s.places if any(w and w in t for w in (p.get("area") or "").split()[1:])]
    if near:
        return {"name": text.strip(), "lat": sum(p["lat"] for p in near) / len(near),
                "lng": sum(p["lng"] for p in near) / len(near)}
    return None


def plan_course(date: str = "", start_hour: int = 10, stops: int = 3, theme: str = "전체", start_from: str = ""):
    s = store()
    date = norm_date(date, s)
    n = max(1, min(5, int(stops)))
    pool = [p for p in s.places if theme not in THEMES or p["theme"] == theme] or list(s.places)
    origin = _origin(s, start_from)
    note = None
    if start_from and not origin:
        note = f"'{start_from}'의 위치를 알아보지 못해 제주 전체에서 골랐어요."
    if origin:                                   # 출발지 가까운 곳부터: 30km 안 → 45km 안 → 전체
        for r in (30, 45, 999):
            near = [p for p in pool if core.km(origin, p) <= r]
            if len(near) >= n:
                pool = near
                break
    plan = s.plan(date, max(6, min(18, int(start_hour))), n, pool, origin)
    if not plan:
        return {**_meta(s, date), "error": "해 지기 전에 둘러볼 시간이 모자라요. 출발 시간을 앞당겨 보세요."}
    st = plan["stops"]
    items = [{"order": i + 1, "arrive": clock(t), "name": p["name"], "area": p.get("area", ""), "theme": p["theme"],
              "stay_min": round(s.stay[p["theme"]] * 60), "drive_from_prev_min": d,
              "quiet_word": quiet_word(q), "parking": park_word(q),
              "best_window": f"{s.best_window(p, date)}–{s.best_window(p, date) + 2}시",
              "directions_kakao": kakao_to(p), "directions_naver": naver_to(p)} for i, (p, t, q, d) in enumerate(st)]
    last = st[-1]
    out = {**_meta(s, date), "start_from": origin["name"] if origin else "첫 장소에서 시작",
           "depart": clock(max(6, min(18, int(start_hour)))), "stops": items,
           "end_time": clock(last[1] + s.stay[last[0]["theme"]]),
           "total_drive_min": sum(x["drive_from_prev_min"] for x in items),
           "kakao_route": kakao_course([x[0] for x in st]),
           "naver_route": naver_course([x[0] for x in st]),
           "rule": ("비 오는 날은 오름을 빼고 숲길·마을을 더 권함. " if s.rainy(date) else "")
                   + "한산함 합 − 이동 시간(출발지에서 첫 장소까지 포함), 테마가 다양할수록 가점"}
    if origin:
        out["first_leg"] = f"{origin['name']}에서 {items[0]['name']}까지 차로 약 {items[0]['drive_from_prev_min']}분"
    if note:
        out["note"] = note
    return out


def week_range(text):
    """'이번 주', '다음 주', '이번 주말', '다음 주말', '주말' → (시작, 끝) YYYYMMDD. 아니면 None."""
    import datetime as dt
    t = (text or "").replace(" ", "")
    if not t:
        return None
    today = dt.date.today()
    mon = today - dt.timedelta(days=today.weekday())
    f = lambda d: d.strftime("%Y%m%d")
    if t in ("이번주말", "주말", "이번주토일"):
        sat = mon + dt.timedelta(days=5)
        return f(max(sat, today)), f(mon + dt.timedelta(days=6))
    if t == "다음주말":
        return f(mon + dt.timedelta(days=12)), f(mon + dt.timedelta(days=13))
    if t == "이번주":
        return f(today), f(mon + dt.timedelta(days=6))
    if t == "다음주":
        return f(mon + dt.timedelta(days=7)), f(mon + dt.timedelta(days=13))
    return None


def rank_spots(date_from: str = "", date_to: str = "", order: str = "busy", limit: int = 10, scope: str = "all"):
    """기간 동안 '평소(30일 평균) 대비' 예측이 높은/낮은 관광지 순위."""
    s = store()
    span = week_range(date_from)
    if span:
        d0, d1 = span
    else:
        d0 = norm_date(date_from, s)
        d1 = norm_date(date_to, s) if date_to else d0
    days = [d for d in s.dates if d0 <= d <= d1] or [d0]
    names = s.all_spots if scope == "all" else [p["api"] for p in s.places + s.famous if p.get("api")]
    rows = []
    for n in names:
        rs = [s.rate.get((d, n)) for d in days]
        rs = [r for r in rs if r is not None]
        avg = s.spot_avg.get(n)
        if not rs or not avg:
            continue
        k = sum(rs) / len(rs) / avg
        rows.append({"spot": n, "ratio_to_usual": round(k, 2), "pct_of_usual": round(k * 100)})
    rows.sort(key=lambda r: r["ratio_to_usual"], reverse=(order != "quiet"))
    return {"period": f"{fmt_date(days[0])} ~ {fmt_date(days[-1])}", "order": "평소보다 붐비는 순" if order != "quiet" else "평소보다 한산한 순",
            "spots_compared": len(rows), "ranking": rows[:max(1, min(30, int(limit)))],
            "source": "한국관광공사 관광지 집중률 방문자 추이 예측 (제주 관광지, 30일)",
            "note": "집중률은 각 관광지의 자기 평소 대비 값이라, 관광지끼리 방문객 수를 비교한 것은 아니에요."}


def jeju_card_time_pattern(district: str = "내국인 주요 관광지", user_type: str = "내국인관광객"):
    return datahub.card_time_pattern(district, user_type)


def wifi_visitors(place_name: str = "", limit: int = 10):
    return datahub.wifi_visitors(place_name, limit)


def area_visitors(area: str = "", limit: int = 8):
    return datahub.area_visitors(area, limit)


FUNCS = {f.__name__: f for f in [find_quiet_places, place_forecast, get_weather, plan_course, rank_spots,
                                 wifi_visitors, area_visitors, jeju_card_time_pattern]}

_DATE = {"type": "string", "description": "날짜. 'YYYY-MM-DD', '11/22', '오늘', '내일', '토요일' 등. 비우면 예측 첫날(보통 오늘)."}
TOOLS = [
    {"type": "function", "function": {
        "name": "find_quiet_places",
        "description": "고른 날짜·시간에 한산한 제주 장소를 한산함 점수 순으로 찾는다. 날씨·그날 제주 붐빔·주차 예상·여유로운 시간·길안내 링크를 함께 준다.",
        "parameters": {"type": "object", "properties": {
            "date": _DATE,
            "hour": {"type": "integer", "description": "가는 시각(6~20시). 기본 10."},
            "theme": {"type": "string", "enum": ["전체", "숲길", "오름", "바다", "마을"]},
            "include_famous": {"type": "boolean", "description": "유명 관광지 37곳도 포함할지. 기본 false(덜 알려진 조용한 곳 16곳만)."},
            "limit": {"type": "integer", "description": "몇 곳까지. 기본 5."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "place_forecast",
        "description": "한 장소의 상세 예측: 그날 시간대별 한산함, 앞으로 14일의 평소 대비 예측과 날씨, 가장 한산한 날.",
        "parameters": {"type": "object", "properties": {
            "place_name": {"type": "string", "description": "장소 이름 (예: 성산일출봉, 따라비오름, 사려니숲길)"},
            "date": _DATE}, "required": ["place_name"]}}},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "제주 날씨 예보(기상청 단기·중기예보, 없는 날은 Open-Meteo). date 를 비우면 14일치.",
        "parameters": {"type": "object", "properties": {"date": _DATE}, "required": []}}},
    {"type": "function", "function": {
        "name": "plan_course",
        "description": "출발 시각·출발 지역·장소 수로 한산한 장소를 이어 코스를 짠다. 출발 지역을 주면 그 근처(30km 안)에서 고르고 첫 장소까지 이동 시간도 넣는다. 이동 시간·머무는 시간·해 지는 시각·비 예보를 반영하고 카카오맵 경로 링크를 준다.",
        "parameters": {"type": "object", "properties": {
            "date": _DATE,
            "start_hour": {"type": "integer", "description": "출발 시각(6~18시). 기본 10."},
            "stops": {"type": "integer", "description": "장소 수 1~5. 반나절 3, 하루 5."},
            "theme": {"type": "string", "enum": ["전체", "숲길", "오름", "바다", "마을"]},
            "start_from": {"type": "string", "description": "출발 지역이나 장소. 예: 성산, 제주공항, 서귀포, 중문, 애월, 협재, 함덕, 구좌읍, 사려니숲길. 사용자가 '어디 쪽에서', '숙소가 어디' 라고 하면 꼭 넣는다. 비우면 제주 전체에서 고름."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "rank_spots",
        "description": "기간 동안 제주 관광지(최대 448곳)를 '평소 대비' 예측으로 줄 세운다. 담당자의 '다음 주 붐빌 관광지 순위' 같은 분석 질문용.",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "시작 날짜. '이번 주', '다음 주', '이번 주말', '다음 주말' 처럼 기간 말을 그대로 넣어도 된다 (그때는 date_to 불필요)."},
            "date_to": _DATE,
            "order": {"type": "string", "enum": ["busy", "quiet"], "description": "busy=평소보다 붐비는 순, quiet=한산한 순"},
            "limit": {"type": "integer", "description": "몇 곳까지. 기본 10, 최대 30."},
            "scope": {"type": "string", "enum": ["all", "app"], "description": "all=예측 대상 전체, app=앱의 장소 53곳만"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "wifi_visitors",
        "description": "제주데이터허브 '와이파이 AP그룹별 일일 사용량'(공공와이파이 하루 접속자 수, 약 3일 전까지 매일 갱신)으로 최근 5주 실제 붐빔을 본다. "
                       "place_name 을 주면 그 장소의 날짜별 접속자·최근 7일 추세·요일별 지수, 비우면 37곳을 '요즘 평소보다 한산/붐빔' 순으로 준다. "
                       "'요즘 실제로 붐벼?', '무슨 요일이 한산해?' 같은 질문용.",
        "parameters": {"type": "object", "properties": {
            "place_name": {"type": "string", "description": "장소 이름. 비우면 전체 순위."},
            "limit": {"type": "integer", "description": "순위 몇 곳까지. 기본 10."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "area_visitors",
        "description": "제주데이터허브 '읍면동 단위 내국인 유동인구'(방문 인구, 공개가 2~3달 늦음)로 지역(읍면동)의 요일 패턴과 주민 대비 방문 비율을 본다. "
                       "area 에 읍면동(구좌읍)이나 장소 이름(따라비오름)을 주면 그 지역, 비우면 방문이 몰리는/한적한 지역 순위.",
        "parameters": {"type": "object", "properties": {
            "area": {"type": "string", "description": "읍면동 또는 장소 이름. 비우면 전체 순위."},
            "limit": {"type": "integer", "description": "순위 몇 곳까지. 기본 8."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "jeju_card_time_pattern",
        "description": "제주데이터허브 '관광지·상업지구 시간대별 카드 데이터'로 지구별 시간대(오전·점심·오후·저녁·밤) 카드 결제 비율을 본다. 하루 중 언제 붐비는지의 근거.",
        "parameters": {"type": "object", "properties": {
            "district": {"type": "string", "enum": datahub.DISTRICTS},
            "user_type": {"type": "string", "enum": datahub.USERS}}, "required": []}}},
]


def call(name: str, args: dict):
    f = FUNCS.get(name)
    if not f:
        return {"error": f"없는 도구: {name}"}
    try:
        return f(**(args or {}))
    except Exception as e:                       # 도구 오류는 에이전트에게 그대로 알려 다시 시도하게 한다
        return {"error": f"{type(e).__name__}: {e}"}
