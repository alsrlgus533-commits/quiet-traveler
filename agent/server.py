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
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import ROOT, env


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # .env 나 코드 폴더는 화면으로 내보내지 않는다
    def send_head(self):
        path = self.path.split("?")[0]
        if path.startswith("/.env") or path.startswith("/agent/") or path.startswith("/tools/") or path.startswith("/.git"):
            self.send_error(404)
            return None
        return super().send_head()

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
