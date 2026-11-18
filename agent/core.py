"""조용한 여행자 계산 로직 (화면 index.html 의 JavaScript 와 같은 식).

에이전트의 도구는 모두 이 모듈로 계산한다. 숫자는 여기서만 나오고, AI 는 질문 해석과 설명만 맡는다.
- 한산함 점수(0~100): 100 - 붐빔 추정. 붐빔 = 장소 규모(pop) × 그날 예측 배율 × 시간대 곡선
- 그날 예측 배율: 관광공사 집중률을 그 장소의 30일 평균과 비교 (예측이 없는 곳은 제주 전체 평균과 비교)
- 비 오는 날: 오름 제외, 숲길·마을 가점, 바다 감점
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import urllib.parse
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLACES_JSON = os.path.join(HERE, "data", "places.json")
FORECAST_JSON = os.path.join(ROOT, "forecast.json")
WD = "월화수목금토일"          # date.weekday() 순서
RAINY = {"rain", "shower", "snow", "storm"}
PROF_WORD = {"forest": "숲길", "oreum": "오름", "beach": "바다", "coast": "바다", "village": "마을"}


def jround(x: float) -> int:
    """JavaScript Math.round 와 같게(0.5 는 올림)."""
    return math.floor(x + 0.5)


# ---------- 하루 시간대 곡선 ----------
def _g(h, c, w):
    return math.exp(-(((h - c) / w) ** 2))


_RAW = {
    "forest": lambda h: _g(h, 12, 3),
    "oreum": lambda h: .45 * _g(h, 6.5, 1) + .8 * _g(h, 16.5, 1.6) + .6 * _g(h, 12, 2.6),
    "beach": lambda h: _g(h, 15, 2.6),
    "coast": lambda h: .55 * _g(h, 13, 3) + _g(h, 18, 1.3),
    "village": lambda h: _g(h, 14, 3),
}
_MAX = {k: max(f(h) for h in range(6, 21)) for k, f in _RAW.items()}


def prof(kind: str, h: float) -> float:
    return _RAW[kind](h) / _MAX[kind]


# ---------- 데이터 ----------
class Store:
    """장소·예측·날씨를 한 번 읽어 두고 계산에 쓴다."""

    def __init__(self, places_path=PLACES_JSON, forecast_path=FORECAST_JSON):
        p = json.load(open(places_path, encoding="utf-8"))
        self.places = p["places"]
        for x in self.places:
            x["api"] = p["api_name"].get(x["id"])
            x["famous"] = False
        self.famous = p["famous"]
        for i, f in enumerate(self.famous):           # 화면과 같은 id·규모
            f["id"], f["pop"], f["famous"] = f"f{i}", .5, True
            f["theme"] = PROF_WORD.get(f["prof"], "")
        self.swaps = p["swaps"]
        self.stay = p["stay"]
        self.rain_fit = p["rain_fit"]
        self.sun_up, self.sun_down = p["sun_up"], p["sun_down"]
        self.forecast = {"items": [], "sample": True}
        if os.path.exists(forecast_path):
            self.forecast = json.load(open(forecast_path, encoding="utf-8"))
        self.weather = self.forecast.get("weather") or {}
        self._index()

    def _index(self):
        by, sp = {}, {}
        self.rate = {}
        for it in self.forecast.get("items", []):
            if it.get("rate") is None:
                continue
            r = float(it["rate"])
            by.setdefault(it["date"], []).append(r)
            sp.setdefault(it["name"], []).append(r)
            self.rate[(it["date"], it["name"])] = r
        self.spot_avg = {n: sum(v) / len(v) for n, v in sp.items()}
        self.day_avg = {d: sum(v) / len(v) for d, v in by.items()}
        self.overall = (sum(self.day_avg.values()) / len(self.day_avg)) if self.day_avg else 1
        today = dt.date.today().strftime("%Y%m%d")
        ds = sorted(by)
        future = [d for d in ds if d >= today]
        self.dates = (future or ds)[:30]
        self.all_spots = sorted(sp)

    # --- 조회 ---
    def find(self, name: str):
        """이름(일부만 맞아도)으로 조용한 곳·유명한 곳을 찾는다."""
        name = name.replace(" ", "")
        pool = self.places + self.famous
        for p in pool:
            if p["name"].replace(" ", "") == name:
                return p
        for p in pool:
            n = p["name"].replace(" ", "")
            if name in n or n in name or (p.get("api") and name in p["api"].replace(" ", "")):
                return p
        return None

    def rate_of(self, api, date):
        return self.rate.get((date, api)) if api else None

    # --- 계산 (index.html 과 같은 식) ---
    def day_factor(self, date):
        a = self.day_avg.get(date)
        if a is None:
            return 1.15 if parse(date).weekday() >= 5 else 1
        return max(.8, min(1.3, a / self.overall))

    def rel_factor(self, p, date):
        r = self.rate_of(p.get("api"), date)
        if r is None or not self.spot_avg.get(p.get("api")):
            return self.day_factor(date)
        return max(.5, min(1.8, r / self.spot_avg[p["api"]]))

    def crowd(self, p, h, date):
        return min(100, jround(100 * p["pop"] * prof(p["prof"], h) * self.rel_factor(p, date) * 1.5 + 6))

    def quiet(self, p, h, date):
        return 100 - self.crowd(p, h, date)

    def best_window(self, p, date):
        m = parse(date).month - 1
        best, low = self.sun_up[m], 1e9
        for h in range(self.sun_up[m], self.sun_down[m] - 1):
            v = self.crowd(p, h, date) + self.crowd(p, h + 1, date)
            if v < low:
                low, best = v, h
        return best

    def usual(self, p, date):
        """그날 예측이 그 장소의 평소(30일 평균)보다 어떤지. 예측이 없으면 None."""
        r = self.rate_of(p.get("api"), date)
        avg = self.spot_avg.get(p.get("api"))
        if r is None or not avg:
            return None
        k = r / avg
        word = "평소보다 붐빔" if k > 1.15 else "평소보다 한산" if k < .85 else "평소 수준"
        return {"word": word, "ratio_to_usual": round(k, 2), "rate": r, "avg_30d": round(avg, 1)}

    def weather_of(self, date):
        return self.weather.get(date)

    def rainy(self, date):
        w = self.weather_of(date)
        return bool(w) and w.get("sky") in RAINY

    def day_state(self, date):
        f = self.day_factor(date)
        return "붐비는 날" if f > 1.08 else "한산한 날" if f < .95 else "평소 같은 날"

    # --- 코스 (빔 탐색, index.html makePlan 과 같은 식) ---
    def plan(self, date, start, n, pool=None, origin=None):
        """origin 을 주면 그곳에서 출발해 첫 장소까지 가는 시간도 계산한다 (첫 이동은 1분에 1점을 빼 가까운 곳을 더 먼저 고름)."""
        end = self.sun_down[parse(date).month - 1]
        wet = self.rainy(date)
        pool = pool or self.places
        if wet:
            pool = [p for p in pool if p["theme"] != "오름"]
        stay = self.stay

        def stop_score(q, p):
            return q - (30 if q < 45 else 0) + (self.rain_fit[p["theme"]] if wet else 0)

        def quiet_stay(p, t):
            return 100 - (self.crowd(p, t, date) + self.crowd(p, t + stay[p["theme"]] / 2, date)) / 2

        beam = []
        for p in pool:
            d0 = drive_min(origin, p) if origin else 0
            t0 = start + d0 / 60
            if t0 + stay[p["theme"]] <= end:
                q = quiet_stay(p, t0)
                beam.append({"stops": [(p, t0, q, d0)], "t": t0 + stay[p["theme"]],
                             "score": stop_score(q, p) + 8 - d0, "themes": {p["theme"]}})
        best = beam
        for _ in range(1, n):
            nxt = []
            for path in beam:
                last = path["stops"][-1][0]
                for p in pool:
                    if any(s[0] is p for s in path["stops"]):
                        continue
                    d = drive_min(last, p)
                    t = path["t"] + d / 60
                    if t + stay[p["theme"]] > end:
                        continue
                    q = quiet_stay(p, t)
                    nt = p["theme"] not in path["themes"]
                    nxt.append({"stops": path["stops"] + [(p, t, q, d)], "t": t + stay[p["theme"]],
                                "score": path["score"] + stop_score(q, p) - d * .5 + (8 if nt else 0),
                                "themes": path["themes"] | {p["theme"]} if nt else path["themes"]})
            if not nxt:
                break
            nxt.sort(key=lambda x: -x["score"])
            beam = nxt[:300]
            best = beam
        return max(best, key=lambda x: x["score"]) if best else None


# ---------- 도움 함수 ----------
def parse(ymd: str) -> dt.date:
    return dt.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def norm_date(s: str | None, store: Store) -> str:
    """'2026-11-22', '20261122', '11/22', '오늘', '내일', '토요일' 같은 말을 YYYYMMDD 로."""
    today = dt.date.today()
    if not s:
        return store.dates[0] if store.dates else today.strftime("%Y%m%d")
    s = s.strip()
    if s in ("오늘", "today"):
        return today.strftime("%Y%m%d")
    if s in ("내일", "tomorrow"):
        return (today + dt.timedelta(days=1)).strftime("%Y%m%d")
    if s in ("모레",):
        return (today + dt.timedelta(days=2)).strftime("%Y%m%d")
    for i, w in enumerate("월화수목금토일"):
        if s.startswith(w) and ("요일" in s or len(s) == 1):
            ahead = (i - today.weekday()) % 7
            return (today + dt.timedelta(days=ahead)).strftime("%Y%m%d")
    digits = "".join(c if c.isdigit() else " " for c in s).split()
    if len(digits) == 1 and len(digits[0]) == 8:
        return digits[0]
    if len(digits) >= 3:
        return f"{int(digits[0]):04d}{int(digits[1]):02d}{int(digits[2]):02d}"
    if len(digits) == 2:
        mo, d = int(digits[0]), int(digits[1])
        y = today.year + (1 if mo < today.month - 6 else 0)
        return f"{y:04d}{mo:02d}{d:02d}"
    raise ValueError(f"날짜를 알아볼 수 없어요: {s}")


def fmt_date(ymd: str) -> str:
    d = parse(ymd)
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def clock(h: float) -> str:
    m = jround(h * 60 / 5) * 5
    return f"{m // 60}:{m % 60:02d}"


def km(a, b):
    r = math.pi / 180
    dla, dlo = (b["lat"] - a["lat"]) * r, (b["lng"] - a["lng"]) * r
    x = math.sin(dla / 2) ** 2 + math.cos(a["lat"] * r) * math.cos(b["lat"] * r) * math.sin(dlo / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))


def drive_min(a, b):
    return max(10, jround(km(a, b) * 1.4 / 35 * 60 / 5) * 5)


def quiet_word(q):
    return "한산해요" if q >= 65 else "적당해요" if q >= 45 else "붐벼요"


def park_word(q):
    return "여유" if q >= 65 else "보통" if q >= 45 else "혼잡"


def kakao_to(p):
    return f"https://map.kakao.com/link/to/{urllib.parse.quote(p['name'])},{p['lat']},{p['lng']}"


def kakao_course(ps):
    return "https://map.kakao.com/link/by/car/" + "/".join(
        f"{urllib.parse.quote(p['name'])},{p['lat']},{p['lng']}" for p in ps[:7])


_NV = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _nv62(v):
    """네이버 지도 주소의 좌표 형식: 경·위도 × 1천만 + 20억을 62진수로 (index.html 의 nv62 와 같음)."""
    n, out = math.floor(v * 1e7 + 0.5) + 2_000_000_000, ""
    while n > 0:
        out = _NV[n % 62] + out
        n //= 62
    return out


def _nv_pt(p):
    return f"{_nv62(p['lng'])},{_nv62(p['lat'])},{urllib.parse.quote(p['name'])},,ADDRESS_POI"


def naver_course(ps):
    """네이버 지도 웹 길찾기. 출발을 '-' 로 비워 네이버 지도에서 내 위치 등으로 고르게 하고, 마지막 곳이 도착, 나머지는 경유(최대 5)."""
    goal, via = ps[-1], ps[:-1][:5]
    return (f"https://map.naver.com/p/directions/-/{_nv_pt(goal)}/"
            f"{':'.join(_nv_pt(p) for p in via) if via else '-'}/car")


def naver_to(p):
    return naver_course([p])


@lru_cache(maxsize=1)
def store() -> Store:
    return Store()
