"""첫 화면 추천: 계산식이 고른 후보(최대 12곳) 가운데 AI 가 6곳(또는 5곳)을 골라 순서와 한 줄 이유를 붙인다.

토큰을 아끼는 방법
- 후보는 번호·이름·테마·한산함·차 시간만 한 줄씩 보낸다 (입력 약 550토큰, 출력 약 50토큰).
- 이유는 AI 가 꼬리표(한산·가까움·비·테마)만 고르고, 서버가 사실과 맞는지 확인해 정해진 문장으로 바꾼다 (지어낸 이유가 나오지 않게, 출력 토큰도 줄게).
- 가벼운 모델(UPSTAGE_PICKS_MODEL, 기본 solar-mini4)을 쓴다.
- 같은 날짜·같은 후보 묶음이면 서버가 기억해 둔 답을 그대로 돌려준다 (근처 사람들은 대부분 같은 후보라 캐시가 잘 맞는다).
- 하루 호출 수(PICKS_LIMIT_PER_DAY)와 한 사람의 1시간 호출 수(PICKS_LIMIT_PER_IP_HOUR)를 묶는다.
- AI 가 꺼져 있거나 늦거나 이상한 답을 주면 계산식 순서를 그대로 쓴다 (화면은 늘 뜬다).

장소 이름·테마는 화면이 보낸 글자가 아니라 서버의 장소 목록에서 읽는다 (캐시가 여러 사람에게 공유되므로).
"""
from __future__ import annotations

import json
import re
import threading
import time

from .config import env
from .core import store

_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}
_HITS: dict[str, list[float]] = {}
STATS = {"date": "", "calls": 0, "cache_hits": 0, "fallbacks": 0, "tokens_in": 0, "tokens_out": 0}

SYSTEM = (
    "너는 제주 여행 큐레이터다. 사람 많은 곳에 가면 지치는 내향적인 여행자에게, 후보 중에서 지금 가기 좋은 곳을 고른다.\n"
    "기준: 한산함(0~100, 높을수록 한산)이 가장 중요하다. 한산함이 더 높은 후보를 두고 낮은 후보를 고르지 않는다(다만 차로 20분 안의 가까운 곳은 조금 낮아도 된다). 테마는 겹치지 않게 고루 섞는다. "
    "비 예보가 있으면 숲길·실내처럼 비에 괜찮은 곳을 앞에 두고 오름·바다는 뒤로 뺀다.\n"
    "각 곳에 고른 까닭을 꼬리표 하나로 붙인다: 한산(사람이 적음), 가까움(차로 20분 안), 비(비 예보에 비에 괜찮은 테마), 테마(같은 테마 중 가장 한산).\n"
    '출력은 JSON 한 줄만. 예: {"pick":[[3,"한산"],[7,"가까움"],[1,"비"]]}'
)


def _today():
    return time.strftime("%Y-%m-%d")


def _roll_day():
    t = _today()
    if STATS["date"] != t:
        STATS.update(date=t, calls=0, cache_hits=0, fallbacks=0, tokens_in=0, tokens_out=0)
        _CACHE.clear()


def _allow(ip: str):
    per_ip = int(env("PICKS_LIMIT_PER_IP_HOUR", "0") or 0)
    per_day = int(env("PICKS_LIMIT_PER_DAY", "0") or 0)
    now = time.time()
    if per_day and STATS["calls"] >= per_day:
        return False
    hits = [t for t in _HITS.get(ip, []) if now - t < 3600]
    if per_ip and len(hits) >= per_ip:
        return False
    hits.append(now)
    _HITS[ip] = hits
    return True


def _clean(data: dict):
    """화면이 보낸 후보를 서버 장소 목록과 맞춰 본다. 모르는 id 는 버린다."""
    s = store()
    by_id = {p["id"]: p for p in s.places + s.famous}
    out = []
    for c in (data.get("cands") or [])[:12]:
        p = by_id.get(str(c.get("id", "")))
        if not p:
            continue
        q = max(0, min(100, int(round(float(c.get("q") or 0)))))
        drive = max(0, min(300, int(round(float(c.get("drive") or 0)))))
        kind = str(c.get("kind") or p.get("theme") or "")[:6]
        out.append({"id": p["id"], "name": p["name"], "kind": kind, "q": q, "drive": drive, "famous": bool(p.get("famous"))})
    n = 5 if int(data.get("n") or 6) == 5 else 6
    date = re.sub(r"[^0-9]", "", str(data.get("date") or ""))[:8]
    return out, n, date, bool(data.get("wet")), bool(data.get("near"))


def _key(cands, n, date, wet, near):
    # 한산함은 5점, 차 시간은 10분 단위로 묶어 근처 사람끼리 같은 답을 쓰게 한다
    body = ",".join(f"{c['id']}:{c['q']//5}:{c['drive']//10}" for c in sorted(cands, key=lambda c: c["id"]))
    return f"{date}|{int(wet)}|{int(near)}|{n}|{body}"


def _prompt(cands, n, date, wet, near):
    d = f"{date[4:6]}/{date[6:8]}" if len(date) == 8 else "오늘"
    head = f"날짜 {d}, {'비 예보' if wet else '비 없음'}, {'내 위치 기준 차 시간' if near else '위치 모름'}. {n}곳을 추천 순서로 골라."
    rows = [f"{i + 1}. {c['name']} | {c['kind']}{' (유명한 곳)' if c['famous'] else ''} | 한산함 {c['q']}"
            + (f" | 차로 {c['drive']}분" if near else "") for i, c in enumerate(cands)]
    return head + "\n" + "\n".join(rows)


