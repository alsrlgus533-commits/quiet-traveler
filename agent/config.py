"""설정값 읽기: 환경변수가 먼저, 없으면 프로젝트 폴더의 .env 파일."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v:
        return v.strip()
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line.startswith(name + "="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return default
