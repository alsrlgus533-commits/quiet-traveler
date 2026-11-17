"""유명 관광지(build_famous.FAMOUS)의 대표 사진을 TourAPI(KorService2/searchKeyword2 의 firstimage)에서 받아
목록 행과 같은 760x230 으로 잘라 images/famous/<contentid>.webp 로 저장하고,
앱에 넣을 이름→파일 대응을 tools/famous_photos.json, 출처 표를 images/famous/README.md 로 남긴다.

  python tools/fetch_famous_photos.py
.env 의 TOUR_API_KEY 필요. Pillow 필요. 한 번 받아 두면 된다.
"""
import datetime as dt
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_famous import FAMOUS, ROOT, key, search  # noqa: E402
from PIL import Image  # noqa: E402

OUT_DIR = os.path.join(ROOT, "images", "famous")
W, H = 760, 230


def crop(img):
    img = img.convert("RGB")
    sw, sh = img.size
    target = W / H
    if sw / sh > target:                      # 옆으로 넓으면 양옆을 자른다
        nw = int(sh * target)
        img = img.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:                                     # 위아래를 자르되 살짝 위쪽(하늘보다 풍경)을 남긴다
        nh = int(sw / target)
        top = int((sh - nh) * 0.45)
        img = img.crop((0, top, sw, top + nh))
    return img.resize((W, H), Image.LANCZOS)


def main():
    k = key()
    os.makedirs(OUT_DIR, exist_ok=True)
    mapping, table, miss = {}, [], []
    for name, api, word, prof in FAMOUS:
        try:
            items = [i for i in search(k, word) if "제주" in (i.get("addr1") or "") and i.get("firstimage")]
        except Exception as e:
            miss.append(f"{name}: {e}")
            continue
        items.sort(key=lambda i: (i.get("title") != word, not i.get("title", "").startswith(word),
                                  word not in i.get("title", ""), len(i.get("title", ""))))
        if not items:
            miss.append(f"{name}: 사진 없음")
            continue
        it = items[0]
        url = it["firstimage"].replace("http://", "https://")
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "QuietTraveler"}), timeout=40).read()
            img = crop(Image.open(io.BytesIO(raw)))
        except Exception as e:
            miss.append(f"{name}: 내려받기 실패 {e}")
            continue
        fn = f"{it['contentid']}.webp"
        img.save(os.path.join(OUT_DIR, fn), "WEBP", quality=62, method=6)
        mapping[name] = fn
        table.append(f"| `{fn}` | {name} | {it.get('title')} | {it['contentid']} | {it.get('addr1', '')} |")
        print(f"  {name} -> {fn} ({os.path.getsize(os.path.join(OUT_DIR, fn)) // 1024}KB)")
    json.dump(mapping, open(os.path.join(ROOT, "tools", "famous_photos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    readme = [
        "# 유명 관광지 사진 출처", "",
        f"한국관광공사 국문 관광정보 서비스(TourAPI, `KorService2/searchKeyword2`)의 대표 사진(`firstimage`)을 "
        f"{dt.date.today().isoformat()}에 받아 760×230 으로 자르고 WebP 로 줄였다. `tools/fetch_famous_photos.py` 로 다시 만들 수 있다.", "",
        "| 파일 | 앱의 장소 | TourAPI 제목 | contentid | 주소 |", "|---|---|---|---|---|", *table, "",
    ]
    open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8").write("\n".join(readme))
    print(f"저장 {len(mapping)}장")
    for m in miss:
        print("  빠짐:", m)


if __name__ == "__main__":
    main()
