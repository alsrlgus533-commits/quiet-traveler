"""업스테이지 Solar 로 도는 도구 호출 에이전트.

질문 → Solar 가 필요한 도구를 고름 → tools.py 가 데이터로 계산 → 결과를 Solar 에게 돌려줌 → 도구 결과에 근거한 답 (출처는 화면이 '조회한 데이터'로 표시).
업스테이지 API 는 OpenAI 호환이라 openai 패키지로 부른다 (base_url = https://api.upstage.ai/v1).

    python -m agent.agent "이번 토요일 덜 붐비는 숲길 어디야?"
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys

from openai import OpenAI

from . import tools
from .config import env
from .core import fmt_date, store

MAX_ROUNDS = 6           # 도구 호출을 몇 번까지 이어 갈지 (무한 반복 방지)

SYSTEM = """당신은 '조용한 여행자'라는 제주 여행·관광 분석 도우미입니다. 사람들이 덜 붐비는 제주를 고르도록 돕습니다.

말투 (가장 먼저 지킬 것)
- 사용자에게 하는 답은 처음부터 끝까지 부드러운 존댓말 해요체로 씁니다: '~해요', '~이에요', '~예요', '~세요', '~할게요'.
- 반말('~해', '~야', '~어', '~지', '~거든', '좋아', '붐벼')이나 딱딱한 문어체('~이다', '~한다', '~습니다')는 쓰지 않습니다. 목록 항목 끝도 '~해요'로 맞춥니다.

