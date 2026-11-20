"""장소별 무장애(장애인 편의시설) 정보 만들기: agent/data/access.json

제주관광공사 비짓제주 관광정보 OPEN API(vsjApi/contents/searchList) 전체(약 5,900건)를 받아,
앱의 장소(index.html 의 PLACES·FAMOUS)와 위치(2km 안)·이름이 맞는 항목의 태그(alltag)에서
편의시설 태그만 골라 담는다. 태그가 없는 장소는 '정보 없음'으로 두고 지어내지 않는다.

    python tools/build_access.py            # .env 의 VISITJEJU_API_KEY 필요
    python tools/build_access.py --cache 경로.json   # 미리 받아 둔 전체 목록으로 (API 호출 없이)
"""
import difflib
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "agent", "data", "access.json")
# 비짓제주 태그 → 앱에서 보여 줄 말 (보여 주는 순서)
TAGS = [
    ("장애인 전용 주차장", "장애인 주차"), ("장애인 주차", "장애인 주차"),
    ("장애인 화장실", "장애인 화장실"),
    ("수동 휠체어 대여 가능", "휠체어 대여"), ("전동 휠체어 대여 가능", "휠체어 대여"),
    ("장애인 전용 리프트", "리프트"),
    ("시각장애인 접근성", "시각장애인 안내"), ("청각장애인 접근성", "청각장애인 안내"),
    ("유모차 대여 서비스", "유모차 대여"), ("수유실", "수유실"),
]


def env(name):
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8-sig"):
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_all():
    key, items, page = env("VISITJEJU_API_KEY"), [], 1
    if not key:
        raise SystemExit(".env 에 VISITJEJU_API_KEY 가 없어요.")
    while True:
        q = urllib.parse.urlencode({"apiKey": key, "locale": "kr", "page": page})
        d = json.load(urllib.request.urlopen("http://api.visitjeju.net/vsjApi/contents/searchList?" + q, timeout=30))
        items += d.get("items") or []
        if page >= int(d.get("pageCount") or 1):
            return items
        page += 1


def app_places():
    """index.html 의 PLACES(조용한 곳)·FAMOUS(유명한 곳)에서 이름·좌표를 읽는다."""
    s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    out = []
    for m in re.finditer(r'\{id:"(\w+)", lat:([\d.]+), lng:([\d.]+), name:"([^"]+)"', s):
        out.append({"key": m.group(4), "name": m.group(4), "lat": float(m.group(2)), "lng": float(m.group(3))})
    fam = s[s.index("const FAMOUS = ["):]
    fam = fam[:fam.index("];")]
    for m in re.finditer(r'\{name:"([^"]+)",[^}]*?lat:([\d.]+), lng:([\d.]+)', fam):
        out.append({"key": m.group(1), "name": m.group(1), "lat": float(m.group(2)), "lng": float(m.group(3))})
    return out


def km(a, b):
    r = math.pi / 180
    x = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def norm(t):
    return re.sub(r"[\s()\[\]·\-]|해수욕장$|해변$", "", t or "")


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    items = json.load(open(cache, encoding="utf-8")) if cache else fetch_all()
    # 관광지·테마여행·쇼핑(시장) 항목에만 맞춘다 (같은 이름의 음식점·숙소·행사에 잘못 붙지 않게)
    items = [it for it in items if it.get("latitude") and it.get("longitude") and (it.get("contentscd") or {}).get("label") in ("관광지", "테마여행", "쇼핑")]
    result, table = {}, []
    for p in app_places():
        best = None
        for it in items:
            d = km((p["lat"], p["lng"]), (float(it["latitude"]), float(it["longitude"])))
            if d > 2:
                continue
            a, b = norm(p["name"]), norm(it.get("title"))
            sim = difflib.SequenceMatcher(None, a, b).ratio()
            if not (a in b or b in a or sim >= 0.6):
                continue
            score = sim - d * 0.1 + (0.3 if a == b else 0)
            if not best or score > best[0]:
                best = (score, it, d)
        tags = []
        if best:
            raw = [t.strip() for t in re.split(r"[,，]", best[1].get("alltag") or "")]
            for src, word in TAGS:
                if src in raw and word not in tags:
                    tags.append(word)
        result[p["key"]] = {"tags": tags, "source": best[1]["contentsid"] if best else None,
                            "title": best[1]["title"] if best else None}
        table.append((p["name"], best[1]["title"] if best else "-", round(best[2], 2) if best else "-", ", ".join(tags) or "-"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 앱(index.html)의 ACCESS 줄도 새로 쓴다: 정보가 있는 곳만 {장소 이름: [편의시설…]}
    idx = os.path.join(ROOT, "index.html"); html = open(idx, encoding="utf-8").read()
    line = "const ACCESS = " + json.dumps({k: v["tags"] for k, v in result.items() if v["tags"]}, ensure_ascii=False) + ";"
    html = re.sub(r"^const ACCESS = .*;$", lambda _: line, html, count=1, flags=re.M)
    open(idx, "w", encoding="utf-8", newline="").write(html)
    for row in table:
        print(" | ".join(map(str, row)))
    print(f"저장: {OUT} · 정보 있는 곳 {sum(1 for v in result.values() if v['tags'])}/{len(result)}")


if __name__ == "__main__":
    main()
