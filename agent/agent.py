"""업스테이지 Solar 로 도는 도구 호출 에이전트.

질문 → Solar 가 필요한 도구를 고름 → tools.py 가 데이터로 계산 → 결과를 Solar 에게 돌려줌 → 근거를 붙인 답.
업스테이지 API 는 OpenAI 호환이라 openai 패키지로 부른다 (base_url = https://api.upstage.ai/v1).

    python -m agent.agent "이번 토요일 덜 붐비는 숲길 어디야?"
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from openai import OpenAI

from . import tools
from .config import env
from .core import fmt_date, store

MAX_ROUNDS = 6           # 도구 호출을 몇 번까지 이어 갈지 (무한 반복 방지)

SYSTEM = """너는 '조용한 여행자'라는 제주 여행·관광 분석 도우미야. 사람들이 덜 붐비는 제주를 고르도록 돕는다.

규칙
- 장소·시간·날씨·순위·비율 같은 숫자와 사실은 반드시 도구 결과에서만 가져온다. 도구에 없는 숫자나 장소를 지어내지 않는다.
- 질문에 맞는 도구를 먼저 부른다. 필요하면 여러 도구를 차례로 부른다 (예: 날씨를 본 뒤 장소 찾기).
- 날짜가 없으면 오늘 기준으로 본다. '이번 주말'은 다가오는 토·일요일이다.
- 비 예보가 있는 날은 오름을 권하지 않고 숲길·마을을 먼저 권한다.
- 답은 한국어로, 쉬운 말로 짧게. 먼저 결론 한두 문장, 그다음 장소·코스를 목록으로.
- 장소마다 한산함(한산해요/적당해요/붐벼요), 가장 여유로운 시간, 주차 예상을 붙이고, 도구가 준 길안내 링크가 있으면 붙인다.
- 답 끝에 '근거:' 한 줄로 어떤 데이터(관광공사 예측, 기상청 예보, 제주데이터허브 카드 데이터 등)와 어느 날짜를 썼는지 적는다.
- 한산함과 주차는 실시간 측정이 아니라 예측·패턴으로 만든 추정이다. 사용자가 실시간인지 물으면 그렇게 답한다.
- 관광공사 집중률은 장소마다 '자기 평소 대비' 값이라, 장소끼리 방문객 수를 비교하는 말로 쓰지 않는다.
- 제주 여행·관광 데이터와 상관없는 질문에는 할 수 있는 일을 짧게 안내한다."""


def _context():
    s = store()
    today = dt.date.today()
    rng = f"{fmt_date(s.dates[0])} ~ {fmt_date(s.dates[-1])}" if s.dates else "없음"
    return (f"오늘은 {today.isoformat()} ({'월화수목금토일'[today.weekday()]}요일)이다. "
            f"관광지 예측이 있는 기간: {rng}. 날씨 예보는 앞의 14일 정도만 있다.")


def client():
    key = env("UPSTAGE_API_KEY")
    if not key:
        raise RuntimeError("UPSTAGE_API_KEY 가 없어요. .env 파일에 'UPSTAGE_API_KEY=발급받은키' 를 넣어 주세요.")
    return OpenAI(api_key=key, base_url=env("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1"))


def run(history: list[dict]) -> dict:
    """history = [{"role":"user"|"assistant","content":"…"}, …] (마지막은 user).
    돌려주는 값: {"reply": 답, "steps": [{"tool": 이름, "args": 인자, "ok": 성공 여부}]}"""
    c = client()
    model = env("UPSTAGE_MODEL", "solar-pro4")
    messages = [{"role": "system", "content": SYSTEM + "\n\n" + _context()}]
    messages += [{"role": m["role"], "content": str(m["content"])} for m in history[-12:]
                 if m.get("role") in ("user", "assistant") and m.get("content")]
    steps = []
    for _ in range(MAX_ROUNDS):
        resp = c.chat.completions.create(model=model, messages=messages, tools=tools.TOOLS, tool_choice="auto")
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        if not calls:
            return {"reply": (msg.content or "").strip(), "steps": steps, "model": model}
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
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name,
                             "content": json.dumps(result, ensure_ascii=False)})
    # 도구를 너무 많이 부르면 지금까지의 결과로 마무리하게 한다
    messages.append({"role": "user", "content": "지금까지 받은 도구 결과만으로 답을 마무리해 줘."})
    resp = c.chat.completions.create(model=model, messages=messages)
    return {"reply": (resp.choices[0].message.content or "").strip(), "steps": steps, "model": model}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "이번 주말 비 안 오고 덜 붐비는 곳 추천해 줘"
    out = run([{"role": "user", "content": q}])
    for st in out["steps"]:
        print(f"[도구] {st['tool']} {json.dumps(st['args'], ensure_ascii=False)}")
    print(out["reply"])