def _why(tag, c, cands, wet, near, used=()):
    """AI 가 붙인 꼬리표가 후보의 사실과 맞을 때만 정해진 문장으로 바꾼다. 안 맞으면 맞는 꼬리표 중 첫째.
    같은 뜻의 문장을 여러 개 두고, 이미 쓴 문장은 피해서 판마다 같은 말이 되풀이되지 않게 한다."""
    rain_ok = store().rain_fit.get(c["kind"], 0) > 0
    best_kind = c["q"] >= max(o["q"] for o in cands if o["kind"] == c["kind"])
    close = near and c["drive"] <= 20
    facts = {
        "비": ["비 와도 걷기 좋아요", "비 오는 날에 잘 맞아요"] if wet and rain_ok else [],
        "한산": (["사람이 아주 적어요", "조용히 쉬기 좋아요", "붐빌 걱정 없어요", "한적하게 둘러봐요"] if c["q"] >= 75
                 else ["비교적 한산해요", "사람이 적은 편이에요", "여유롭게 볼 수 있어요"] if c["q"] >= 60 else []),
        "가까움": (["가깝고 조용해요", "가까워서 편해요"] if c["q"] >= 50 else ["차로 금방이에요"]) if close else [],
        "테마": [f"{c['kind']} 중 가장 한산해요"] if best_kind and c["kind"] else [],
    }
    tag = str(tag or "").strip()
    order = ([tag] if facts.get(tag) else []) + [k for k in ("비", "한산", "가까움", "테마") if k != tag]
    for k in order:
        for w in facts.get(k, []):
            if w not in used:
                return w
    return ""


def _parse(text, cands, n, wet, near):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        pick = json.loads(m.group(0)).get("pick") or []
    except Exception:
        return None
    ids, why, seen, per = [], {}, set(), {}
    for row in pick:
        if isinstance(row, dict):                      # {"번호":3,"이유":"…"} 꼴로 올 때
            row = list(row.values())
        if isinstance(row, (int, str)):                # 번호만 올 때
            row = [row]
        if not isinstance(row, (list, tuple)) or not row:
            continue
        try:
            i = int(row[0]) - 1
        except Exception:
            continue
        if not 0 <= i < len(cands) or i in seen:
            continue
        k = cands[i]["kind"]
        if per.get(k, 0) >= 2:                         # 같은 테마는 두 곳까지 (화면 계산식과 같은 규칙)
            continue
        per[k] = per.get(k, 0) + 1
        seen.add(i)
        ids.append(cands[i]["id"])
        w = _why(row[1] if len(row) > 1 else "", cands[i], cands, wet, near, set(why.values()))
        if w:
            why[cands[i]["id"]] = w
        if len(ids) == n:
            break
    for c in cands:                                    # 모자라면 계산식 순서로 채운다 (테마 규칙은 지키며)
        if len(ids) >= n:
            break
        if c["id"] not in ids and per.get(c["kind"], 0) < 2:
            per[c["kind"]] = per.get(c["kind"], 0) + 1
            ids.append(c["id"])
            w = _why("", c, cands, wet, near, set(why.values()))
            if w:
                why[c["id"]] = w
    if len(ids) < n:
        ids += [c["id"] for c in cands if c["id"] not in ids][: n - len(ids)]
    return {"ids": ids, "why": why}


def choose(data: dict, ip: str = "") -> dict:
    """POST /api/picks 의 본문을 받아 {"ids", "why", "ai", "cached"} 를 돌려준다."""
    cands, n, date, wet, near = _clean(data)
    fallback = {"ids": [c["id"] for c in cands][:n], "why": {}, "ai": False, "cached": False}
    if len(cands) <= n or not env("UPSTAGE_API_KEY"):
        return fallback
    key = _key(cands, n, date, wet, near)
    with _LOCK:
        _roll_day()
        if key in _CACHE:
            STATS["cache_hits"] += 1
            return {**_CACHE[key], "ai": True, "cached": True}
        if not _allow(ip):
            STATS["fallbacks"] += 1
            return fallback
        STATS["calls"] += 1
    try:
        from .agent import client
        r = client().with_options(timeout=12, max_retries=0).chat.completions.create(
            model=env("UPSTAGE_PICKS_MODEL", "solar-mini4"),
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": _prompt(cands, n, date, wet, near)}],
            temperature=0.2, max_tokens=120)
        u = getattr(r, "usage", None)
        out = _parse(r.choices[0].message.content, cands, n, wet, near)
    except Exception as e:
        print(f"[picks] AI 선별 실패, 계산식 순서로: {type(e).__name__}: {e}")
        u, out = None, None
    with _LOCK:
        if u:
            STATS["tokens_in"] += getattr(u, "prompt_tokens", 0) or 0
            STATS["tokens_out"] += getattr(u, "completion_tokens", 0) or 0
        if not out:
            STATS["fallbacks"] += 1
            return fallback
        if len(_CACHE) > 2000:                         # 하루 안에 이만큼 쌓일 일은 드물지만, 메모리가 커지지 않게
            _CACHE.clear()
        _CACHE[key] = out
    return {**out, "ai": True, "cached": False}
