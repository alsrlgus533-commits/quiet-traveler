"""제출용 ZIP 만들기: dist/quiet-traveler-agent.zip

git 이 추적하는 파일 + forecast.json(실행용 예측 저장본)을 담고, .env 와 키가 들어갈 수 있는 파일은 뺀다.
    python tools/build_zip.py
"""
import os
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "quiet-traveler-agent.zip")
SKIP_PREFIX = (".claude/", "dist/", ".git")
SKIP_NAMES = {".env"}


def main():
    # -z: 한글 파일 이름을 따옴표·8진수로 바꾸지 않고 그대로 받는다
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout.decode("utf-8").split("\0")
    files = [f for f in files if f and not f.startswith(SKIP_PREFIX) and os.path.basename(f) not in SKIP_NAMES]
    if os.path.exists(os.path.join(ROOT, "forecast.json")):
        files.append("forecast.json")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(set(files)):
            z.write(os.path.join(ROOT, f), "quiet-traveler/" + f)
    # 키가 섞여 들어가지 않았는지 확인 (.env 값과 같은 문자열이 있으면 중단)
    secrets = []
    env = os.path.join(ROOT, ".env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8-sig"):
            if "=" in line and not line.strip().startswith("#"):
                v = line.split("=", 1)[1].strip()
                if len(v) >= 12:
                    secrets.append(v)
    with zipfile.ZipFile(OUT) as z:
        for n in z.namelist():
            data = z.read(n)
            for s in secrets:
                if s.encode() in data:
                    os.remove(OUT)
                    raise SystemExit(f"키로 보이는 값이 {n} 에 들어 있어 ZIP 을 지웠어요. 확인해 주세요.")
    print(f"저장: {OUT} ({len(files)}개 파일, {os.path.getsize(OUT) // 1024} KB) · 키 검사 통과")


if __name__ == "__main__":
    main()
