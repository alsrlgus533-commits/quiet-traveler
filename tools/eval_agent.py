"""에이전트 검증: 정해 둔 질문을 실제로 업스테이지 Solar 에이전트에 묻고, 답이 도구 결과에 근거하는지 자동으로 확인한다.

    python tools/eval_agent.py            # 결과: docs/에이전트_검증.md, docs/에이전트_검증_결과.json

확인하는 것 (질문마다)
  1. 도구 선택   : 그 질문에 맞는 도구(expect 중 하나 이상)를 불렀는가
  2. 장소 근거   : 답에 나온 장소 이름이 모두 도구 결과에 있는가 (지어낸 장소가 없는가)
  3. 링크        : 답의 지도 링크가 모두 도구가 만든 주소인가, 채워지지 않은 {{표시}} 가 남지 않았는가
  4. 근거 줄     : 답 끝에 '근거:' 가 있는가
  5. 수치 근거율 : 답에 나온 숫자(시간·분·%·°) 가운데 도구 결과에서 찾을 수 있는 비율 (참고 지표)
업스테이지 API 를 질문 수만큼 부르므로 사용량이 든다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent import agent, tools  # noqa: E402
from agent.core import store  # noqa: E402

QUESTIONS = [
    ("이번 토요일 비 안 오고 덜 붐비는 숲길 어디야?", ["find_quiet_places"]),
    ("내일 오전에 한산한 바다 추천해줘", ["find_quiet_places"]),
    ("오늘 오후 3시에 한산한 오름 알려줘", ["find_quiet_places"]),
    ("비 오는 날 가기 좋은 조용한 곳 있어?", ["find_quiet_places"]),
    ("아이랑 걷기 좋은 조용한 마을 추천해줘", ["find_quiet_places"]),
    ("성산 쪽에서 10시부터 반나절 코스 짜줘", ["plan_course"]),
    ("숙소가 애월인데 일요일 하루 코스 추천해줘", ["plan_course"]),
    ("서귀포에서 출발해서 5곳 도는 하루 코스 짜줘", ["plan_course"]),
    ("다음 주에 성산일출봉 가장 한산한 날은?", ["place_forecast"]),
    ("우도 내일 몇 시에 가면 덜 붐벼?", ["place_forecast"]),
    ("사려니숲길 이번 주말에 붐벼?", ["place_forecast"]),
    ("협재해수욕장 대신 갈 만한 한산한 곳 있어?", ["find_quiet_places", "place_forecast"]),
    ("이번 주 제주 날씨 어때?", ["get_weather"]),
    ("다음 주 평소보다 붐빌 관광지 10곳 순위 알려줘", ["rank_spots"]),
    ("이번 주말 평소보다 한산한 관광지는?", ["rank_spots"]),
    ("요즘 성산일출봉 실제로 붐벼?", ["wifi_visitors"]),
    ("요즘 평소보다 한산해진 관광지 알려줘", ["wifi_visitors"]),
    ("구좌읍은 무슨 요일에 사람이 적어?", ["area_visitors"]),
    ("주민에 비해 방문객이 많이 몰리는 읍면동은 어디야?", ["area_visitors"]),
    ("구도심은 하루 중 언제 카드 결제가 많아?", ["jeju_card_time_pattern"]),
    ("서울 맛집 추천해줘", []),          # 범위 밖: 도구 없이 할 수 있는 일을 안내해야 함
]

URL = re.compile(r"\((https?://[^\s)]+)\)")
NUM = re.compile(r"(\d{1,2}–\d{1,2}시|\d{1,2}:\d{2}|\d+(?:\.\d+)?\s*(?:분|%|°|명|곳|km|배))")


def _known_names():
    s = store()
    return sorted({p["name"] for p in s.places + s.famous}, key=len, reverse=True)


def _mentioned(text, names):
    found, t = [], text
    for n in names:                       # 긴 이름부터 지워 가며 찾는다 (성산일출봉 안의 '성산' 등 겹침 방지)
        if n in t:
            found.append(n)
            t = t.replace(n, " ")
    return found


def run_one(q, expect, names):
    calls = []
    orig = tools.call

    def spy(name, args):
        r = orig(name, args)
        calls.append({"tool": name, "args": args, "result": r})
        return r

    tools.call = spy
    t0 = time.time()
    try:
        out = agent.run([{"role": "user", "content": q}])
        err = None
    except Exception as e:                # API 오류도 결과에 남긴다
        out, err = {"reply": "", "steps": []}, f"{type(e).__name__}: {e}"
    finally:
        tools.call = orig
    sec = round(time.time() - t0, 1)
    reply = out.get("reply", "")
    used = [c["tool"] for c in calls]
    blob = json.dumps([c["result"] for c in calls], ensure_ascii=False)

    links = {}
    for c in calls:
        agent._linkify(c["result"], links)
    allowed = set(URL.findall(" ".join(f"({u})" for v in links.values() for u in URL.findall(v))))
    urls = URL.findall(reply)
    bad_urls = [u for u in urls if u not in allowed]

    places = _mentioned(reply, names)
    # 질문에 사용자가 직접 적은 장소(예: '협재해수욕장 대신…')는 답에 나와도 지어낸 것이 아니므로 뺀다
    unsupported = [n for n in places if n not in blob and n not in q]

    text = re.sub(r"\[[^\]]*\]\(https?://[^\s)]+\)", " ", reply)     # 지도 링크 속 숫자는 빼고 센다
    nums = NUM.findall(text)
    def _in_blob(n):
        # '7–9시'·'10:15' 는 그 글자 그대로, 나머지는 숫자가 결과 JSON 의 한 값으로 있는지 (앞뒤가 숫자가 아닐 때만)
        if "–" in n or ":" in n:
            return n.replace(" ", "") in blob
        v = re.sub(r"[^\d.]", "", n)
        return bool(re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", blob))
    num_ok = sum(1 for n in nums if _in_blob(n))

    checks = {
        "tool": (not expect and not used) or bool(set(expect) & set(used)),
        "places": not unsupported,
        "links": not bad_urls and "{{" not in reply,
        "basis": (not expect) or ("근거" in reply),
    }
    return {"q": q, "expect": expect, "used": used, "sec": sec, "error": err,
            "places": places, "unsupported_places": unsupported, "links": len(urls), "bad_links": bad_urls,
            "numbers": len(nums), "numbers_found": num_ok, "checks": checks,
            "pass": all(checks.values()) and not err, "reply": reply}


def main():
    if "--rescore" in sys.argv:          # API 를 다시 부르지 않고, 저장된 답을 바뀐 기준으로 다시 채점
        saved = json.load(open(os.path.join(ROOT, "docs", "에이전트_검증_결과.json"), encoding="utf-8"))
        rows = saved["rows"]
        for r in rows:
            r["unsupported_places"] = [x for x in r["unsupported_places"] if x not in r["q"]]
            r["checks"]["places"] = not r["unsupported_places"]
            r["pass"] = all(r["checks"].values()) and not r["error"]
        return report(rows, saved["model"], saved["date"])
    names = _known_names()
    rows = []
    for i, (q, expect) in enumerate(QUESTIONS, 1):
        r = run_one(q, expect, names)
        rows.append(r)
        mark = "통과" if r["pass"] else "확인 필요"
        print(f"[{i:2}/{len(QUESTIONS)}] {mark} · {r['sec']}s · {', '.join(r['used']) or '도구 없음'} · {q}", flush=True)
    report(rows, os.environ.get("UPSTAGE_MODEL") or "solar-pro4", time.strftime("%Y-%m-%d"))


def report(rows, model, day):
    n = len(rows)
    passed = sum(r["pass"] for r in rows)
    agg = {k: sum(r["checks"][k] for r in rows) for k in ("tool", "places", "links", "basis")}
    nums = sum(r["numbers"] for r in rows)
    nums_ok = sum(r["numbers_found"] for r in rows)
    avg = round(sum(r["sec"] for r in rows) / n, 1)

    json.dump({"date": day, "model": model, "rows": rows}, open(os.path.join(ROOT, "docs", "에이전트_검증_결과.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    ok = lambda b: "○" if b else "×"
    lines = [
        "# 에이전트 검증 결과", "",
        f"- 날짜: {day} · 모델: 업스테이지 `{model}` · 질문 {n}개 (`python tools/eval_agent.py`)",
        f"- **전체 통과 {passed}/{n}**",
        f"- 도구 선택 {agg['tool']}/{n} · 장소 근거 {agg['places']}/{n} · 링크 정상 {agg['links']}/{n} · 근거 줄 {agg['basis']}/{n}",
        f"- 수치 근거율(참고): 답에 나온 숫자 {nums}개 중 {nums_ok}개({round(nums_ok / max(1, nums) * 100)}%)를 도구 결과에서 찾음",
        f"- 평균 응답 시간 {avg}초", "",
        "확인 기준: 도구 선택 = 질문에 맞는 도구를 불렀는가 · 장소 근거 = 답의 장소가 모두 도구 결과나 질문에 있는가(지어낸 장소 없음) · "
        "링크 = 지도 주소가 모두 도구가 만든 것인가 · 근거 줄 = 답 끝에 '근거:'가 있는가. "
        "수치 근거율은 표기 차이(0.87 → 13% 줄어듦 등)로 낮게 잡힐 수 있어 참고 지표로만 둔다.", "",
        "| # | 질문 | 부른 도구 | 도구 | 장소 | 링크 | 근거 | 수치 | 초 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        c = r["checks"]
        lines.append(f"| {i} | {r['q']} | {', '.join(r['used']) or '없음'} | {ok(c['tool'])} | {ok(c['places'])} | "
                     f"{ok(c['links'])} | {ok(c['basis'])} | {r['numbers_found']}/{r['numbers']} | {r['sec']} |")
    fails = [r for r in rows if not r["pass"]]
    if fails:
        lines += ["", "## 확인이 필요한 답", ""]
        for r in fails:
            why = [k for k, v in r["checks"].items() if not v]
            lines.append(f"- **{r['q']}** — {', '.join(why) or r['error']}"
                         + (f" · 근거 없는 장소: {', '.join(r['unsupported_places'])}" if r["unsupported_places"] else "")
                         + (f" · 오류: {r['error']}" if r["error"] else ""))
    open(os.path.join(ROOT, "docs", "에이전트_검증.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"\n통과 {passed}/{n} · 결과: docs/에이전트_검증.md")


if __name__ == "__main__":
    main()