규칙
- 장소·시간·날씨·순위·비율 같은 숫자와 사실은 반드시 도구 결과에서만 가져온다. 도구에 없는 숫자나 장소를 지어내지 않는다.
- 질문에 맞는 도구를 먼저 부른다. 필요하면 여러 도구를 차례로 부른다 (예: 날씨를 본 뒤 장소 찾기).
- 코스·일정을 짜 달라면 반드시 plan_course 를, 장소 추천이면 find_quiet_places 를 부르고, 그 결과에 나온 장소만 말한다. 도구 결과에 없는 장소 이름을 꺼내지 않는다.
- '평소보다 붐빌/한산할 관광지', '붐빌 관광지 순위'처럼 '평소보다'·'순위'가 나오면 rank_spots 를 부른다 (기간 말은 date_from 에 그대로). 그냥 '한산한 곳'은 find_quiet_places 다.
- 날짜가 없으면 오늘 기준으로 본다. '이번 주말'은 다가오는 토·일요일이다. '지금'은 아래에 적힌 현재 시각(정시)을 hour 로 쓴다.
- '○○ 근처', '○○ 쪽', '동쪽·서쪽·남쪽·북쪽' 처럼 위치가 나오면 find_quiet_places 의 near 에 넣는다. 이어지는 질문의 '거기·그 근처'는 앞 답에서 말한 장소를 near 에 넣는다.
- 앞 대화에 나온 정보로 답하더라도, 새로 장소·한산함·주차를 말하려면 도구를 다시 부른다.
- 비 예보가 있는 날은 오름을 권하지 않고 숲길·마을을 먼저 권한다.
- 답은 한국어로, 쉬운 말로 짧게. 먼저 결론 한두 문장, 그다음 장소·코스를 목록으로. 화면이 표(|)·제목(#)·구분선(---)을 못 그리므로 굵은 글씨와 '-' 목록만 쓴다.
- 장소마다 한산함(한산해요/적당해요/붐벼요), 가장 여유로운 시간, 주차 예상을 붙인다.
- 여행객·도민에게는 붐빔을 퍼센트·배율·집중률 숫자로 말하지 않는다. '평소보다 꽤 한산해요 / 평소와 비슷해요 / 평소보다 붐벼요'처럼 말로 바꾼다 (예: 평소의 87% → 평소보다 조금 한산해요). 비 올 확률도 '비 올 가능성이 높아요/낮아요'처럼 말한다. 다만 '순위·분석·데이터·몇 퍼센트'처럼 담당자가 숫자를 묻는 질문에는 숫자를 그대로 쓴다.
- 길안내는 도구 결과의 directions·course_route 값(예: {{길안내:삼다수숲길}}, {{코스경로1}})을 중괄호까지 그대로 적는다. 그 자리에 카카오맵 길안내 링크가 들어간다. 인터넷 주소(URL)는 직접 쓰지 않는다.
- '근거:' 줄이나 데이터 출처 목록을 답에 따로 쓰지 않는다. 화면이 답 아래에 조회한 데이터를 보여 준다. 다만 와이파이·유동인구처럼 지난 기록을 쓸 때는 기간을 문장 안에서 짧게 밝힌다.
- 도구 이름(find_quiet_places, plan_course 같은 영어 이름), '도구'라는 말, 도구를 부르거나 다시 답하는 과정, 계산 방식 설명을 답에 쓰지 않는다. 사용자에게는 결과만 말한다.
- 한산함과 주차는 실시간 측정이 아니라 예측·패턴으로 만든 추정이다. 사용자가 실시간인지 물으면 그렇게 답한다.
- 앞으로의 날짜는 관광공사 예측(find_quiet_places·place_forecast·rank_spots)으로, '요즘 실제로 어땠는지'는 와이파이 접속자(wifi_visitors)로, 지역·요일 패턴은 유동인구(area_visitors)로 답한다. 둘 이상을 함께 쓰면 근거가 더 탄탄하다.
- 와이파이·유동인구는 지난 기록이다. 기간(예: 10/12~11/15)을 밝히고, 미래 예측처럼 말하지 않는다. 와이파이 접속자는 방문객의 일부라 장소끼리 숫자를 견주지 않는다.
- 관광공사 집중률은 장소마다 '자기 평소 대비' 값이라, 장소끼리 방문객 수를 비교하는 말로 쓰지 않는다.
- 인사·감사('고마워', '안녕')에는 도구 없이 한두 문장으로만 답한다. 할 수 있는 일을 목록으로 늘어놓지 않는다.
- 제주 여행·관광 데이터와 상관없는 질문에는 할 수 있는 일을 한두 문장으로 짧게 안내한다."""


# {{길안내:이름}} · {{코스경로1}} — AI 가 괄호를 하나만 써도({길안내:이름}) 알아본다
_TOKEN = re.compile(r"\{\{?((?:길안내:|코스경로)[^{}]{0,40})\}?\}")


def _linkify(obj, links):
    """도구 결과의 지도 주소를 짧은 표시({{길안내:이름}})로 바꿔 AI 에게 보낸다.
    긴 주소를 AI 가 옮겨 적다 글자가 틀리는 일을 막고, 답이 나온 뒤 표시를 실제 링크로 바꾼다."""
    if isinstance(obj, list):
        return [_linkify(x, links) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k in ("directions_kakao", "directions_naver", "kakao_route", "naver_route"):
            continue
        out[k] = _linkify(v, links)
    if "directions_kakao" in obj:
        name = obj.get("name") or obj.get("place") or "장소"
        tok = f"길안내:{name}"
        links[tok] = f"[카카오맵 길안내]({obj['directions_kakao']})"   # 지도는 카카오맵 하나로 통일
        out["directions"] = "{{" + tok + "}}"
    if "kakao_route" in obj:
        tok = f"코스경로{sum(1 for t in links if t.startswith('코스경로')) + 1}"
        links[tok] = f"[카카오맵으로 코스 길안내]({obj['kakao_route']})"
        out["course_route"] = "{{" + tok + "}}"
    return out


def _fill(text, links):
    text = _TOKEN.sub(lambda m: links.get(m.group(1).strip(), ""), text)
    # 없는 표시를 지워 빈 목록 줄만 남았으면 그 줄도 지운다
    lines = [ln for ln in text.splitlines() if ln.strip() not in ("-", "*", "•", "- ·", "·")]
    return "\n".join(lines).strip()


# 답에 영어 도구 이름이 섞여 나오면 사람이 읽는 말로 바꾼다
TOOL_WORD = {
    "find_quiet_places": "한산한 곳 찾기", "place_forecast": "장소 예측", "plan_course": "코스 계산",
    "rank_spots": "붐빔 순위", "get_weather": "날씨 예보", "wifi_visitors": "와이파이 접속 기록",
    "area_visitors": "유동인구 기록", "jeju_card_time_pattern": "카드 결제 시간대",
}
# 찾는 동작을 '앞으로 하겠다'고만 한 말 (찾아보겠습니다·찾을게요·고를게·코스를 짤게요 …).
# '도와드릴게요'·'안내할게요' 같은 인사말은 걸리지 않게, 찾는 동작 낱말 바로 뒤의 말끝만 본다.
_PROMISE = re.compile(r"(찾|불러 ?보|불러 ?볼|부르|부를|알아보|알아볼|확인해 ?보|확인해 ?볼|조회|살펴보|살펴볼|골라 ?보|고르|고를|짜 ?보|짜 ?볼|짤)[^\s.,!?]{0,4}?(겠습니다|겠어요|게요|게)(?=[\s.!,]|$)")
# 제주 여행·혼잡에 대한 질문인지 (그렇다면 첫 차례부터 도구를 부르게 한다). '추천'은 '서울 맛집 추천'처럼 범위 밖에도 쓰여 뺐다.
_TRAVEL = re.compile(r"(한산|붐비|붐벼|붐빌|붐빔|덜 ?붐|조용|여유|코스|일정|날씨|비 ?와|비 ?오|관광지|명소|오름|숲길|바다|해변|해수욕장|마을|폭포"
                     r"|요일|몇 ?시|주차|와이파이|유동|카드|순위|근처|주변|쪽에서|가볼|가 ?볼|갈 ?만|어디|제주)")
# 도구를 하나도 안 불렀는데 한산함·주차를 말하면 지어낸 것이다
_CROWD = re.compile(r"(한산해요|적당해요|붐벼요|한산함|주차\s*(?:예상|여유|보통|혼잡))")
_BASIS = re.compile(r"^\s*(?:[-*•]\s*)?(?:\*\*)?\s*근거\s*(?:\*\*)?\s*[:：].*$", re.M)


def _finish(text, links, steps):
    """표시를 실제 링크로 채우고, '근거:' 줄은 뺀다 (출처는 화면이 답 아래 '조회한 데이터'로 따로 보여 줌).
    AI 가 길안내를 하나도 안 붙였으면, 답에 나온 장소(최대 5곳)의 길안내를 맨 아래에 붙인다."""
    text = _fill(text, links)
    if "](http" not in text:
        names = [t.split(":", 1)[1] for t in links if t.startswith("길안내:")]
        hit = [n for n in names if n in text][:5]
        if hit:
            text += "\n\n**길안내**\n" + "\n".join(f"- {n}: {links['길안내:' + n]}" for n in hit)
    text = _BASIS.sub("", text)
    for k, v in TOOL_WORD.items():
        text = text.replace(f"`{k}`", v).replace(k, v)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _now():
    """한국 시간 (VM 시계가 UTC 여도 '오늘'·'지금'이 틀리지 않게)."""
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))


def _context():
    s = store()
    now = _now()
    rng = f"{fmt_date(s.dates[0])} ~ {fmt_date(s.dates[-1])}" if s.dates else "없음"
    return (f"오늘은 {now.date().isoformat()} ({'월화수목금토일'[now.weekday()]}요일), 지금은 한국 시간 {now.hour}시 {now.minute:02d}분이다. "
            f"관광지 예측이 있는 기간: {rng}. 날씨 예보는 앞의 14일 정도만 있다.")


def client():
    key = env("UPSTAGE_API_KEY")
    if not key:
        raise RuntimeError("UPSTAGE_API_KEY 가 없어요. .env 파일에 'UPSTAGE_API_KEY=발급받은키' 를 넣어 주세요.")
    return OpenAI(api_key=key, base_url=env("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1"), timeout=60, max_retries=2)


def _named_place(question):
    """질문에 앱 장소 이름(띄어쓰기 무시)이 있으면 그 이름."""
    q = question.replace(" ", "")
    s = store()
    for p in sorted(s.places + s.famous, key=lambda x: -len(x["name"])):
        if p["name"].replace(" ", "") in q:
            return p["name"]
    return None


def _ungrounded(text, seen, question):
    """답에 나온 앱 장소 이름 가운데 도구 결과(seen)에도, 사용자 질문에도 없는 것 (띄어쓰기 무시)."""
    flat, q = seen.replace(" ", ""), question.replace(" ", "")
    s = store()
    names = sorted({p["name"] for p in s.places + s.famous}, key=len, reverse=True)
    out, t = [], text
    for n in names:
        if n in t:
            t = t.replace(n, " ")
            k = n.replace(" ", "")
            if k not in flat and k not in q:
                out.append(n)
    return out


# 오늘이 아닌 날의 코스를 묻는데 출발 시각이 없으면, AI 를 부르기 전에 몇 시에 출발할지 먼저 묻는다
# (출발 시각에 따라 장소마다 도착할 때의 한산함이 달라지므로). 다음 답에 시각이 오면 바로 코스를 짠다.
_COURSE = re.compile(r"(코스|일정|동선|루트)")
_OTHER_DAY = re.compile(r"(내일|모레|글피|주말|토요일|일요일|월요일|화요일|수요일|목요일|금요일|다음 ?주|\d+\s*일|\d+/\d+)")
_TIME = re.compile(r"(\d+\s*시|아침|오전|오후|점심|저녁|새벽|정오|지금|바로|일찍)")
ASK_TIME = "몇 시에 출발하실 거예요? 출발 시각에 맞춰, 장소마다 도착할 때 한산한 순서로 코스를 짜 드릴게요. (예: 9시, 오후 2시)"


def run(history: list[dict]) -> dict:
    """history = [{"role":"user"|"assistant","content":"…"}, …] (마지막은 user).
    돌려주는 값: {"reply": 답, "steps": [{"tool": 이름, "args": 인자, "ok": 성공 여부}]}"""
    c = client()
    model = env("UPSTAGE_MODEL", "solar-pro4")
    messages = [{"role": "system", "content": SYSTEM + "\n\n" + _context()}]
    link = re.compile(r"\[([^\]]+)\]\(https?://[^)]+\)")
    messages += [{"role": m["role"], "content": link.sub(lambda g: g.group(1), str(m["content"])) if m["role"] == "assistant" else str(m["content"])}
                 for m in history[-12:] if m.get("role") in ("user", "assistant") and m.get("content")]
    question = str(history[-1].get("content", ""))
    if _COURSE.search(question) and _OTHER_DAY.search(question) and not _TIME.search(question) and "오늘" not in question:
        return {"reply": ASK_TIME, "steps": [], "model": model}
    asked_time = len(history) >= 2 and history[-2].get("role") == "assistant" and str(history[-2].get("content", "")).startswith("몇 시에 출발하실 거예요")
    # 여행·혼잡 질문이면 첫 차례부터 도구를 꼭 부르게 한다 (인사·범위 밖 질문은 그대로 말로 답함)
    steps, links, nudged, grounded = [], {}, False, False
    if re.search(r"(요즘|최근|실제로)", question) and re.search(r"(붐|한산|사람)", question):
        force = {"type": "function", "function": {"name": "wifi_visitors"}}  # '요즘 실제로 붐벼?' 는 지난 와이파이 기록
    elif _named_place(question) and not re.search(r"(근처|주변|대신|말고|쪽|코스|일정)", question):
        force = {"type": "function", "function": {"name": "place_forecast"}}  # '사려니숲길 주말에 붐벼?' 처럼 한 장소를 물음
    elif re.search(r"(평소보다.{0,15}(관광지|곳|명소|데)|순위)", question):
        force = {"type": "function", "function": {"name": "rank_spots"}}   # '평소보다 ~한 관광지' · '순위' 는 평소 대비 순위
    else:
        force = bool(_TRAVEL.search(question))
    if asked_time and _TIME.search(question):
        force = {"type": "function", "function": {"name": "plan_course"}}   # 앞에서 물은 출발 시각에 답했으면 바로 코스
        # '9시'만 보내면 앞 질문의 날짜(토요일 등)를 놓치므로, 앞 질문과 합쳐 한 질문으로 넘긴다
        prev_q = str(history[-3].get("content", "")) if len(history) >= 3 and history[-3].get("role") == "user" else ""
        if prev_q:
            question = f"{prev_q} (출발 시각: {question})"
            messages[-1] = {"role": "user", "content": question}
    seen = ""                                   # 지금까지 받은 도구 결과 글자 (답 검사용)
    for _ in range(MAX_ROUNDS):
        # 검사 장치가 다시 시킨 차례에는 말로 미루지 못하게 도구 호출을 강제한다
        resp = c.chat.completions.create(model=model, messages=messages, tools=tools.TOOLS,
                                         tool_choice=force if isinstance(force, dict) else ("required" if force else "auto"))
        force = False
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        if not calls:
            text = msg.content or ""
            # 1) "찾아보겠습니다"처럼 하겠다는 말만 하고 도구를 안 부른 채 끝내면, 한 번 더 실제로 하게 시킨다
            # (날씨만 보고 "찾아볼게요"로 멈춘 경우도 포함)
            if not nudged and ((len(text) < 600 and _PROMISE.search(text)) or (not steps and _CROWD.search(text))):
                nudged = True
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "(안내: 방금 답은 사용자에게 보내지 않았어요. 이 과정은 말하지 말고, 도구를 불러 그 결과로 처음부터 답해 주세요.)"})
                force = True
                continue
            # 2) 답 검사: 도구 결과에 없는 장소를 추천했으면 내보내지 않고, 도구로 찾은 뒤 다시 답하게 한다
            bad = _ungrounded(text, seen, question)
            if bad and not grounded:
                grounded = True
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content":
                    f"(안내: 방금 답은 사용자에게 보내지 않았어요. 도구 결과에 없는 장소({', '.join(bad[:6])})가 있었어요. 이 과정은 말하지 말고, find_quiet_places 같은 도구를 "
                    "먼저 부르고 그 결과에 나온 장소와 값만 써서 처음부터 답해 주세요.)"})
                force = True
                continue
            if bad:                              # 다시 답하게 했는데도 남았으면 그 장소가 나온 줄을 지운다
                kept = [ln for ln in text.splitlines() if not any(b in ln for b in bad)]
                if any(ln.strip() for ln in kept):
                    text = "\n".join(kept)
            return {"reply": _finish(text, links, steps), "steps": steps, "model": model,
                    "checked": {"retried_for_action": nudged, "retried_for_grounding": grounded}}
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in calls]})
        for tc in calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "도구 인자를 JSON 으로 읽지 못했어요. 다시 보내 주세요."}
            else:
                result = tools.call(tc.function.name, args)
            steps.append({"tool": tc.function.name, "args": args, "ok": "error" not in result})
            seen += json.dumps(result, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name,
                             "content": json.dumps(_linkify(result, links), ensure_ascii=False)})
    # 도구를 너무 많이 부르면 지금까지의 결과로 마무리하게 한다
    messages.append({"role": "user", "content": "지금까지 받은 도구 결과만으로 답을 마무리해 주세요."})
    resp = c.chat.completions.create(model=model, messages=messages)
    return {"reply": _finish(resp.choices[0].message.content or "", links, steps), "steps": steps, "model": model}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "이번 주말 비 안 오고 덜 붐비는 곳 추천해 줘"
    out = run([{"role": "user", "content": q}])
    for st in out["steps"]:
        print(f"[도구] {st['tool']} {json.dumps(st['args'], ensure_ascii=False)}")
    print(out["reply"])
