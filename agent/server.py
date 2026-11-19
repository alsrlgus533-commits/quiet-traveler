"""화면(index.html)과 에이전트 API 를 함께 띄우는 로컬 서버 (표준 라이브러리만 사용).

    python -m agent.server            # http://localhost:8000 을 브라우저로 연다
    python -m agent.server --port 9000

POST /api/chat   {"messages":[{"role":"user","content":"…"}, …]} → {"reply", "steps", "model"}
GET  /api/health → {"ok", "agent": 키가 있어 대화가 되는지}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import ROOT, env

# 공개 주소에 띄울 때 업스테이지 사용량이 새지 않도록 질문 수를 묶는다 (0 이면 제한 없음, 내 PC 기본값).
#   CHAT_LIMIT_PER_IP_HOUR : 한 사람(IP)이 1시간에 할 수 있는 질문 수
#   CHAT_LIMIT_PER_DAY     : 서버 전체가 하루에 받는 질문 수
_LOCK = threading.Lock()
_HITS: dict[str, list[float]] = {}
_DAY = {"date": "", "n": 0}


def _allow(ip: str):
    per_ip = int(env("CHAT_LIMIT_PER_IP_HOUR", "0") or 0)
    per_day = int(env("CHAT_LIMIT_PER_DAY", "0") or 0)
    now, today = time.time(), time.strftime("%Y-%m-%d")
    with _LOCK:
        if _DAY["date"] != today:
            _DAY.update(date=today, n=0)
        if per_day and _DAY["n"] >= per_day:
            return "오늘 시연용 질문 수를 다 썼어요. 내일 다시 물어봐 주세요. (화면의 추천·지도·코스는 그대로 쓸 수 있어요)"
        hits = [t for t in _HITS.get(ip, []) if now - t < 3600]
        if per_ip and len(hits) >= per_ip:
            return f"질문이 많아 잠시 쉬어 갈게요. 1시간에 {per_ip}번까지 물을 수 있어요."
        hits.append(now)
        _HITS[ip] = hits
        _DAY["n"] += 1
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # .env 나 코드 폴더는 화면으로 내보내지 않는다
    def send_head(self):
        path = self.path.split("?")[0]
        if path.startswith(("/.env", "/agent/", "/tools/", "/.git", "/dist/", "/deploy/")):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        # 화면(HTML)과 예측 파일은 브라우저가 예전 것을 쓰지 않게 매번 서버에 확인하고(no-cache),
        # 바뀔 일이 드문 그림·글꼴은 하루 동안 저장해 두게 한다. (이 표시가 없으면 폰 브라우저가 몇 시간씩 옛 화면을 보여 줌)
        path = self.path.split("?")[0]
        if not path.startswith("/api/"):
            if path == "/" or path.endswith((".html", ".json")):
                self.send_header("Cache-Control", "no-cache")
            elif path.endswith((".webp", ".png", ".jpg", ".jpeg", ".svg", ".woff2", ".ico")):
                self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/health"):
            return self._json(200, {"ok": True, "agent": bool(env("UPSTAGE_API_KEY"))})
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/chat"):
            return self._json(404, {"error": "없는 주소"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(min(n, 200_000)).decode("utf-8") or "{}")
            history = data.get("messages") or []
            if not history or history[-1].get("role") != "user":
                return self._json(400, {"error": "마지막 메시지는 사용자 질문이어야 해요."})
            # Caddy 같은 앞단을 거쳐 오면 실제 접속 IP 는 X-Forwarded-For 첫 값이다
            ip = self.client_address[0]
            if ip in ("127.0.0.1", "::1") and self.headers.get("X-Forwarded-For"):
                ip = self.headers["X-Forwarded-For"].split(",")[0].strip()
            busy = _allow(ip)
            if busy:
                return self._json(429, {"error": busy})
            from .agent import run
            return self._json(200, run(history))
        except RuntimeError as e:                    # 키 없음 등 설정 문제
            return self._json(503, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._json(500, {"error": f"에이전트 오류: {type(e).__name__}: {e}"})

    def log_message(self, fmt, *args):
        # API 요청과 오류만 남기고, 그림·데이터 파일 요청 기록은 생략한다
        line = fmt % args
        if "/api/" in line or (args and str(args[0]).isdigit() and int(str(args[0])) >= 400):
            sys.stderr.write("%s - %s\n" % (self.address_string(), line))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(env("PORT", "8000")))
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(ROOT, "forecast.json")):
        print("[알림] forecast.json 이 없어요. 'python fetch_forecast.py' 로 예측을 먼저 받으면 실제 데이터로 계산해요.")
    if not env("UPSTAGE_API_KEY"):
        print("[알림] UPSTAGE_API_KEY 가 없어요. 화면은 뜨지만 AI 대화는 꺼져요. .env 에 키를 넣어 주세요.")
    print(f"조용한 여행자: http://localhost:{a.port}  (끄려면 Ctrl+C)")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
