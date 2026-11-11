
import os
import sys
import runpy
import traceback
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 디렉터리
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# 로그 파일
LOG_FILE = ROOT / "web-dashboard" / "start.log"

# 표준 출력과 오류를 파일로 저장
log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
sys.stdout = log
sys.stderr = log

print(f"\n[{datetime.now()}] MyAgent starting...")

try:
    runpy.run_path(
        str(ROOT / "web-dashboard" / "start.py"),
        run_name="__main__"
    )
except BaseException:
    traceback.print_exc()
finally:
    print(f"[{datetime.now()}] MyAgent stopped.")
    log.close()
