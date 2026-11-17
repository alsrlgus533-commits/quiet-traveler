"""유명 관광지 목록(FAMOUS)의 좌표를 한국관광공사 TourAPI(KorService2/searchKeyword2)에서 받아
index.html 에 붙여 넣을 JS 조각을 tools/famous.js 로 저장한다.

  python tools/build_famous.py
.env 의 TOUR_API_KEY 를 쓴다(공공데이터포털에서 '국문 관광정보 서비스' 활용신청 필요).
좌표는 한 번 받아 두면 되므로 매일 돌릴 필요 없다.
"""
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "famous.js")

# (앱에 보일 이름, 관광공사 예측 API 관광지명, TourAPI 검색어, 하루 곡선 유형)
FAMOUS = [
    ("성산일출봉", "성산일출봉 [유네스코 세계자연유산]", "성산일출봉", "oreum"),
    ("우도", "우도(해양도립공원)", "우도", "beach"),
    ("협재해수욕장", "협재해수욕장", "협재해수욕장", "beach"),
    ("비자림", "비자림", "비자림", "forest"),
    ("월정리해변", "월정리해변(월정리해수욕장)", "월정리해변", "beach"),
    ("한담해변", "한담해변", "한담해변", "coast"),
    ("새별오름", "새별오름", "새별오름", "oreum"),
    ("쇠소깍", "쇠소깍", "쇠소깍", "coast"),
    ("섭지코지", "섭지코지", "섭지코지", "coast"),
    ("함덕해수욕장", "함덕 서우봉 해변 (함덕해수욕장)", "함덕해수욕장", "beach"),
    ("천지연폭포", "천지연폭포 (제주도 국가지질공원)", "천지연폭포", "forest"),
    ("정방폭포", "정방폭포", "정방폭포", "coast"),
    ("중문색달해변", "중문·색달 해변", "중문색달해수욕장", "beach"),
    ("용두암", "용두암", "용두암", "coast"),
    ("만장굴", "만장굴 (제주도 국가지질공원)", "만장굴", "forest"),
    ("산방산", "산방산(제주)", "산방산", "oreum"),
    ("주상절리대", "주상절리대(대포동지삿개)", "주상절리대", "coast"),
    ("오설록 티뮤지엄", "오설록 티뮤지엄", "오설록 티뮤지엄", "village"),
    ("카멜리아힐", "카멜리아힐", "카멜리아힐", "forest"),
    ("이호테우해변", "이호테우해변", "이호테우해수욕장", "coast"),
    ("곽지해수욕장", "곽지해수욕장 (곽지과물해변)", "곽지해수욕장", "beach"),
    ("금능해수욕장", "금능해수욕장", "금능해수욕장", "beach"),
    ("용머리해안", "용머리해안", "용머리해안", "coast"),
    ("김녕해수욕장", "김녕성세기해변 (김녕해수욕장)", "김녕해수욕장", "beach"),
    ("표선해수욕장", "표선 해비치 해변", "표선해수욕장", "beach"),
    ("천제연폭포", "천제연폭포", "천제연폭포", "forest"),
    ("외돌개", "외돌개(제주)", "외돌개", "coast"),
    ("송악산", "송악산", "송악산", "oreum"),
    ("아부오름", "아부오름", "아부오름", "oreum"),
    ("용눈이오름", "용눈이오름", "용눈이오름", "oreum"),
    ("금오름", "금오름", "금오름", "oreum"),
    ("절물자연휴양림", "제주절물자연휴양림", "절물자연휴양림", "forest"),
    ("광치기해변", "광치기해변", "광치기해변", "coast"),
    ("세화해변", "세화해변", "세화해변", "beach"),
    ("한라산", "한라산 (제주도 국가지질공원)", "한라산", "forest"),
    ("1100고지습지", "1100고지습지", "1100고지", "forest"),
    ("동문재래시장", "동문재래시장", "동문재래시장", "village"),
    ("서귀포매일올레시장", "서귀포매일올레시장", "서귀포매일올레시장", "village"),
    ("보롬왓", "보롬왓", "보롬왓", "village"),
]


def key():
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if line.strip().startswith("TOUR_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env 에 TOUR_API_KEY 가 없습니다.")


def search(k, word):
    q = urllib.parse.urlencode({"serviceKey": k, "MobileOS": "WEB", "MobileApp": "QuietTraveler",
                                "_type": "json", "keyword": word, "numOfRows": 30, "pageNo": 1})
    url = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2?" + q
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "QuietTraveler"}), timeout=30).read()
    body = json.loads(raw.decode("utf-8"))["response"]["body"]
    items = (body.get("items") or {}).get("item") or []
    return [items] if isinstance(items, dict) else items


def main():
    k = key()
    rows, miss = [], []
    for name, api, word, prof in FAMOUS:
        try:
            items = [i for i in search(k, word) if "제주" in (i.get("addr1") or "")]
        except Exception as e:
            miss.append(f"{name}: {e}")
            continue
        # 제목이 검색어와 가장 가까운 것: 정확히 같은 것 > 검색어로 시작하는 것 > 포함하는 것
        def rank(i):
            t = i.get("title", "")
            return (t != word, not t.startswith(word), word not in t, len(t))
        items.sort(key=rank)
        if not items or not items[0].get("mapy"):
            miss.append(f"{name}: 검색 결과 없음")
            continue
        it = items[0]
        rows.append({"name": name, "api": api, "prof": prof,
                     "lat": round(float(it["mapy"]), 4), "lng": round(float(it["mapx"]), 4),
                     "src": it.get("title")})
    lines = ["// 유명 관광지(관광공사 예측 대상). 좌표는 TourAPI searchKeyword2, tools/build_famous.py 로 생성"]
    lines.append("const FAMOUS = [")
    for r in rows:
        lines.append(f'  {{name:"{r["name"]}", api:"{r["api"]}", prof:"{r["prof"]}", lat:{r["lat"]}, lng:{r["lng"]}}},'
                     f'  // {r["src"]}')
    lines.append("];")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"저장: {OUT} ({len(rows)}곳)")
    for m in miss:
        print("  빠짐:", m)


if __name__ == "__main__":
    main()
